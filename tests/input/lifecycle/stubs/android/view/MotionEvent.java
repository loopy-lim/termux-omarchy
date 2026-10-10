package android.view;
/** HOST STUB: validates fixture ID range/distinctness/action shape; no native event converter. */
public final class MotionEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,ACTION_POINTER_DOWN=5,
 ACTION_POINTER_UP=6,ACTION_HOVER_MOVE=7,ACTION_SCROLL=8,ACTION_HOVER_EXIT=10,ACTION_BUTTON_PRESS=11,ACTION_BUTTON_RELEASE=12;
 public static final int TOOL_TYPE_UNKNOWN=0,TOOL_TYPE_FINGER=1,TOOL_TYPE_STYLUS=2,TOOL_TYPE_MOUSE=3,TOOL_TYPE_ERASER=4;
 public static final int BUTTON_PRIMARY=1,BUTTON_SECONDARY=2,BUTTON_TERTIARY=4,AXIS_VSCROLL=9,AXIS_HSCROLL=10;
 private final int action,index,source,tool,device;private final int[] ids;private final float[] xs,ys;
 public MotionEvent(int action,int index,int source,int tool,int device,int[] ids,float[] xs,float[] ys){
  if(ids==null||xs==null||ys==null||ids.length==0||ids.length>32||ids.length!=xs.length||ids.length!=ys.length)
   throw new IllegalArgumentException("fixture pointer-array shape");
  boolean[] seen=new boolean[32];for(int id:ids){
   if(id<0||id>31||seen[id])throw new IllegalArgumentException("fixture pointer ID range/distinctness");seen[id]=true;}
  boolean pointerAction=action==ACTION_POINTER_DOWN||action==ACTION_POINTER_UP;
  if(index<0||index>=ids.length||(!pointerAction&&index!=0)||(pointerAction&&ids.length<2)||
    ((action==ACTION_DOWN||action==ACTION_UP)&&ids.length!=1))throw new IllegalArgumentException("fixture action/index shape");
  this.action=action;this.index=index;this.source=source;this.tool=tool;this.device=device;
  this.ids=ids.clone();this.xs=xs.clone();this.ys=ys.clone();}
 public int getAction(){return action|(index<<8);} public int getActionMasked(){return action;}
 public int getActionIndex(){return index;} public int getSource(){return source;} public int getDeviceId(){return device;}
 public int getMetaState(){return 0;} public int getButtonState(){return 0;} public int getPointerCount(){return ids.length;}
 public int getPointerId(int index){return ids[index];} public int getToolType(int index){int ignored=ids[index];return tool;}
 public float getX(){return getX(0);} public float getY(){return getY(0);}
 public float getX(int index){return xs[index];} public float getY(int index){return ys[index];}
 public float getAxisValue(int axis){return 0;} public boolean isFromSource(int value){return (source&value)==value;}
 public void offsetLocation(float x,float y){for(int i=0;i<xs.length;i++){xs[i]+=x;ys[i]+=y;}}
}
