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

/** Pinned insertions at physical-touchpad raw-motion and terminal default branches only. */
public final class PatchLifecycleDex {
 static final String OWNER="Lcom/termux/x11/input/TouchInputHandler;",POLICY="Lcom/termux/x11/input/PhysicalTouchpadMotion;",STRATEGY="Lcom/termux/x11/input/InputStrategyInterface;";
 static void require(boolean b,String why){if(!b)throw new IllegalArgumentException(why);}
 static Reference ref(Instruction i){return i instanceof ReferenceInstruction?((ReferenceInstruction)i).getReference():null;}
 static void move(Label l,MethodLocation destination){l.getLocation().getLabels().remove(l);destination.getLabels().add(l);}
 static BuilderInstruction strategy(){return new BuilderInstruction22c(Opcode.IGET_OBJECT,0,10,new ImmutableFieldReference(OWNER,"mInputStrategy",STRATEGY));}
 static BuilderInstruction isTrackpad(){return new BuilderInstruction22c(Opcode.INSTANCE_OF,0,0,new ImmutableTypeReference("Lcom/termux/x11/input/InputStrategyInterface$TrackpadInputStrategy;"));}
 static BuilderInstruction policy(String method){return new BuilderInstruction35c(Opcode.INVOKE_STATIC,1,13,0,0,0,0,new ImmutableMethodReference(POLICY,method,List.of("Landroid/view/MotionEvent;"),"Z"));}
 static BuilderInstruction clear(String field){return new BuilderInstruction22c(Opcode.IPUT_BOOLEAN,3,10,new ImmutableFieldReference(OWNER,field,"Z"));}
 static Method patched(Method m){
  MutableMethodImplementation c=new MutableMethodImplementation(m.getImplementation());require(c.getRegisterCount()==14,"register-layout");require(m.getImplementation().getTryBlocks().isEmpty(),"unexpected-try-block");
  int scroller=-1,masked=-1;List<BuilderInstruction>a=c.getInstructions();
  for(int i=0;i<a.size();i++){Reference r=ref(a.get(i));if(r instanceof FieldReference&&((FieldReference)r).getName().equals("mScroller")){require(scroller<0,"scroller-count");scroller=i;}if(r instanceof MethodReference&&((MethodReference)r).getDefiningClass().equals("Landroid/view/MotionEvent;")&&((MethodReference)r).getName().equals("getActionMasked")){require(masked<0,"masked-count");masked=i;}}
  require(scroller>1&&masked>scroller,"anchors");require(a.get(scroller).getOpcode()==Opcode.IGET_OBJECT&&((TwoRegisterInstruction)a.get(scroller)).getRegisterA()==0&&((TwoRegisterInstruction)a.get(scroller)).getRegisterB()==10,"scroller-load");
  require(a.get(masked+2).getOpcode()==Opcode.SPARSE_SWITCH&&a.get(masked+3).getOpcode()==Opcode.GOTO,"terminal-default-layout");int finish=masked+3;
  require(((FiveRegisterInstruction)a.get(masked)).getRegisterC()==13,"masked-event-register");require(((OneRegisterInstruction)a.get(masked+2)).getRegisterA()==0,"switch-action-register");
  // Existing terminal defaults fall through here; original switch cases and return remain intact.
  Label skipFinish=c.newLabelForIndex(finish),terminal=c.newLabelForIndex(finish);
  List<BuilderInstruction> f=List.of(new BuilderInstruction11n(Opcode.CONST_4,4,1),new BuilderInstruction22t(Opcode.IF_EQ,0,4,terminal),new BuilderInstruction11n(Opcode.CONST_4,4,3),new BuilderInstruction22t(Opcode.IF_NE,0,4,skipFinish),strategy(),isTrackpad(),new BuilderInstruction21t(Opcode.IF_EQZ,0,skipFinish),policy("shouldFinish"),new BuilderInstruction11x(Opcode.MOVE_RESULT,0),new BuilderInstruction21t(Opcode.IF_EQZ,0,skipFinish),clear("mSuppressCursorMovement"),clear("mSwipeCompleted"),clear("mIsDragging"));
  for(int i=0;i<f.size();i++)c.addInstruction(finish+i,f.get(i));move(terminal,c.getInstructions().get(finish+4).getLocation());
  // Move only prior incoming labels to the guard. The new skip label stays on original mScroller IGET.
  MethodLocation oldScroller=c.getInstructions().get(scroller).getLocation();List<Label>incoming=new ArrayList<>(oldScroller.getLabels());Label skipRaw=c.newLabelForIndex(scroller);
  List<BuilderInstruction>r=List.of(strategy(),isTrackpad(),new BuilderInstruction21t(Opcode.IF_EQZ,0,skipRaw),policy("shouldResume"),new BuilderInstruction11x(Opcode.MOVE_RESULT,0),new BuilderInstruction21t(Opcode.IF_EQZ,0,skipRaw),clear("mSuppressCursorMovement"));
  for(int i=0;i<r.size();i++)c.addInstruction(scroller+i,r.get(i));for(Label l:incoming)move(l,c.getInstructions().get(scroller).getLocation());
  return new ImmutableMethod(m.getDefiningClass(),m.getName(),m.getParameters(),m.getReturnType(),m.getAccessFlags(),m.getAnnotations(),m.getHiddenApiRestrictions(),c);
 }
 public static void main(String[]args)throws Exception{
  require(args.length==3,"arguments");require(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[0])))).equals("78e1f0262a42c8de4ea627b6663812631fa6bcbe5e4a7c0ce69a011403db83fe"),"input-dex-sha");require(!Files.exists(Path.of(args[2])),"output-exists");
  DexFile original=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28)),compiled=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));require(compiled.getClasses().size()==1,"policy-count");ClassDef policy=compiled.getClasses().iterator().next();require(policy.getType().equals(POLICY),"policy-type");
  List<ClassDef>classes=new ArrayList<>();int methods=0,policies=0;
  for(ClassDef c:original.getClasses()){
   if(c.getType().equals(POLICY)){classes.add(policy);policies++;continue;}if(!c.getType().equals(OWNER)){classes.add(c);continue;}
   List<Method>virtuals=new ArrayList<>();for(Method m:c.getVirtualMethods()){if(m.getName().equals("handleTouchEvent")&&m.getParameterTypes().toString().equals("[Landroid/view/View;, Landroid/view/View;, Landroid/view/MotionEvent;]")){virtuals.add(patched(m));methods++;}else virtuals.add(m);}
   classes.add(new ImmutableClassDef(c.getType(),c.getAccessFlags(),c.getSuperclass(),c.getInterfaces(),c.getSourceFile(),c.getAnnotations(),c.getStaticFields(),c.getInstanceFields(),c.getDirectMethods(),virtuals));
  }require(methods==1&&policies==1,"change-count");DexPool.writeTo(args[2],new ImmutableDexFile(original.getOpcodes(),classes));System.out.println("PASS one handleTouchEvent raw guard and UP/CANCEL default guard; existing incoming labels retargeted; physical policy replaced only");
 }
}
