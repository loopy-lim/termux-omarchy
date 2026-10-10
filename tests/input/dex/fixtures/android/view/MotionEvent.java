package android.view;
public final class MotionEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,TOOL_TYPE_FINGER=1;
 private final int count,action,source,tool;
 public MotionEvent(int c,int a,int s,int t){count=c;action=a;source=s;tool=t;}
 public int getPointerCount(){return count;} public int getActionMasked(){return action&255;}
 public int getActionIndex(){return (action>>8)&255;} public int getSource(){return source;}
 public int getToolType(int i){if(i<0||i>=count)throw new IllegalArgumentException("fixture-index");return tool;}
}
