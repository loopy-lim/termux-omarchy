package com.termux.x11.input;
/** HOST EFFECT SPY: records intended input, never injects into a device/server. */ public final class InputEventSender {
 public boolean pointerCapture=true,pauseKeyInterceptingWithEsc,dexMetaKeyCapture,scaleTouchpad,tapToMove;
 public float capturedPointerSpeedFactor=1;public int moves,wheels,clicks,buttonDowns,buttonUps;
 public final java.util.List<Integer> downButtons=new java.util.ArrayList<>(),upButtons=new java.util.ArrayList<>();
 public void sendCursorMove(float x,float y,boolean relative){if(!relative)throw new AssertionError("relative expected");moves++;}
 public void sendMouseWheelEvent(float x,float y){wheels++;} public void sendMouseClick(int button,boolean relative){clicks++;}
 public void sendMouseDown(int button,boolean relative){buttonDowns++;downButtons.add(button);}
 public void sendMouseUp(int button,boolean relative){buttonUps++;upButtons.add(button);}
 public void sendMouseEvent(android.graphics.PointF point,int button,boolean down,boolean relative){if(down)buttonDowns++;else buttonUps++;}
 public void releaseStuckModifiers(int meta){} public void syncLockKeysState(int meta){}
 public void sendTouchEvent(android.view.MotionEvent event,RenderData data){throw new AssertionError("direct touch outside fixture");}
}
