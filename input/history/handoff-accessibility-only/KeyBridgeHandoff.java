package com.termux.x11.utils;

import android.content.Context;
import android.database.ContentObserver;
import android.hardware.input.InputManager;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.ViewTreeObserver;

import com.termux.x11.MainActivity;

import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

/** Explicit cooperation with the one reviewed Deskweft configuration, default off.
 * The private marker attests that setup; it is not a live read of another app's TOML.
 * No events, text, device descriptors, or window titles are recorded.
 */
public final class KeyBridgeHandoff {
    public static final String OPT_IN_FILE = "loopy-keybridge-handoff.opt-in";
    public static final String CONFIG_SHA256 = "628cc8736c1c09d0be7035f7e4a1aa8247984e3f1911ee9a1fc81d1e9e25ff5c";
    private static final Map<MainActivity, State> states = new WeakHashMap<>();
    private static boolean watchersAttempted;
    private static boolean watchersReady;

    private KeyBridgeHandoff() {}

    private static final class State implements ViewTreeObserver.OnWindowFocusChangeListener {
        final Set<Integer> capsDevices = new HashSet<>();
        final Map<Long, Long> ownedUps = new HashMap<>();
        final Set<Long> nativeUps = new HashSet<>();
        String services;
        boolean active;

        @Override public void onWindowFocusChanged(boolean focused) {
            if (!focused) synchronized (KeyBridgeHandoff.class) { capsDevices.clear(); }
        }
    }

    private static void clearCaps(int device, boolean all) {
        synchronized (KeyBridgeHandoff.class) {
            for (State state : states.values()) {
                if (all) state.capsDevices.clear();
                else state.capsDevices.remove(device);
                // Keep only the paired-UP claim; never synthesize a release for a raw key.
            }
        }
    }

    private static boolean watchBoundaries(MainActivity activity) {
        if (watchersAttempted) return watchersReady;
        watchersAttempted = true;
        try {
            Context app = activity.getApplicationContext();
            Handler handler = new Handler(Looper.getMainLooper());
            InputManager input = app.getSystemService(InputManager.class);
            if (input == null) return false;
            input.registerInputDeviceListener(new InputManager.InputDeviceListener() {
                @Override public void onInputDeviceAdded(int id) { clearCaps(id, false); }
                @Override public void onInputDeviceRemoved(int id) { clearCaps(id, false); }
                @Override public void onInputDeviceChanged(int id) { clearCaps(id, false); }
            }, handler);
            ContentObserver observer = new ContentObserver(handler) {
                @Override public void onChange(boolean selfChange) { clearCaps(0, true); }
            };
            app.getContentResolver().registerContentObserver(Settings.Secure.getUriFor(
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES), false, observer);
            app.getContentResolver().registerContentObserver(Settings.Secure.getUriFor(
                    Settings.Secure.ACCESSIBILITY_ENABLED), false, observer);
            watchersReady = true;
        } catch (RuntimeException unavailable) {
            // Without lifecycle boundaries the optional handoff stays off.
        }
        return watchersReady;
    }

    private static boolean optedIn(MainActivity activity) {
        byte[] expected = (CONFIG_SHA256 + "\n").getBytes(StandardCharsets.US_ASCII);
        ByteBuffer data = ByteBuffer.allocate(expected.length + 1);
        try (SeekableByteChannel channel = Files.newByteChannel(
                activity.getFilesDir().toPath().resolve(OPT_IN_FILE),
                StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            if (channel.size() != expected.length) return false;
            while (data.hasRemaining() && channel.read(data) > 0) {}
            if (data.position() != expected.length) return false;
            for (int i = 0; i < expected.length; i++) if (data.get(i) != expected[i]) return false;
            return true;
        } catch (Exception absentOrInvalid) { return false; }
    }

    private static boolean keyBridgeEnabled(String services) {
        if (services == null) return false;
        for (String component : services.split(":"))
            if (component.equals("dev.loopy.keybridge/dev.loopy.keybridge.RemapService")
                    || component.equals("dev.loopy.keybridge/.RemapService")) return true;
        return false;
    }

    private static boolean capsKey(KeyEvent event) {
        return event.getKeyCode() == 115
                || (event.getKeyCode() == 142 && event.getScanCode() == 58);
    }

    private static boolean mappedKey(int code) {
        // The attested Android keymap: H/J/K/L, D/F, 1..0, minus/equal.
        return code == 36 || code == 38 || code == 39 || code == 40
                || code == 32 || code == 34 || (code >= 7 && code <= 16)
                || code == 69 || code == 70;
    }

    private static long physicalKey(KeyEvent event) {
        int key = event.getScanCode() != 0 ? event.getScanCode() : event.getKeyCode() + 65536;
        return ((long) event.getDeviceId() << 32) | (key & 0xffffffffL);
    }

    /** Replacement for the single KeyInterceptor -> MainActivity.handleKey call. */
    public static synchronized boolean handleKey(MainActivity activity, KeyEvent event) {
        int action = event.getAction();
        if (action != KeyEvent.ACTION_DOWN && action != KeyEvent.ACTION_UP)
            return activity.handleKey(event);
        String services = Settings.Secure.getString(activity.getContentResolver(),
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        boolean active = optedIn(activity) && keyBridgeEnabled(services)
                && MainActivity.getInstance() == activity && activity.hasWindowFocus()
                && activity.getLorieView().connected() && watchBoundaries(activity);
        State state = states.get(activity);
        if (state == null && !active) return activity.handleKey(event);
        if (state == null) {
            state = new State();
            states.put(activity, state);
            activity.getWindow().getDecorView().getViewTreeObserver().addOnWindowFocusChangeListener(state);
        }
        if (state.active != active || !java.util.Objects.equals(state.services, services))
            state.capsDevices.clear();
        state.active = active;
        state.services = services;

        InputDevice device = event.getDevice();
        boolean virtual = event.getDeviceId() < 0 || (device != null && device.isVirtual());
        int code = event.getKeyCode();
        boolean legacyVirtual = virtual && (event.getFlags() & KeyEvent.FLAG_SOFT_KEYBOARD) != 0
                && event.isFromSource(InputDevice.SOURCE_KEYBOARD) && event.getScanCode() == 0
                && (code == 183 || code == 184);
        long key = physicalKey(event);
        // Installed RemoteKeys creates a fresh downTime on each injected DOWN and UP.
        // Native pairs use its exact virtual signature; raw Caps pairs retain downTime.
        if (state.nativeUps.contains(key) && legacyVirtual) {
            if (action == KeyEvent.ACTION_UP) state.nativeUps.remove(key);
            // Finish only our native pair across opt-in, focus, and service changes.
            if (activity.getLorieView().connected())
                return activity.getLorieView().sendKeyEvent(event.getKeyCode(), 0,
                        action == KeyEvent.ACTION_DOWN);
            return true;
        }
        Long ownedTime = state.ownedUps.get(key);
        if (ownedTime != null && ownedTime == event.getDownTime()) {
            if (action == KeyEvent.ACTION_UP) {
                state.ownedUps.remove(key);
                if (capsKey(event)) state.capsDevices.remove(event.getDeviceId());
            }
            return true;
        }
        if (action == KeyEvent.ACTION_DOWN) state.ownedUps.remove(key);
        if (!active) return activity.handleKey(event);

        if (legacyVirtual && action == KeyEvent.ACTION_DOWN) {
            // Deskweft's legacy aliases are Android PROG_RED/GREEN, not API36 F13/F14.
            // This verified JNI uses nonzero scanCode directly as Linux evdev, then adds 8.
            boolean sent = activity.getLorieView().sendKeyEvent(code, 0, true);
            if (sent) state.nativeUps.add(key);
            return sent;
        }
        boolean physical = device != null && !virtual && device.isExternal()
                && event.isFromSource(InputDevice.SOURCE_KEYBOARD)
                && (event.getFlags() & KeyEvent.FLAG_SOFT_KEYBOARD) == 0;
        if (!physical) return activity.handleKey(event);
        if (action == KeyEvent.ACTION_UP) {
            if (capsKey(event) && ownedTime == null) state.capsDevices.remove(event.getDeviceId());
            return activity.handleKey(event);
        }
        if (capsKey(event) || (state.capsDevices.contains(event.getDeviceId()) && mappedKey(code))) {
            if (capsKey(event)) state.capsDevices.add(event.getDeviceId());
            state.ownedUps.put(key, event.getDownTime());
            return true;
        }
        return activity.handleKey(event);
    }
}
