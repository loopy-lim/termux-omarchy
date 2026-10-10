package com.termux.x11.input;

import android.view.InputDevice;
import android.view.MotionEvent;

/** A physical touchpad can resume single-finger motion without a new ACTION_DOWN. */
public final class PhysicalTouchpadMotion {
    private PhysicalTouchpadMotion() {}

    public static boolean shouldResume(MotionEvent event) {
        if (event.getPointerCount() != 1 || event.getActionMasked() != MotionEvent.ACTION_MOVE)
            return false;
        int source = event.getSource();
        if ((source & InputDevice.SOURCE_TOUCHPAD) != InputDevice.SOURCE_TOUCHPAD
                || (source & InputDevice.SOURCE_TOUCHSCREEN) == InputDevice.SOURCE_TOUCHSCREEN)
            return false;
        return event.getToolType(0) == MotionEvent.TOOL_TYPE_FINGER;
    }

    /** Only a final physical touchpad UP or CANCEL ends the gesture latches. */
    public static boolean shouldFinish(MotionEvent event) {
        int action = event.getActionMasked();
        if (action != MotionEvent.ACTION_UP && action != MotionEvent.ACTION_CANCEL)
            return false;
        int source = event.getSource();
        if ((source & InputDevice.SOURCE_TOUCHPAD) != InputDevice.SOURCE_TOUCHPAD
                || (source & InputDevice.SOURCE_TOUCHSCREEN) == InputDevice.SOURCE_TOUCHSCREEN)
            return false;
        return event.getToolType(event.getActionIndex()) == MotionEvent.TOOL_TYPE_FINGER;
    }
}
