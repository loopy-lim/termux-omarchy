package android.view;
/** HOST STUB: fixed touch slop8; timing behavior is not modeled. */ public final class ViewConfiguration {
 public static ViewConfiguration get(android.content.Context context){return new ViewConfiguration();}
 public int getScaledTouchSlop(){return 8;} public int getScaledDoubleTapSlop(){return 100;}
 public static int getDoubleTapTimeout(){return 300;} public static int getLongPressTimeout(){return 500;}}
