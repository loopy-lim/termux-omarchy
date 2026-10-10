import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.builder.*;
import com.android.tools.smali.dexlib2.builder.instruction.*;
import com.android.tools.smali.dexlib2.iface.*;
import com.android.tools.smali.dexlib2.iface.instruction.*;
import com.android.tools.smali.dexlib2.iface.reference.*;
import com.android.tools.smali.dexlib2.immutable.*;
import com.android.tools.smali.dexlib2.immutable.reference.*;
import com.android.tools.smali.dexlib2.writer.pool.DexPool;
import java.io.File;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Two same-width calls only; preserve every existing input method and native payload. */
public final class PatchHandoffDex {
 static final String OWNER="Lcom/termux/x11/utils/KeyInterceptor;", MAIN="Lcom/termux/x11/MainActivity;", HELPER="Lcom/termux/x11/utils/KeyBridgeHandoff;", HANDLER="Lcom/termux/x11/input/TouchInputHandler;", EVENT="Landroid/view/KeyEvent;";
 static void require(boolean b,String why){if(!b)throw new IllegalArgumentException(why);}
 static boolean call(Instruction i,String reference){
  if(!(i instanceof ReferenceInstruction))return false;
  Reference r=((ReferenceInstruction)i).getReference();
  return r instanceof MethodReference && r.toString().equals(reference);
 }
 static boolean accessMethod(Method m){return m.getName().equals("onKeyEvent")&&m.getParameterTypes().toString().equals("["+EVENT+"]")&&m.getReturnType().equals("Z");}
 static boolean listenerMethod(Method m){return m.getName().equals("lambda$onCreate$4")&&m.getParameterTypes().toString().equals("[Landroid/view/View;, I, "+EVENT+"]")&&m.getReturnType().equals("Z");}
 static Method patched(Method m,boolean listener){
  MutableMethodImplementation c=new MutableMethodImplementation(m.getImplementation());int changed=0;
  String reference=listener?HANDLER+"->sendKeyEvent("+EVENT+")Z":MAIN+"->handleKey("+EVENT+")Z";
  for(int i=0;i<c.getInstructions().size();i++){
   Instruction q=c.getInstructions().get(i);if(!call(q,reference))continue;
   require(q.getOpcode()==Opcode.INVOKE_VIRTUAL && q instanceof FiveRegisterInstruction,"call-format");
   FiveRegisterInstruction a=(FiveRegisterInstruction)q;require(a.getRegisterCount()==2,"call-arguments");
   BuilderInstruction replacement;
   if(listener){
    // Pinned instance lambda has p0=v3, handler=v1 and original event=p3=v6.
    require((m.getAccessFlags()&8)==0&&c.getRegisterCount()==7&&a.getRegisterC()==1&&a.getRegisterD()==6,"listener-register-layout");
    replacement=new BuilderInstruction35c(Opcode.INVOKE_STATIC,3,3,1,6,0,0,new ImmutableMethodReference(HELPER,"sendKeyEvent",List.of(MAIN,HANDLER,EVENT),"Z"));
   }else{
    replacement=new BuilderInstruction35c(Opcode.INVOKE_STATIC,2,a.getRegisterC(),a.getRegisterD(),a.getRegisterE(),a.getRegisterF(),a.getRegisterG(),new ImmutableMethodReference(HELPER,"handleKey",List.of(MAIN,EVENT),"Z"));
   }
   require(q.getCodeUnits()==replacement.getCodeUnits(),"call-width");
   c.replaceInstruction(i,replacement);changed++;
  }
  require(changed==1,"call-count");
  return new ImmutableMethod(m.getDefiningClass(),m.getName(),m.getParameters(),m.getReturnType(),m.getAccessFlags(),m.getAnnotations(),m.getHiddenApiRestrictions(),c);
 }
 public static void main(String[]args)throws Exception{
  require(args.length==3,"arguments");
  require(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[0])))).equals("a5f44c7306aafbbde94c371cc6d35dc32f33a6f21a85505039cf4f868dfb9c7e"),"input-dex-sha");
  require(!Files.exists(Path.of(args[2])),"output-exists");
  DexFile original=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28)),compiled=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));
  List<ClassDef>classes=new ArrayList<>();Set<String>types=new HashSet<>();int access=0,listener=0,helper=0;
  for(ClassDef c:original.getClasses()){
   types.add(c.getType());require(!c.getType().startsWith(HELPER.substring(0,HELPER.length()-1)),"helper-already-present");
   if(!c.getType().equals(OWNER)&&!c.getType().equals(MAIN)){classes.add(c);continue;}
   List<Method>directs=new ArrayList<>(),virtuals=new ArrayList<>();
   for(Method m:c.getDirectMethods()){
    if(c.getType().equals(MAIN)&&listenerMethod(m)){directs.add(patched(m,true));listener++;}else directs.add(m);
   }
   for(Method m:c.getVirtualMethods()){
    if(c.getType().equals(OWNER)&&accessMethod(m)){virtuals.add(patched(m,false));access++;}else virtuals.add(m);
   }
   classes.add(new ImmutableClassDef(c.getType(),c.getAccessFlags(),c.getSuperclass(),c.getInterfaces(),c.getSourceFile(),c.getAnnotations(),c.getStaticFields(),c.getInstanceFields(),directs,virtuals));
  }
  for(ClassDef c:compiled.getClasses()){
   require(c.getType().equals(HELPER)||c.getType().startsWith(HELPER.substring(0,HELPER.length()-1)+"$"),"helper-only-no-stubs");
   require(types.add(c.getType()),"duplicate-class");classes.add(c);if(c.getType().equals(HELPER))helper++;
  }
  require(access==1&&listener==1&&helper==1,"change-count");
  DexPool.writeTo(args[2],new ImmutableDexFile(original.getOpcodes(),classes));
  System.out.println("PASS two same-width calls replaced (accessibility and Activity listener); only compiled helper family added");
 }
}
