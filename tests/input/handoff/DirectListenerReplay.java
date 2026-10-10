import com.termux.x11.MainActivity;
import com.termux.x11.utils.KeyInterceptor;
import android.content.ContentResolver;
import android.provider.Settings;
import android.view.InputDevice;
import android.view.KeyEvent;
import java.nio.file.Files;
import java.nio.file.Path;

/** Real helper/interceptor; Activity listener, Android and native boundaries are stubs. */
public final class DirectListenerReplay {
    private static final String MARKER = "loopy-keybridge-handoff.opt-in";
    private static final String SHA = "628cc8736c1c09d0be7035f7e4a1aa8247984e3f1911ee9a1fc81d1e9e25ff5c\n";
    private static MainActivity activity;
    private static KeyInterceptor interceptor;
    private static int passed, failed;

    private interface Scenario { void run() throws Exception; }

    private static void check(boolean ok, String reason) {
        if (!ok) throw new AssertionError(reason);
    }

    private static void setup(boolean optIn) throws Exception {
        activity = new MainActivity();
        activity.files = Files.createTempDirectory("direct-listener-public-").toFile();
        MainActivity.focused = activity;
        interceptor = new KeyInterceptor();
        new InputDevice(1, false);
        new InputDevice(-1, true);
        Settings.Secure.services = "dev.loopy.keybridge/dev.loopy.keybridge.RemapService";
        ContentResolver.changed();
        if (optIn) Files.writeString(activity.files.toPath().resolve(MARKER), SHA);
    }

    private static KeyEvent legacy(int code, boolean down, long downTime) {
        return new KeyEvent(code, down ? 0 : 1, -1, 0, 2, downTime);
    }

    private static boolean deliver(boolean direct, KeyEvent event) {
        return direct ? activity.listener(event) : interceptor.onKeyEvent(event);
    }

    private static void pair(boolean direct, int code) {
        check(deliver(direct, legacy(code, true, 10)), "down-result");
        check(deliver(direct, legacy(code, false, 11)), "fresh-downTime-up-result");
        check(activity.forwarded == 0, "legacy-event-fell-through");
        check(activity.nativeKeys.toString().equals("[" + code + ":0:true, " + code + ":0:false]"),
              "expected-exactly-one-native-down-up");
    }

    private static void ordinary(KeyEvent event) {
        int before = activity.forwarded;
        check(activity.listener(event), "ordinary-result");
        check(activity.forwarded == before + 1 && activity.forwardedEvents.get(before) == event,
              "ordinary-object-not-forwarded-once");
        check(activity.nativeKeys.isEmpty(), "ordinary-event-rewritten");
    }

    private static void scenario(String name, Scenario action) {
        try {
            action.run(); passed++; System.out.println("PASS " + name);
        } catch (Throwable failure) {
            failed++; System.out.println("FAIL " + name + " " + failure.getMessage());
        } finally {
            if (activity != null) try {
                Files.deleteIfExists(activity.files.toPath().resolve(MARKER));
                Files.delete(activity.files.toPath());
            } catch (Exception cleanup) { throw new RuntimeException(cleanup); }
        }
    }

    public static void main(String[] args) {
        for (int code : new int[] {183, 184}) {
            scenario("direct-listener-legacy-" + code + "-native-pair", () -> { setup(true); pair(true, code); });
            scenario("accessibility-legacy-" + code + "-native-pair", () -> { setup(true); pair(false, code); });
        }
        scenario("direct-ordinary-caps-arrows-text-modifiers-object-unchanged", () -> {
            setup(true);
            for (int code : new int[] {115,142,36,38,39,40,32,34,19,20,21,22,29,61,111,117})
                for (int action : new int[] {0,1})
                    ordinary(new KeyEvent(code, action, 1, code == 115 ? 58 : 0, 0, 20 + code, 0x1003, 0));
        });
        scenario("direct-virtual-ordinary-output-object-and-meta-unchanged", () -> {
            setup(true);
            for (int code : new int[] {19,20,21,22,131,142,204})
                ordinary(new KeyEvent(code, 0, -1, 0, 2, 100 + code, 0x1003, 1));
        });
        scenario("accessibility-ordinary-goes-through-listener-exactly-once", () -> {
            setup(true); KeyEvent event = new KeyEvent(29, 0, 1, 30, 0, 200, 0x1003, 0);
            check(interceptor.onKeyEvent(event), "access-ordinary-result");
            check(activity.forwarded == 1 && activity.forwardedEvents.get(0) == event
                  && activity.nativeKeys.isEmpty(), "access-ordinary-duplicated-or-mutated");
        });
        scenario("direct-default-off-legacy-original-object", () -> { setup(false); ordinary(legacy(183,true,300)); });
        scenario("direct-wrong-marker-legacy-original-object", () -> {
            setup(true); Files.writeString(activity.files.toPath().resolve(MARKER), "0".repeat(64) + "\n");
            ordinary(legacy(184,true,310));
        });
        scenario("direct-malformed-marker-legacy-original-object", () -> {
            setup(true); Files.writeString(activity.files.toPath().resolve(MARKER), SHA + "extra");
            ordinary(legacy(183,true,320));
        });
        scenario("direct-symlink-marker-stays-default-off", () -> {
            setup(true); Path marker = activity.files.toPath().resolve(MARKER);
            Files.delete(marker); Files.createSymbolicLink(marker, Path.of("absent-public-target"));
            ordinary(legacy(184,true,330));
        });
        scenario("direct-service-disabled-original-object", () -> {
            setup(true); Settings.Secure.services = ""; ContentResolver.changed(); ordinary(legacy(183,true,340));
        });
        scenario("direct-unfocused-original-object", () -> {
            setup(true); activity.focus = false; ordinary(legacy(184,true,350));
        });
        scenario("direct-different-activity-owner-original-object", () -> {
            setup(true); MainActivity.focused = new MainActivity(); ordinary(legacy(183,true,360));
        });
        scenario("direct-disconnected-original-object", () -> {
            setup(true); activity.connected = false; ordinary(legacy(184,true,370));
        });
        scenario("direct-legacy-signature-is-narrow", () -> {
            setup(true);
            ordinary(new KeyEvent(183,0,1,0,0,380));
            ordinary(new KeyEvent(183,0,-1,0,0,381));
            ordinary(new KeyEvent(184,0,-1,13,2,382));
            ordinary(new KeyEvent(184,0,-1,0,2,383,0,0,0x2002));
            ordinary(new KeyEvent(183,2,-1,0,2,384));
        });
        scenario("direct-unmatched-up-original-object", () -> { setup(true); ordinary(legacy(184,false,390)); });
        scenario("direct-paired-up-survives-focus-service-marker-changes-and-fresh-time", () -> {
            setup(true); check(activity.listener(legacy(183,true,400)), "down-result");
            activity.focus = false;
            activity.getWindow().getDecorView().getViewTreeObserver().focus(false);
            Settings.Secure.services = ""; ContentResolver.changed();
            Files.delete(activity.files.toPath().resolve(MARKER));
            check(activity.listener(legacy(183,false,401)), "paired-up-result");
            check(activity.forwarded == 0 && activity.nativeKeys.toString().equals("[183:0:true, 183:0:false]"),
                  "owned-up-lost-or-duplicated");
        });
        for (boolean downDirect : new boolean[] {false,true}) {
            scenario("shared-ownership-down-direct-" + downDirect + "-up-other-path", () -> {
                setup(true); check(deliver(downDirect, legacy(184,true,410)), "cross-down");
                check(deliver(!downDirect, legacy(184,false,411)), "cross-up");
                check(activity.forwarded == 0 && activity.nativeKeys.toString().equals("[184:0:true, 184:0:false]"),
                      "cross-path-state-not-shared");
            });
        }
        scenario("direct-native-false-does-not-fall-through-or-claim-up", () -> {
            setup(true); activity.nativeAccept = false;
            check(!activity.listener(legacy(183,true,420)), "native-false-return-changed");
            check(activity.forwarded == 0 && activity.nativeKeys.size() == 1, "failed-send-fell-through");
            KeyEvent up = legacy(183,false,421); check(activity.listener(up), "unowned-up-result");
            check(activity.forwarded == 1 && activity.forwardedEvents.get(0) == up && activity.nativeKeys.size() == 1,
                  "failed-send-claimed-up");
        });
        scenario("direct-owned-up-disconnected-consumed-without-fallback", () -> {
            setup(true); check(activity.listener(legacy(184,true,430)), "connected-down");
            activity.connected = false;
            check(activity.listener(legacy(184,false,431)), "disconnected-up-result");
            check(activity.forwarded == 0 && activity.nativeKeys.toString().equals("[184:0:true]"), "disconnected-up-leaked");
        });
        scenario("direct-original-handler-false-return-preserved", () -> {
            setup(false); activity.handlerAccept = false; KeyEvent event = legacy(183,true,440);
            check(!activity.listener(event), "handler-false-return-changed");
            check(activity.forwarded == 1 && activity.forwardedEvents.get(0) == event, "handler-false-object-changed");
        });
        scenario("direct-listener-extra-key-side-effect-kept-once", () -> {
            setup(true); activity.useTermuxEKBarBehaviour = true; pair(true,183);
            check(activity.extraKeysUnset == 2, "listener-extra-key-side-effect-changed");
        });
        System.out.println("RESULT " + passed + " pass " + failed + " fail");
        if (failed != 0) System.exit(1);
    }
}
