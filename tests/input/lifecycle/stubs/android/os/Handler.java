package android.os;
/** HOST STUB: scheduled callbacks are NOT executed; long-press/double-tap timing is outside coverage. */
public class Handler {public interface Callback {boolean handleMessage(Message message);}
 public Handler(){} public Handler(Callback callback){}
 public void handleMessage(Message message){} public boolean sendEmptyMessageDelayed(int what,long delay){return true;}
 public void removeMessages(int what){} }
