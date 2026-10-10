package com.termux.x11.input;
/** HOST STUB: identity render transform only. */ public final class RenderData {
 public final android.graphics.PointF scale=new android.graphics.PointF(1,1);
 public int screenWidth=1920,screenHeight=1280;private final android.graphics.PointF cursor=new android.graphics.PointF();
 public android.graphics.PointF getCursorPosition(){return cursor;} public void mapScreenPoint(float x,float y,float[] out){out[0]=x;out[1]=y;}
 public boolean setCursorPosition(float x,float y){boolean changed=cursor.x!=x||cursor.y!=y;cursor.set(x,y);return changed;}
}
