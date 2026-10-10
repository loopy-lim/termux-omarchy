package android.view;
/** HOST ANDROID FRAMEWORK STUB. Models focus centroid/lift index and DOWN/UP/CANCEL lifecycle ONLY.
 * This is NOT Android GestureDetector and does not validate its slop, velocity, timing, batching or dispatch. */
public final class GestureDetector {
 public static class SimpleOnGestureListener {
  public boolean onDown(MotionEvent event){return false;}
  public boolean onScroll(MotionEvent first,MotionEvent event,float x,float y){return false;}
 }
 public boolean stillDown,previousUpPresent,declineScrollCallbacks;public Runnable terminalObserver;
 private MotionEvent down;private float lastX,lastY;
 private final SimpleOnGestureListener listener;
 public GestureDetector(android.content.Context context,SimpleOnGestureListener listener,Object handler,boolean unused){this.listener=listener;}
 public void setIsLongpressEnabled(boolean enabled){if(enabled)throw new AssertionError("real constructor disables longpress");}
 public boolean onTouchEvent(MotionEvent event){
  int action=event.getActionMasked();int skip=action==MotionEvent.ACTION_POINTER_UP?event.getActionIndex():-1;
  float x=0,y=0;int count=0;for(int i=0;i<event.getPointerCount();i++){if(i==skip)continue;x+=event.getX(i);y+=event.getY(i);count++;}
  if(count>0){x/=count;y/=count;}
  switch(action){
   case MotionEvent.ACTION_DOWN:stillDown=true;down=event;lastX=x;lastY=y;return listener.onDown(event);
   case MotionEvent.ACTION_POINTER_DOWN:case MotionEvent.ACTION_POINTER_UP:lastX=x;lastY=y;return true;
   case MotionEvent.ACTION_MOVE:float dx=lastX-x,dy=lastY-y;lastX=x;lastY=y;
    return !declineScrollCallbacks&&stillDown&&(dx!=0||dy!=0)&&listener.onScroll(down,event,dx,dy);
   case MotionEvent.ACTION_UP:if(terminalObserver!=null)terminalObserver.run();stillDown=false;previousUpPresent=true;return true;
   case MotionEvent.ACTION_CANCEL:if(terminalObserver!=null)terminalObserver.run();stillDown=false;return true;
   default:return false;
  }
 }
}
