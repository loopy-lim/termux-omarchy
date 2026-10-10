import com.android.tools.smali.baksmali.Adaptors.ClassDefinition;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.baksmali.formatter.BaksmaliWriter;
import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.iface.*;
import com.android.tools.smali.dexlib2.iface.instruction.*;
import com.android.tools.smali.dexlib2.iface.reference.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Real packaged invocation seams plus exact decoded preservation, not stub behavior. */
public final class DexDirectHandoffTest {
 static final String OWNER="Lcom/termux/x11/utils/KeyInterceptor;", MAIN="Lcom/termux/x11/MainActivity;";
 static final String INPUT="Lcom/termux/x11/input/TouchInputHandler;", KEY="Landroid/view/KeyEvent;";
 static final String HELPER="Lcom/termux/x11/utils/KeyBridgeHandoff;";
 static final String OLD_ACCESS=MAIN+"->handleKey("+KEY+")Z", NEW_ACCESS=HELPER+"->handleKey("+MAIN+KEY+")Z";
 static final String OLD_DIRECT=INPUT+"->sendKeyEvent("+KEY+")Z", NEW_DIRECT=HELPER+"->sendKeyEvent("+MAIN+INPUT+KEY+")Z";
 static void check(boolean ok,String why){if(!ok)throw new AssertionError(why);}
 static Map<String,ClassDef> classes(DexFile d){Map<String,ClassDef>r=new HashMap<>();for(ClassDef c:d.getClasses())check(r.put(c.getType(),c)==null,"duplicate-type");return r;}
 static String text(ClassDef c)throws Exception{BaksmaliOptions o=new BaksmaliOptions();o.apiLevel=28;o.sequentialLabels=true;o.accessorComments=false;StringWriter s=new StringWriter();BaksmaliWriter w=new BaksmaliWriter(s);ClassDefinition d=new ClassDefinition(o,c);d.writeTo(w);w.close();check(!d.hadValidationErrors(),"decoded-validation");return s.toString();}
 static Method method(ClassDef c,String name,List<String>params){check(c!=null,"class-missing");Method found=null;for(Method m:c.getMethods())if(m.getName().equals(name)&&m.getParameterTypes().equals(params)){check(found==null,"ambiguous-method");found=m;}check(found!=null&&found.getImplementation()!=null,"method-missing-"+name);return found;}
 static Method access(ClassDef c){return method(c,"onKeyEvent",List.of(KEY));}
 static Method direct(ClassDef c){return method(c,"lambda$onCreate$4",List.of("Landroid/view/View;","I",KEY));}
 static List<Instruction> code(Method m){List<Instruction>r=new ArrayList<>();m.getImplementation().getInstructions().forEach(r::add);return r;}
 static String ref(Instruction i){return i instanceof ReferenceInstruction?((ReferenceInstruction)i).getReference().toString():"";}
 static int[] regs(FiveRegisterInstruction q){return new int[]{q.getRegisterC(),q.getRegisterD(),q.getRegisterE(),q.getRegisterF(),q.getRegisterG()};}
 static Instruction uniqueCall(Method m,String oldRef,String newRef){Instruction found=null;for(Instruction i:code(m)){check(!ref(i).equals(oldRef),"baseline-direct-call-still-present");if(ref(i).equals(newRef)){check(found==null,"duplicate-hook");found=i;}}check(found!=null,"packaged-hook-missing");return found;}
 static void seam(DexFile d){
  Map<String,ClassDef>c=classes(d);check(c.containsKey(HELPER),"packaged-helper-missing");
  Instruction a=uniqueCall(access(c.get(OWNER)),OLD_ACCESS,NEW_ACCESS), b=uniqueCall(direct(c.get(MAIN)),OLD_DIRECT,NEW_DIRECT);
  check(a.getOpcode()==Opcode.INVOKE_STATIC&&((FiveRegisterInstruction)a).getRegisterCount()==2,"access-static-two-args");
  check(b.getOpcode()==Opcode.INVOKE_STATIC&&((FiveRegisterInstruction)b).getRegisterCount()==3,"direct-static-three-args");
  Method leaf=method(c.get(HELPER),"sendKeyEvent",List.of(MAIN,INPUT,KEY));check((leaf.getAccessFlags()&8)!=0,"leaf-static");
  boolean originalFallback=false;for(Instruction i:code(leaf)){
   check(!ref(i).equals(OLD_ACCESS)&&!ref(i).equals(NEW_ACCESS),"direct-leaf-recurses-through-activity");
   if(ref(i).equals(OLD_DIRECT))originalFallback=true;
  }
  check(originalFallback,"direct-original-fallback-missing");
  System.out.println("PASS both real packaged entry seams; direct listener leaf does not recurse through Activity");
 }
 static String expectedText(String before,String oldLine,String newLine){check(before.indexOf(oldLine)>=0&&before.indexOf(oldLine)==before.lastIndexOf(oldLine),"exact-decoded-call-count");return before.replace(oldLine,newLine);}
 static void widths(Method before,Method after,boolean direct){
  List<Instruction>b=code(before),a=code(after);check(b.size()==a.size(),"instruction-count");check(before.getImplementation().getRegisterCount()==after.getImplementation().getRegisterCount(),"register-count");int changed=0;
  for(int i=0;i<b.size();i++){
   Instruction x=b.get(i),y=a.get(i);check(x.getCodeUnits()==y.getCodeUnits(),"instruction-width-"+i);
   if(ref(x).equals(direct?OLD_DIRECT:OLD_ACCESS)){
    check(x.getOpcode()==Opcode.INVOKE_VIRTUAL&&y.getOpcode()==Opcode.INVOKE_STATIC,"replacement-opcodes");
    FiveRegisterInstruction p=(FiveRegisterInstruction)x,q=(FiveRegisterInstruction)y;int[]pr=regs(p),qr=regs(q);
    check(p.getRegisterCount()==2&&q.getRegisterCount()==(direct?3:2),"replacement-argument-count");
    if(direct){int self=before.getImplementation().getRegisterCount()-4;check(self==3&&pr[0]==1&&pr[1]==6&&qr[0]==self&&qr[1]==pr[0]&&qr[2]==pr[1],"direct-activity-handler-event-registers");}
    else check(Arrays.equals(pr,qr),"access-arguments-identical");
    changed++;
   }
  }
  check(changed==1,"exact-one-call-per-method");
 }
 public static void main(String[]args)throws Exception{
  check(args.length==2||args.length==4,"arguments");DexFile after=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));seam(after);if(args[0].equals("--seam-only"))return;
  DexFile before=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28)),helper=DexFileFactory.loadDexFile(new File(args[2]),Opcodes.forApi(28));
  Map<String,ClassDef>b=classes(before),a=classes(after),h=classes(helper);Set<String>expected=new HashSet<>(b.keySet());check(Collections.disjoint(expected,h.keySet()),"helpers-new-only");expected.addAll(h.keySet());check(expected.equals(a.keySet()),"only-helper-family-added");
  int unchanged=0;for(String type:b.keySet()){
   String x=text(b.get(type)),y=text(a.get(type));
   if(type.equals(OWNER)){
    check(expectedText(x,"invoke-virtual {v1, p1}, "+OLD_ACCESS,"invoke-static {v1, p1}, "+NEW_ACCESS).equals(y),"access-class-only-one-call-changed");
   }else if(type.equals(MAIN)){
    check(expectedText(x,"invoke-virtual {v1, p3}, "+OLD_DIRECT,"invoke-static {p0, v1, p3}, "+NEW_DIRECT).equals(y),"activity-class-only-listener-call-changed");
   }else{check(x.equals(y),"unrelated-class-changed-"+type);unchanged++;}
   if(type.equals(OWNER)||type.equals(MAIN)){String name=type.equals(OWNER)?"KeyInterceptor":"MainActivity";Files.writeString(Path.of(args[3]).resolve(name+"-before.smali"),x);Files.writeString(Path.of(args[3]).resolve(name+"-after.smali"),y);}
  }
  for(String type:h.keySet()){
   check(type.equals(HELPER)||type.startsWith(HELPER.substring(0,HELPER.length()-1)+"$"),"helper-family-only");check(text(h.get(type)).equals(text(a.get(type))),"compiled-helper-equality-"+type);
   for(Method m:h.get(type).getMethods())if(m.getImplementation()!=null)for(Instruction i:code(m)){
    if(!(i instanceof ReferenceInstruction)||!(((ReferenceInstruction)i).getReference() instanceof MethodReference))continue;MethodReference target=(MethodReference)((ReferenceInstruction)i).getReference();
    if(!Set.of(MAIN,"Lcom/termux/x11/LorieView;",INPUT).contains(target.getDefiningClass()))continue;
    Method actual=null;for(Method candidate:b.get(target.getDefiningClass()).getMethods())if(candidate.toString().equals(target.toString()))actual=candidate;
    if(actual==null){check(target.getDefiningClass().equals(MAIN)&&Set.of("getApplicationContext","getContentResolver","getFilesDir","getWindow","hasWindowFocus").contains(target.getName()),"actual-app-method-missing-"+target);continue;}
    check((b.get(target.getDefiningClass()).getAccessFlags()&1)!=0&&(actual.getAccessFlags()&1)!=0,"actual-app-api-public-"+target);
    check(((actual.getAccessFlags()&8)!=0)==(i.getOpcode()==Opcode.INVOKE_STATIC||i.getOpcode()==Opcode.INVOKE_STATIC_RANGE),"actual-method-static-parity-"+target);
   }
  }
  widths(access(b.get(OWNER)),access(a.get(OWNER)),false);widths(direct(b.get(MAIN)),direct(a.get(MAIN)),true);
  System.out.println("PASS "+unchanged+" existing classes decoded-identical; two classes differ only by exact same-width calls; "+h.size()+" compiled helper classes match; register/debug/try and all other methods retained");
 }
}
