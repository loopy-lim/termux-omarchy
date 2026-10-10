import com.termux.x11.MainActivity;
import com.termux.x11.utils.KeyInterceptor;
import android.view.*;import android.provider.Settings;import android.content.ContentResolver;
import android.hardware.input.InputManager;import java.nio.file.*;
public class HandoffReplay {
 static int pass,fail;static MainActivity a;static KeyInterceptor s;
 static final String SHA="628cc8736c1c09d0be7035f7e4a1aa8247984e3f1911ee9a1fc81d1e9e25ff5c\n";
 static void check(boolean b,String m){if(!b)throw new AssertionError(m);}
 static void setup(boolean opt)throws Exception{a=new MainActivity();a.files=Files.createTempDirectory("handoff-host-").toFile();MainActivity.focused=a;s=new KeyInterceptor();new InputDevice(1,false);new InputDevice(2,false);new InputDevice(-1,true);Settings.Secure.services="dev.loopy.keybridge/dev.loopy.keybridge.RemapService";ContentResolver.changed();if(opt)Files.writeString(a.files.toPath().resolve("loopy-keybridge-handoff.opt-in"),SHA);}
 static void key(int c,boolean d,int id,int scan,long t,int flags){check(s.onKeyEvent(new KeyEvent(c,d?0:1,id,scan,flags,t)),"not-consumed");}
 static void caps(boolean d,long t){key(115,d,1,58,t,0);}
 static void scenario(String n,Test t){try{t.run();pass++;System.out.println("PASS "+n);}catch(Throwable e){fail++;System.out.println("FAIL "+n+" "+e.getMessage());}finally{try{Files.deleteIfExists(a.files.toPath().resolve("loopy-keybridge-handoff.opt-in"));Files.delete(a.files.toPath());}catch(Exception e){throw new RuntimeException(e);}}}
 interface Test{void run()throws Exception;}
 public static void main(String[]args)throws Exception{
  scenario("default-off-preserves-raw",()->{setup(false);caps(true,1);key(36,true,1,35,2,0);check(a.forwarded==2,"raw-default");});
  scenario("fixed-caps-115-h-pair",()->{setup(true);caps(true,10);key(36,true,1,35,11,0);key(36,false,1,35,11,0);caps(false,10);check(a.forwarded==0,"raw-caps-leaked");});
  scenario("native-caps-f12-scan58",()->{setup(true);key(142,true,1,58,20,0);key(40,true,1,38,21,0);key(40,false,1,38,21,0);key(142,false,1,58,20,0);check(a.forwarded==0,"raw-native-caps-leaked");});
  scenario("device-isolation",()->{setup(true);caps(true,30);key(36,true,2,35,31,0);key(36,true,1,35,32,0);check(a.forwarded==1,"device-caps-crossed");});
  scenario("virtual-arrow-preserved",()->{setup(true);caps(true,40);key(21,true,-1,0,41,2);check(a.forwarded==1,"virtual-not-forwarded");});
  scenario("virtual-legacy-f13-f14",()->{setup(true);for(int c:new int[]{183,184}){key(c,true,-1,0,c,2);key(c,false,-1,0,c,2);}check(a.forwarded==0&&a.nativeKeys.toString().equals("[183:0:true, 183:0:false, 184:0:true, 184:0:false]"),"legacy-native-missing");});
  scenario("physical-color-preserved",()->{setup(true);key(183,true,1,0,50,0);check(a.forwarded==1&&a.nativeKeys.isEmpty(),"physical-color-remapped");});
  scenario("virtual-without-softflag-preserved",()->{setup(true);key(183,true,-1,0,60,0);check(a.forwarded==1&&a.nativeKeys.isEmpty(),"unmarked-virtual-remapped");});
  scenario("service-off-preserves-raw",()->{setup(true);Settings.Secure.services="com.termux.x11/com.termux.x11.utils.KeyInterceptor";ContentResolver.changed();caps(true,70);key(36,true,1,35,71,0);check(a.forwarded==2,"disabled-service-gated");});
  scenario("service-change-drains-owned-up",()->{setup(true);caps(true,80);key(36,true,1,35,81,0);Settings.Secure.services="";ContentResolver.changed();Settings.Secure.services="dev.loopy.keybridge/dev.loopy.keybridge.RemapService";ContentResolver.changed();key(36,false,1,35,81,0);key(38,true,1,36,82,0);caps(false,80);check(a.forwarded==1,"service-boundary-state");});
  scenario("focus-change-drains-owned-up",()->{setup(true);caps(true,90);key(36,true,1,35,91,0);a.getWindow().getDecorView().getViewTreeObserver().focus(false);a.getWindow().getDecorView().getViewTreeObserver().focus(true);key(36,false,1,35,91,0);key(38,true,1,36,92,0);caps(false,90);check(a.forwarded==1,"focus-boundary-state");});
  scenario("device-removal-clears-caps",()->{setup(true);caps(true,100);InputManager.INSTANCE.removed(1);key(38,true,1,36,101,0);caps(false,100);check(a.forwarded==1,"device-boundary-state");});
  scenario("pre-caps-owned-key-up-preserved",()->{setup(true);key(36,true,1,35,110,0);caps(true,111);key(36,false,1,35,110,0);check(a.forwarded==2,"pre-caps-up-swallowed");});
  scenario("unmapped-caps-key-preserved",()->{setup(true);caps(true,120);key(42,true,1,49,121,0);check(a.forwarded==1,"unmapped-swallowed");});
  scenario("all-fixed-layer-keys-and-shift-directions",()->{setup(true);caps(true,130);for(int c:new int[]{36,38,39,40,32,34,7,8,9,10,11,12,13,14,15,16,69,70}){key(c,true,1,0,130+c,0);key(c,false,1,0,130+c,0);}for(int c:new int[]{36,38,39,40}){check(s.onKeyEvent(new KeyEvent(c,0,1,0,0,230+c,1,0)),"shift-down");check(s.onKeyEvent(new KeyEvent(c,1,1,0,0,230+c,1,0)),"shift-up");}caps(false,130);check(a.forwarded==0,"fixed-layer-raw-leaked");});
  scenario("wrong-sha-opt-in-preserves-original",()->{setup(true);Files.writeString(a.files.toPath().resolve("loopy-keybridge-handoff.opt-in"),"0".repeat(64)+"\n");caps(true,300);key(36,true,1,0,301,0);check(a.forwarded==2,"wrong-pin-enabled");});
  scenario("malformed-opt-in-preserves-original",()->{setup(true);Files.writeString(a.files.toPath().resolve("loopy-keybridge-handoff.opt-in"),SHA+"extra");caps(true,310);key(36,true,1,0,311,0);check(a.forwarded==2,"malformed-pin-enabled");});
  scenario("default-off-legacy-preserved",()->{setup(false);key(183,true,-1,0,320,2);check(a.forwarded==1&&a.nativeKeys.isEmpty(),"default-legacy-remapped");});
  scenario("claimed-repeats-and-up-remain-owned",()->{setup(true);caps(true,330);key(36,true,1,35,331,0);check(s.onKeyEvent(new KeyEvent(36,0,1,35,0,331,0,2)),"repeat");key(36,false,1,35,331,0);caps(false,330);check(a.forwarded==0,"repeat-leaked");});
  scenario("mismatched-stale-up-preserves-current-caps",()->{setup(true);caps(true,340);caps(false,339);key(36,true,1,35,341,0);key(36,false,1,35,341,0);caps(false,340);check(a.forwarded==1,"stale-up-cleared-current-caps");});
  scenario("virtual-output-code-meta-and-object-identity",()->{setup(true);caps(true,350);int count=0;for(int c:new int[]{19,20,21,22,131,132,133,134,135,136,137,138,139,140,141,142,204}){KeyEvent e=new KeyEvent(c,0,-1,0,2,350+c,1,0);check(s.onKeyEvent(e),"output-down");check(a.forwardedEvents.get(count)==e&&a.forwardedEvents.get(count).getMetaState()==1,"output-mutated");count++;}check(a.forwarded==count&&a.nativeKeys.isEmpty(),"output-rewritten");});
  scenario("nonzero-virtual-scan-preserved",()->{setup(true);key(183,true,-1,13,380,2);check(a.forwarded==1&&a.nativeKeys.isEmpty(),"virtual-scan-remapped");});
  scenario("disconnected-legacy-preserves-original",()->{setup(true);a.connected=false;key(183,true,-1,0,390,2);check(a.forwarded==1&&a.nativeKeys.isEmpty(),"disconnected-remapped");});
  scenario("legacy-native-up-after-focus-loss",()->{setup(true);key(183,true,-1,0,400,2);a.focus=false;a.getWindow().getDecorView().getViewTreeObserver().focus(false);key(183,false,-1,0,400,2);check(a.forwarded==0&&a.nativeKeys.toString().equals("[183:0:true, 183:0:false]"),"native-focus-up-lost");});
  scenario("legacy-native-up-after-service-change",()->{setup(true);key(184,true,-1,0,410,2);Settings.Secure.services="";ContentResolver.changed();key(184,false,-1,0,410,2);check(a.forwarded==0&&a.nativeKeys.toString().equals("[184:0:true, 184:0:false]"),"native-service-up-lost");});
  scenario("legacy-native-up-after-opt-in-removal",()->{setup(true);key(183,true,-1,0,420,2);Files.delete(a.files.toPath().resolve("loopy-keybridge-handoff.opt-in"));key(183,false,-1,0,420,2);check(a.forwarded==0&&a.nativeKeys.toString().equals("[183:0:true, 183:0:false]"),"native-opt-in-up-lost");});
  scenario("unmatched-legacy-up-preserves-original",()->{setup(true);key(184,false,-1,0,430,2);check(a.forwarded==1&&a.nativeKeys.isEmpty(),"unmatched-native-up-rewritten");});
  scenario("installed-emitter-legacy-up-has-new-downTime",()->{setup(true);key(183,true,-1,0,440,2);a.focus=false;key(183,false,-1,0,441,2);check(a.forwarded==0&&a.nativeKeys.toString().equals("[183:0:true, 183:0:false]"),"installed-emitter-up-lost");});
  scenario("unmarked-virtual-up-does-not-steal-native-pair",()->{setup(true);key(184,true,-1,0,450,2);key(184,false,-1,0,451,0);key(184,false,-1,0,452,2);check(a.forwarded==1&&a.nativeKeys.toString().equals("[184:0:true, 184:0:false]"),"unmarked-up-stole-native-pair");});
  System.out.println("RESULT "+pass+" pass "+fail+" fail");if(fail>0)System.exit(1);
 }
}