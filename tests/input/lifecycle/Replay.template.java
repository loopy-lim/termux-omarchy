package com.termux.x11.input;

import android.os.Build;
import android.os.Handler;
import android.graphics.PointF;
import android.view.GestureDetector;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import com.termux.x11.utils.SamsungDexUtils;
import java.util.function.BiConsumer;

/** Production methods are inserted verbatim; surrounding effects are explicit host fakes. */
public final class Replay {
    static final float EPSILON = .001f;
    static final class CapturedPointerTransformation {
        static final int AUTO=-1,NONE=0,COUNTER_CLOCKWISE=1,UPSIDE_DOWN=2,CLOCKWISE=3;
    }
    static final class MathUtils {
        static float clamp(float value,float minimum,float maximum){throw new AssertionError("non-trackpad clamp outside coverage");}
    }
    static final class FakeActivity extends android.content.Context {
        final View view=new View();
        View getLorieView(){return view;}
    }
    static final class UnsupportedRoute {
        int calls;
        boolean onTouch(View view,MotionEvent event){calls++;return false;}
        boolean onTouch(MotionEvent event){calls++;return false;}
    }
    final FakeActivity mActivity;
    final InputEventSender mInjector;
    final RenderData mRenderData=new RenderData();
    final Replay mTouchpadHandler;
    final GestureListener listener=new GestureListener();
    final GestureDetector mScroller;
    final SwipeDetector mSwipePinchDetector;
    final TapGestureDetector mTapDetector;
    final UnsupportedRoute mHMListener=new UnsupportedRoute(),mStylusListener=new UnsupportedRoute(),mDexListener=new UnsupportedRoute();
    final UnsupportedZoom mZoomer=new UnsupportedZoom();
    static final class UnsupportedZoom {int calls;void onTouchEvent(MotionEvent event){calls++;}}
    InputStrategyInterface mInputStrategy;
    boolean ignoreGamepadEvents,mSuppressCursorMovement,mSwipeCompleted,mIsDragging,keyIntercepting=true;
    float mTotalMotionY,mSwipeThreshold=40;
    int capturedPointerTransformation=0,mDisplayRotation=0,savedBS,currentBS,swipeActions;
    final int[][] buttons={{MotionEvent.BUTTON_PRIMARY,InputStub.BUTTON_LEFT},
        {MotionEvent.BUTTON_TERTIARY,InputStub.BUTTON_MIDDLE},{MotionEvent.BUTTON_SECONDARY,InputStub.BUTTON_RIGHT}};
    final BiConsumer<Integer,Boolean> swipeDownAction=(key,down)->swipeActions++;
    final BiConsumer<Integer,Boolean> swipeUpAction=(key,down)->swipeActions++;
    final float[] mappedPoint=new float[2];

    Replay(){this(new FakeActivity(),new InputEventSender(),false);}
    Replay(FakeActivity activity,InputEventSender injector,boolean nested){
        mActivity=activity;mInjector=injector;mInputStrategy=new InputStrategyInterface.TrackpadInputStrategy(injector);
        mScroller=new GestureDetector(activity,listener,null,false);mScroller.setIsLongpressEnabled(false);
        mSwipePinchDetector=new SwipeDetector(activity);mTapDetector=new TapGestureDetector(activity,listener);
        mTouchpadHandler=nested?null:new Replay(activity,injector,true);
    }
    boolean isMouseButtonChanged(int mask){return (savedBS&mask)!=(currentBS&mask);}
    boolean mouseButtonDown(int mask){return (currentBS&mask)!=0;}
    void moveCursorToScreenPoint(float x,float y){throw new AssertionError("non-trackpad absolute route outside coverage");}

    /*__OUTER_METHODS__*/

    final class GestureListener extends GestureDetector.SimpleOnGestureListener implements TapGestureDetector.OnTapListener {
        final Handler mGestureListenerHandler=new Handler(message->{mInputStrategy.onTap(message.what);return true;});
        /*__GESTURE_METHODS__*/
    }

    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static MotionEvent event(int action,int index,int[] ids,float[] xs,float[] ys){
        return new MotionEvent(action,index,InputDevice.SOURCE_TOUCHPAD,MotionEvent.TOOL_TYPE_FINGER,96,ids,xs,ys);
    }
    static void rejectShape(int action,int index,int[] ids){
        try {event(action,index,ids,new float[ids.length],new float[ids.length]);}
        catch(IllegalArgumentException expected){return;}
        throw new AssertionError("invalid fixture shape accepted");
    }
    static void validateFixtureShape(){
        rejectShape(MotionEvent.ACTION_MOVE,0,new int[]{-1});
        rejectShape(MotionEvent.ACTION_MOVE,0,new int[]{32});
        rejectShape(MotionEvent.ACTION_MOVE,0,new int[]{7,7});
        rejectShape(MotionEvent.ACTION_POINTER_DOWN,-1,new int[]{0,31});
        rejectShape(MotionEvent.ACTION_POINTER_UP,2,new int[]{0,31});
        rejectShape(MotionEvent.ACTION_MOVE,1,new int[]{0,31});
        rejectShape(MotionEvent.ACTION_DOWN,0,new int[]{0,31});
        rejectShape(MotionEvent.ACTION_UP,0,new int[]{0,31});
        rejectShape(MotionEvent.ACTION_POINTER_DOWN,0,new int[]{7});
        rejectShape(MotionEvent.ACTION_POINTER_UP,0,new int[]{7});
        rejectShape(MotionEvent.ACTION_MOVE,0,new int[]{});
        int[] tooMany=new int[33];for(int i=0;i<tooMany.length;i++)tooMany[i]=i;
        rejectShape(MotionEvent.ACTION_MOVE,0,tooMany);
        event(MotionEvent.ACTION_POINTER_DOWN,1,new int[]{0,31},new float[2],new float[2]);
        event(MotionEvent.ACTION_POINTER_UP,0,new int[]{0,31},new float[2],new float[2]);
        int[] maximum=new int[32];for(int i=0;i<maximum.length;i++)maximum[i]=i;
        event(MotionEvent.ACTION_MOVE,0,maximum,new float[32],new float[32]);
        System.out.println("FIXTURE_VALIDATION {\"invalidShapesRejected\":12,\"validBoundaryShapesAccepted\":3,\"pointerIdMinimum\":0,\"pointerIdMaximum\":31}");
    }
    static boolean send(Replay h,int action,int index,int[] ids,float[] xs,float[] ys){
        return dispatch(h,event(action,index,ids,xs,ys));
    }
    static boolean dispatch(Replay h,MotionEvent event){
        int[] ids=new int[event.getPointerCount()];for(int i=0;i<ids.length;i++)ids[i]=event.getPointerId(i);
        int moves=h.mInjector.moves,wheels=h.mInjector.wheels;
        boolean result=h.handleTouchEvent(h.mActivity.view,h.mActivity.view,event);Replay n=h.mTouchpadHandler;
        System.out.println("TRACE {\"case\":\""+currentCase+"\",\"action\":"+event.getActionMasked()+
            ",\"index\":"+event.getActionIndex()+",\"pointerIds\":"+java.util.Arrays.toString(ids)+
            ",\"pointerCount\":"+event.getPointerCount()+",\"actionTool\":"+event.getToolType(event.getActionIndex())+
            ",\"consumed\":"+result+",\"moveDelta\":"+(h.mInjector.moves-moves)+",\"wheelDelta\":"+(h.mInjector.wheels-wheels)+
            ",\"nestedSuppress\":"+n.mSuppressCursorMovement+",\"nestedSwipeCompleted\":"+n.mSwipeCompleted+
            ",\"nestedStillDownStub\":"+n.mScroller.stillDown+",\"nestedPreviousUpPresentStub\":"+n.mScroller.previousUpPresent+
            ",\"swipeActions\":"+n.swipeActions+"}");
        return result;
    }
    static void one(Replay h,int action,int id,float x,float y){
        check(send(h,action,0,new int[]{id},new float[]{x},new float[]{y}),"one-pointer route consumed");
    }
    static void normalTwoToOne(boolean liftIndexZero){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;
        one(h,MotionEvent.ACTION_DOWN,7,0,0);one(h,MotionEvent.ACTION_MOVE,7,10,0);
        send(h,MotionEvent.ACTION_POINTER_DOWN,1,new int[]{7,21},new float[]{10,30},new float[]{0,0});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{7,21},new float[]{10,30},new float[]{10,10});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{7,21},new float[]{10,30},new float[]{30,30});
        check(h.mInjector.wheels==1&&n.mSuppressCursorMovement,"real swipe detector reached two-finger wheel route");
        int before=h.mInjector.moves;int upIndex=liftIndexZero?0:1;int remaining=liftIndexZero?21:7;float x=liftIndexZero?30:10;
        send(h,MotionEvent.ACTION_POINTER_UP,upIndex,new int[]{7,21},new float[]{10,30},new float[]{30,30});
        check(!n.mSwipePinchDetector.isSwiping(),"actual SwipeDetector resets on POINTER_UP");
        one(h,MotionEvent.ACTION_MOVE,remaining,x,50);
        check(h.mInjector.moves==before+1&&!n.mSuppressCursorMovement,"relative cursor resumes after either index lifts");
        one(h,MotionEvent.ACTION_UP,remaining,x,50);
        check(!n.mScroller.stillDown&&n.mScroller.previousUpPresent,"final UP reaches nested gesture detector stub");
        check(!n.mSwipeCompleted&&n.swipeActions==0,"two-finger gesture does not trigger three-finger action");
        check(h.mInjector.clicks==0&&n.mZoomer.calls==0,"no tap click or pinch injected");
        check(h.mHMListener.calls==0&&h.mDexListener.calls==0&&h.mStylusListener.calls==0,"physical touchpad takes exact nested route");
    }
    static void normalThreeFinger(){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;
        one(h,MotionEvent.ACTION_DOWN,7,0,0);
        send(h,MotionEvent.ACTION_POINTER_DOWN,1,new int[]{7,21},new float[]{0,20},new float[]{0,0});
        send(h,MotionEvent.ACTION_POINTER_DOWN,2,new int[]{7,21,25},new float[]{0,20,40},new float[]{0,0,0});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{7,21,25},new float[]{0,20,40},new float[]{60,60,60});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{7,21,25},new float[]{0,20,40},new float[]{90,90,90});
        check(n.swipeActions==1&&n.mSwipeCompleted&&n.mSuppressCursorMovement,"normal three-finger action is preserved once");
        send(h,MotionEvent.ACTION_POINTER_UP,2,new int[]{7,21,25},new float[]{0,20,40},new float[]{90,90,90});
        send(h,MotionEvent.ACTION_POINTER_UP,1,new int[]{7,21},new float[]{0,20},new float[]{90,90});
        int before=h.mInjector.moves;one(h,MotionEvent.ACTION_MOVE,7,0,110);
        check(h.mInjector.moves==before+1&&!n.mSuppressCursorMovement&&n.mSwipeCompleted,"three-to-one resumes without replaying swipe");
        one(h,MotionEvent.ACTION_UP,7,0,110);
        check(!n.mScroller.stillDown&&n.swipeActions==1,"three-finger lifecycle terminates");
    }
    static Replay staleContact(){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;
        // id0 is an adversarial retained contact, never receiving its final UP.
        one(h,MotionEvent.ACTION_DOWN,0,0,0);
        send(h,MotionEvent.ACTION_POINTER_DOWN,1,new int[]{0,7},new float[]{0,20},new float[]{0,0});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{0,7},new float[]{0,20},new float[]{0,20});
        check(h.mInjector.moves==0&&h.mInjector.wheels==0,"one real finger plus stationary retained contact is blocked");
        send(h,MotionEvent.ACTION_POINTER_DOWN,2,new int[]{0,7,21},new float[]{0,20,40},new float[]{0,20,20});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{0,7,21},new float[]{0,20,40},new float[]{0,100,100});
        check(n.mSwipeCompleted&&n.swipeActions==1,"two real contacts plus retained ID reach actual onSwipe");
        send(h,MotionEvent.ACTION_POINTER_UP,2,new int[]{0,7,21},new float[]{0,20,40},new float[]{0,100,100});
        send(h,MotionEvent.ACTION_POINTER_UP,1,new int[]{0,7},new float[]{0,20},new float[]{0,100});
        send(h,MotionEvent.ACTION_POINTER_DOWN,1,new int[]{0,25},new float[]{0,20},new float[]{0,0});
        int before=h.mInjector.moves;
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{0,25},new float[]{0,20},new float[]{0,30});
        check(h.mInjector.moves==before&&n.mSuppressCursorMovement&&n.mSwipeCompleted&&n.mScroller.stillDown&&!n.mScroller.previousUpPresent,
            "reproduce exact post-scroll field tuple and failed real-one-finger movement contract");
        return h;
    }
    static void captureLifecycle(){
        Replay h=staleContact();Replay n=h.mTouchpadHandler;
        h.setCapturingEnabled(false);h.setCapturingEnabled(true);
        check(n.mSuppressCursorMovement&&n.mSwipeCompleted&&n.mScroller.stillDown,"capture setter itself does not reset Java state");
        send(h,MotionEvent.ACTION_CANCEL,0,new int[]{0,25},new float[]{0,20},new float[]{0,30});
        check(!n.mScroller.stillDown&&!n.mSwipePinchDetector.isSwiping(),"cancel terminates detector state");
        check(!n.mSuppressCursorMovement&&!n.mSwipeCompleted&&!n.mIsDragging,"physical CANCEL clears ended gesture latches");
        one(h,MotionEvent.ACTION_DOWN,29,0,0);int before=h.mInjector.moves;
        one(h,MotionEvent.ACTION_MOVE,29,0,20);one(h,MotionEvent.ACTION_UP,29,0,20);
        check(h.mInjector.moves==before+1&&!n.mSuppressCursorMovement&&!n.mSwipeCompleted&&!n.mScroller.stillDown,
            "fresh one-contact stream recovers through actual DOWN/MOVE/UP routing");
    }
    static void unknownToolUp(){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;one(h,MotionEvent.ACTION_DOWN,7,0,0);
        MotionEvent bad=new MotionEvent(MotionEvent.ACTION_UP,0,InputDevice.SOURCE_TOUCHPAD,MotionEvent.TOOL_TYPE_UNKNOWN,96,
            new int[]{7},new float[]{0},new float[]{0});
        check(!dispatch(h,bad)&&n.mScroller.stillDown,
            "UNKNOWN tool final UP is not routed into nested detector (adversarial classification)");
        one(h,MotionEvent.ACTION_DOWN,21,0,0);int before=h.mInjector.moves;
        one(h,MotionEvent.ACTION_MOVE,21,0,20);one(h,MotionEvent.ACTION_UP,21,0,20);
        check(h.mInjector.moves==before+1&&!n.mScroller.stillDown,"new valid DOWN recovers even after omitted final UP");
    }
    static void rawSingleMoveWithoutCallback(){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;
        one(h,MotionEvent.ACTION_DOWN,7,0,0);
        send(h,MotionEvent.ACTION_POINTER_DOWN,1,new int[]{7,21},new float[]{0,20},new float[]{0,0});
        send(h,MotionEvent.ACTION_POINTER_DOWN,2,new int[]{7,21,25},new float[]{0,20,40},new float[]{0,0,0});
        send(h,MotionEvent.ACTION_MOVE,0,new int[]{7,21,25},new float[]{0,20,40},new float[]{60,60,60});
        check(n.mSuppressCursorMovement&&n.mSwipeCompleted&&n.swipeActions==1,"real three-finger swipe seeds latches");
        send(h,MotionEvent.ACTION_POINTER_UP,2,new int[]{7,21,25},new float[]{0,20,40},new float[]{60,60,60});
        send(h,MotionEvent.ACTION_POINTER_UP,1,new int[]{7,21},new float[]{0,20},new float[]{60,60});
        n.mIsDragging=true;n.mScroller.declineScrollCallbacks=true;
        int moves=h.mInjector.moves,wheels=h.mInjector.wheels;
        one(h,MotionEvent.ACTION_MOVE,7,0,80);
        check(!n.mSuppressCursorMovement,"raw physical single MOVE clears suppression without onScroll callback");
        check(n.mSwipeCompleted&&n.swipeActions==1&&n.mIsDragging,"three-to-one preserves completed swipe and ongoing drag");
        check(h.mInjector.moves==moves&&h.mInjector.wheels==wheels,"raw reset does not fabricate cursor or wheel output");
    }
    static void terminalReset(int action){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;one(h,MotionEvent.ACTION_DOWN,7,0,0);
        n.mSuppressCursorMovement=true;n.mSwipeCompleted=true;n.mIsDragging=true;
        n.mScroller.terminalObserver=()->check(n.mSuppressCursorMovement&&n.mSwipeCompleted&&n.mIsDragging,
            "terminal detectors observe gesture latches before reset");
        int moves=h.mInjector.moves,wheels=h.mInjector.wheels;
        one(h,action,7,0,0);
        check(!n.mSuppressCursorMovement&&!n.mSwipeCompleted&&!n.mIsDragging,"final physical UP/CANCEL clears all gesture latches");
        check(!n.mScroller.stillDown,"terminal event still reaches gesture detector");
        check(h.mInjector.moves==moves&&h.mInjector.wheels==wheels,"terminal reset does not fabricate movement");
        check(h.mInjector.clicks==(action==MotionEvent.ACTION_UP?1:0),"real tap UP semantics remain, CANCEL does not click");
    }
    static void heldLeftButtonLifecycle(){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;n.mScroller.declineScrollCallbacks=true;
        one(h,MotionEvent.ACTION_DOWN,7,0,0);
        check(n.mInputStrategy.onPressAndHold(InputStub.BUTTON_LEFT,true),"real trackpad strategy accepts forced left hold");
        n.mIsDragging=true;n.mSuppressCursorMovement=true;n.mSwipeCompleted=true;
        check(h.mInjector.buttonDowns==1&&h.mInjector.buttonUps==0,"real strategy has emitted one down and no release");
        one(h,MotionEvent.ACTION_MOVE,7,20,20);
        check(!n.mSuppressCursorMovement&&n.mSwipeCompleted&&n.mIsDragging,"raw MOVE resumes suppression without ending swipe or drag");
        check(h.mInjector.buttonDowns==1&&h.mInjector.buttonUps==0,"raw MOVE does not release the held button");
        one(h,MotionEvent.ACTION_UP,7,20,20);
        check(h.mInjector.buttonDowns==1&&h.mInjector.buttonUps==1,"actual UP routing releases real held strategy button exactly once");
        check(!n.mSuppressCursorMovement&&!n.mSwipeCompleted&&!n.mIsDragging,"UP finishes local gesture latches");
        one(h,MotionEvent.ACTION_DOWN,21,0,0);
        one(h,MotionEvent.ACTION_MOVE,21,20,20);
        one(h,MotionEvent.ACTION_UP,21,20,20);
        check(h.mInjector.buttonDowns==1&&h.mInjector.buttonUps==1,"later valid gesture does not repeat previous held-button release");
        check(h.mInjector.downButtons.equals(java.util.List.of(InputStub.BUTTON_LEFT))&&
            h.mInjector.upButtons.equals(java.util.List.of(InputStub.BUTTON_LEFT)),"held-button down and release both preserve the LEFT identity");
        check(h.mInjector.clicks==0&&h.mInjector.moves==0&&h.mInjector.wheels==0,
            "declined onScroll plus moved tap produces no fabricated click, cursor or wheel output");
    }
    static void excludedLifecycle(int source,int tool,boolean otherStrategy){
        Replay h=new Replay();Replay n=h.mTouchpadHandler;
        if(otherStrategy)n.mInputStrategy=new InputStrategyInterface.SimulatedTouchInputStrategy(n.mRenderData,n.mInjector,n.mActivity);
        dispatch(h,new MotionEvent(MotionEvent.ACTION_DOWN,0,source,tool,96,new int[]{7},new float[]{0},new float[]{0}));
        h.mScroller.declineScrollCallbacks=n.mScroller.declineScrollCallbacks=true;
        h.mSuppressCursorMovement=n.mSuppressCursorMovement=true;
        h.mSwipeCompleted=n.mSwipeCompleted=true;h.mIsDragging=n.mIsDragging=true;
        dispatch(h,new MotionEvent(MotionEvent.ACTION_MOVE,0,source,tool,96,new int[]{7},new float[]{20},new float[]{20}));
        check(h.mSuppressCursorMovement&&n.mSuppressCursorMovement&&h.mSwipeCompleted&&n.mSwipeCompleted&&h.mIsDragging&&n.mIsDragging,
            "excluded MOVE leaves root/nested latches unchanged");
        dispatch(h,new MotionEvent(MotionEvent.ACTION_UP,0,source,tool,96,new int[]{7},new float[]{20},new float[]{20}));
        check(h.mSuppressCursorMovement&&n.mSuppressCursorMovement&&h.mSwipeCompleted&&n.mSwipeCompleted&&h.mIsDragging&&n.mIsDragging,
            "excluded final UP leaves root/nested latches unchanged");
        dispatch(h,new MotionEvent(MotionEvent.ACTION_CANCEL,0,source,tool,96,new int[]{7},new float[]{20},new float[]{20}));
        check(h.mSuppressCursorMovement&&n.mSuppressCursorMovement&&h.mSwipeCompleted&&n.mSwipeCompleted&&h.mIsDragging&&n.mIsDragging,
            "excluded CANCEL leaves root/nested latches unchanged");
    }
    static int passed,failed;static String currentCase;
    static void run(String name,Runnable body){currentCase=name;try{body.run();passed++;System.out.println("PASS "+name);}catch(Throwable error){failed++;System.out.println("FAIL "+name+": "+error);}}
    public static void main(String[] args){
        validateFixtureShape();
        run("normal-two-to-one-lift-index1",()->normalTwoToOne(false));
        run("normal-two-to-one-lift-index0",()->normalTwoToOne(true));
        run("normal-three-finger-swipe-preserved",Replay::normalThreeFinger);
        run("stale-ID-reproduces-current-failure",Replay::staleContact);
        run("capture-toggle-versus-cancel-and-fresh-DOWN",Replay::captureLifecycle);
        run("invalid-tool-UP-routing-and-valid-DOWN-recovery",Replay::unknownToolUp);
        run("raw-single-MOVE-without-onScroll-preserves-three-to-one",Replay::rawSingleMoveWithoutCallback);
        run("final-physical-UP-reset-after-detectors",()->terminalReset(MotionEvent.ACTION_UP));
        run("physical-CANCEL-reset-after-detectors",()->terminalReset(MotionEvent.ACTION_CANCEL));
        run("real-held-left-preserved-MOVE-released-once-UP",Replay::heldLeftButtonLifecycle);
        run("touchscreen-lifecycle-unchanged",()->excludedLifecycle(InputDevice.SOURCE_TOUCHSCREEN,MotionEvent.TOOL_TYPE_FINGER,false));
        run("mixed-touchscreen-touchpad-lifecycle-unchanged",()->excludedLifecycle(InputDevice.SOURCE_TOUCHPAD|InputDevice.SOURCE_TOUCHSCREEN,MotionEvent.TOOL_TYPE_FINGER,false));
        run("Dex-lifecycle-unchanged",()->excludedLifecycle(InputDevice.SOURCE_MOUSE,MotionEvent.TOOL_TYPE_FINGER,false));
        run("other-strategy-lifecycle-unchanged",()->excludedLifecycle(InputDevice.SOURCE_TOUCHPAD,MotionEvent.TOOL_TYPE_FINGER,true));
        run("hardware-mouse-lifecycle-unchanged",()->excludedLifecycle(InputDevice.SOURCE_MOUSE,MotionEvent.TOOL_TYPE_MOUSE,false));
        run("unknown-tool-touchpad-lifecycle-unchanged",()->excludedLifecycle(InputDevice.SOURCE_TOUCHPAD,MotionEvent.TOOL_TYPE_UNKNOWN,false));
        System.out.println("RESULT passed="+passed+" failed="+failed);
        if(failed!=0)throw new AssertionError("lifecycle replay assertions failed");
    }
}
