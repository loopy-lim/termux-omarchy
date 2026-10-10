package android.view;
/** HOST STUB: capture state only, no Android InputReader or dispatch effects. */ public final class View {
 private boolean focused=true,captured=true; public boolean isFocused(){return focused;}
 public void requestFocus(){focused=true;} public void getLocationInWindow(int[] location){location[0]=location[1]=0;}
 public boolean hasPointerCapture(){return captured;} public void requestPointerCapture(){captured=true;}
 public void releasePointerCapture(){captured=false;} }
