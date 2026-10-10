package com.termux.x11.input;

import android.view.InputDevice;

/** Local canvas pinch belongs to the touchscreen, not external pointing devices. */
public final class LocalPinchZoom {
    private LocalPinchZoom() {}

    public static boolean shouldHandle(int source) {
        return (source & InputDevice.SOURCE_TOUCHSCREEN) == InputDevice.SOURCE_TOUCHSCREEN
                && (source & InputDevice.SOURCE_TOUCHPAD) != InputDevice.SOURCE_TOUCHPAD
                && (source & InputDevice.SOURCE_MOUSE) != InputDevice.SOURCE_MOUSE
                && (source & InputDevice.SOURCE_MOUSE_RELATIVE) != InputDevice.SOURCE_MOUSE_RELATIVE;
    }
}
