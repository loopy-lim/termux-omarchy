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

/** Execute the packaged handleTouchEvent guards; compare all original classes and control flow. */
public final class DexLifecycleTest {
 static final String OUTER="Lcom/termux/x11/input/TouchInputHandler;",POLICY="Lcom/termux/x11/input/PhysicalTouchpadMotion;";
 static int passed,failed;
 static void check(boolean ok,String why){if(!ok)throw new AssertionError(why);}
 static void route(boolean ok,String why){if(ok)passed++;else{failed++;System.out.println("FAIL "+why);}}
 static Reference ref(Instruction i){return i instanceof ReferenceInstruction?((ReferenceInstruction)i).getReference():null;}
 static List<Instruction> code(Method m){List<Instruction> a=new ArrayList<>();m.getImplementation().getInstructions().forEach(a::add);return a;}
 static Method method(ClassDef c,String name){for(Method m:c.getMethods())if(m.getName().equals(name))return m;throw new AssertionError("method-missing "+name);}
 static Map<String,ClassDef> classes(DexFile d){Map<String,ClassDef> r=new HashMap<>();for(ClassDef c:d.getClasses())r.put(c.getType(),c);return r;}
 static String text(ClassDef c)throws Exception{BaksmaliOptions o=new BaksmaliOptions();o.apiLevel=28;o.sequentialLabels=true;o.accessorComments=false;StringWriter s=new StringWriter();BaksmaliWriter w=new BaksmaliWriter(s);ClassDefinition d=new ClassDefinition(o,c);d.writeTo(w);w.close();check(!d.hadValidationErrors(),"decoded-validation");return s.toString();}
 static String excluding(String t,String signature){return t.replaceFirst("(?s)\\.method [^\\n]*"+java.util.regex.Pattern.quote(signature)+".*?\\.end method\\n\\n?","");}
 static int field(List<Instruction>a,String n){int found=-1;for(int i=0;i<a.size();i++)if(ref(a.get(i)) instanceof FieldReference&&((FieldReference)ref(a.get(i))).getName().equals(n)){check(found<0,"unique-field-"+n);found=i;}check(found>=0,"field-"+n);return found;}
 static int call(List<Instruction>a,String owner,String n){int found=-1;for(int i=0;i<a.size();i++)if(ref(a.get(i)) instanceof MethodReference){MethodReference r=(MethodReference)ref(a.get(i));if(r.getDefiningClass().equals(owner)&&r.getName().equals(n)){check(found<0,"unique-call-"+n);found=i;}}check(found>=0,"call-"+n);return found;}
 static int[] addresses(List<Instruction>a){int[]r=new int[a.size()];for(int i=1;i<a.size();i++)r[i]=r[i-1]+a.get(i-1).getCodeUnits();return r;}
 static int target(List<Instruction>a,int at){int address=addresses(a)[at]+((OffsetInstruction)a.get(at)).getCodeOffset();for(int i=0;i<a.size();i++)if(addresses(a)[i]==address)return i;throw new AssertionError("branch-target");}
 static int rawStart(List<Instruction>a){return call(a,"Lcom/termux/x11/input/InputStrategyInterface;","onMotionEvent")+1;}
 static int finishStart(List<Instruction>a){int i=call(a,"Landroid/view/MotionEvent;","getActionMasked");check(a.get(i+2).getOpcode()==Opcode.SPARSE_SWITCH,"original-switch");return i+3;}
 static int finishEnd(List<Instruction>a){for(int i=finishStart(a);i<a.size();i++)if(a.get(i).getOpcode()==Opcode.GOTO)return i;throw new AssertionError("default-goto");}
 static boolean[] execute(List<Instruction>a,int start,int end,int count,int action,int source,int tool,boolean trackpad)throws Exception{
  Object[]r=new Object[14];Object self=new Object(),strategy=new Object();r[10]=self;r[13]=new android.view.MotionEvent(count,action,source,tool);r[0]=action&255;r[3]=0;
  boolean[]flags={true,true,true};Object result=null;int pc=start;
  for(int steps=0;pc!=end&&steps<64;steps++){
   check(pc>=start&&pc<end,"guard-escaped-scope");Instruction i=a.get(pc);String op=i.getOpcode().name;Reference reference=ref(i);
   if(op.equals("iget-object")){FieldReference f=(FieldReference)reference;TwoRegisterInstruction q=(TwoRegisterInstruction)i;check(f.getName().equals("mInputStrategy")&&r[q.getRegisterB()]==self,"only-strategy-read");r[q.getRegisterA()]=strategy;}
   else if(op.equals("instance-of")){TwoRegisterInstruction q=(TwoRegisterInstruction)i;check(reference.toString().endsWith("$TrackpadInputStrategy;"),"trackpad-type");r[q.getRegisterA()]=trackpad?1:0;}
   else if(op.equals("invoke-static")){MethodReference m=(MethodReference)reference;FiveRegisterInstruction q=(FiveRegisterInstruction)i;check(m.getDefiningClass().equals(POLICY)&&(m.getName().equals("shouldResume")||m.getName().equals("shouldFinish")),"policy-only-call");result=(Boolean)Class.forName("com.termux.x11.input.PhysicalTouchpadMotion").getMethod(m.getName(),android.view.MotionEvent.class).invoke(null,r[q.getRegisterC()])?1:0;}
   else if(op.equals("move-result"))r[((OneRegisterInstruction)i).getRegisterA()]=result;
   else if(op.equals("const/4"))r[((OneRegisterInstruction)i).getRegisterA()]=((NarrowLiteralInstruction)i).getNarrowLiteral();
   else if(op.equals("iput-boolean")){TwoRegisterInstruction q=(TwoRegisterInstruction)i;check(r[q.getRegisterB()]==self&&Integer.valueOf(0).equals(r[q.getRegisterA()]),"only-false-own-field-write");String n=((FieldReference)reference).getName();int k=n.equals("mSuppressCursorMovement")?0:n.equals("mSwipeCompleted")?1:n.equals("mIsDragging")?2:-1;check(k>=0,"only-approved-three-flags");flags[k]=false;}
   else if(op.equals("if-eqz")||op.equals("if-nez")){boolean zero=Integer.valueOf(0).equals(r[((OneRegisterInstruction)i).getRegisterA()]);if(zero==op.equals("if-eqz")){pc=target(a,pc);continue;}}
   else if(op.equals("if-eq")||op.equals("if-ne")){TwoRegisterInstruction q=(TwoRegisterInstruction)i;boolean eq=Objects.equals(r[q.getRegisterA()],r[q.getRegisterB()]);if(eq==op.equals("if-eq")){pc=target(a,pc);continue;}}
   else throw new AssertionError("guard-opcode-"+op);
   pc++;
  }check(pc==end,"guard-step-bound");return flags;
 }
 static void routes(Method m)throws Exception{
  List<Instruction>a=code(m);int rs=rawStart(a),re=field(a,"mScroller"),fs=finishStart(a),fe=finishEnd(a);
  route(Arrays.equals(execute(a,rs,re,1,2,0x100008,1,true),new boolean[]{false,true,true}),"raw-single-MOVE-clears-only-suppress-before-scroller");
  int[][]no={{0,2,0x100008,1},{2,2,0x100008,1},{3,2,0x100008,1},{1,0,0x100008,1},{1,1,0x100008,1},{1,3,0x100008,1},{1,6,0x100008,1},{1,2,0x1002,1},{1,2,0x10100a,1},{1,2,0x2002,1},{1,2,0x20004,3},{1,2,0,1},{1,2,0x100008,0},{1,2,0x100008,2},{1,2,0x100008,3}};
  for(int[]v:no)route(Arrays.equals(execute(a,rs,re,v[0],v[1],v[2],v[3],true),new boolean[]{true,true,true}),"raw-ineligible-"+Arrays.toString(v));
  route(Arrays.equals(execute(a,rs,re,1,2,0x100008,1,false),new boolean[]{true,true,true}),"raw-other-strategy");
  for(int action:new int[]{1,3}){
   route(Arrays.equals(execute(a,fs,fe,1,action,0x100008,1,true),new boolean[]{false,false,false}),"terminal-all-three-reset-"+action);
   route(Arrays.equals(execute(a,fs,fe,1,action,0x100008,1,false),new boolean[]{true,true,true}),"terminal-other-strategy-"+action);
   for(int[]v:new int[][]{{0x1002,1},{0x10100a,1},{0x2002,1},{0x100008,0},{0x100008,2},{0x100008,3}})route(Arrays.equals(execute(a,fs,fe,1,action,v[0],v[1],true),new boolean[]{true,true,true}),"terminal-ineligible-"+action+Arrays.toString(v));
  }
  for(int action:new int[]{2,6,7,9})route(Arrays.equals(execute(a,fs,fe,1,action,0x100008,1,true),new boolean[]{true,true,true}),"nonterminal-default-"+action);
  check(rs<=re&&fs>call(a,"Lcom/termux/x11/input/SwipeDetector;","onTouchEvent"),"guard-placement");
 }
 static String fingerprint(Instruction i){StringBuilder s=new StringBuilder(i.getOpcode().name);if(i instanceof OneRegisterInstruction)s.append(" A").append(((OneRegisterInstruction)i).getRegisterA());if(i instanceof TwoRegisterInstruction)s.append(" B").append(((TwoRegisterInstruction)i).getRegisterB());if(i instanceof ThreeRegisterInstruction)s.append(" C").append(((ThreeRegisterInstruction)i).getRegisterC());if(i instanceof FiveRegisterInstruction){FiveRegisterInstruction q=(FiveRegisterInstruction)i;s.append(" N").append(q.getRegisterCount()).append(':').append(q.getRegisterC()).append(',').append(q.getRegisterD()).append(',').append(q.getRegisterE()).append(',').append(q.getRegisterF()).append(',').append(q.getRegisterG());}if(i instanceof RegisterRangeInstruction){RegisterRangeInstruction q=(RegisterRangeInstruction)i;s.append(" R").append(q.getStartRegister()).append(':').append(q.getRegisterCount());}if(i instanceof WideLiteralInstruction)s.append(" L").append(((WideLiteralInstruction)i).getWideLiteral());if(i instanceof ReferenceInstruction)s.append(" X").append(ref(i));if(i instanceof DualReferenceInstruction)s.append(" Y").append(((DualReferenceInstruction)i).getReference2());return s.toString();}
 static void preservation(DexFile before,DexFile after,DexFile policy,Path out)throws Exception{
  Map<String,ClassDef>b=classes(before),n=classes(after);check(b.keySet().equals(n.keySet()),"same-class-set");int unchanged=0;
  for(String type:b.keySet()){String x=text(b.get(type)),y=text(n.get(type));if(type.equals(OUTER)){check(excluding(x,"handleTouchEvent(Landroid/view/View;Landroid/view/View;Landroid/view/MotionEvent;)Z").equals(excluding(y,"handleTouchEvent(Landroid/view/View;Landroid/view/View;Landroid/view/MotionEvent;)Z")),"all-other-outer-methods-fields-metadata");Files.writeString(out.resolve("TouchInputHandler-before.smali"),x);Files.writeString(out.resolve("TouchInputHandler-after.smali"),y);}else if(type.equals(POLICY)){check(x.equals(excluding(y,"shouldFinish(Landroid/view/MotionEvent;)Z")),"old-policy-constructor-and-resume-unchanged");check(policy.getClasses().size()==1&&y.equals(text(policy.getClasses().iterator().next())),"packaged-policy-source-compiled-equality");}else{check(x.equals(y),"unrelated-class-changed-"+type);unchanged++;}}
  List<Instruction>a=code(method(b.get(OUTER),"handleTouchEvent")),c=code(method(n.get(OUTER),"handleTouchEvent"));
  int rs=rawStart(c),re=field(c,"mScroller"),fs=finishStart(c),fe=finishEnd(c);List<Integer>map=new ArrayList<>();for(int i=0;i<c.size();i++)if(!(i>=rs&&i<re)&&!(i>=fs&&i<fe))map.add(i);
  check(map.size()==a.size(),"only-two-inserted-blocks");for(int i=0;i<a.size();i++){int j=map.get(i);check(fingerprint(a.get(i)).equals(fingerprint(c.get(j))),"original-instruction-"+i);if(a.get(i) instanceof OffsetInstruction){int t=target(a,i),actual=target(c,j),expected=map.get(t);if(t==rawStart(a))expected=rs;check(actual==expected,"original-branch-target-"+i);}}
  for(int i=0;i<a.size();i++)if(a.get(i) instanceof SwitchPayload){
   int branch=-1;for(int k=0;k<a.size();k++)if(a.get(k).getOpcode()==Opcode.SPARSE_SWITCH&&target(a,k)==i)branch=k;check(branch>=0,"payload-owner");
   List<? extends SwitchElement>x=((SwitchPayload)a.get(i)).getSwitchElements(),y=((SwitchPayload)c.get(map.get(i))).getSwitchElements();check(x.size()==y.size(),"switch-case-count");
   for(int k=0;k<x.size();k++){check(x.get(k).getKey()==y.get(k).getKey(),"switch-case-key");int oldAddress=addresses(a)[branch]+x.get(k).getOffset(),newAddress=addresses(c)[map.get(branch)]+y.get(k).getOffset();int oldTarget=-1,newTarget=-1;for(int q=0;q<a.size();q++)if(addresses(a)[q]==oldAddress)oldTarget=q;for(int q=0;q<c.size();q++)if(addresses(c)[q]==newAddress)newTarget=q;check(oldTarget>=0&&newTarget==map.get(oldTarget),"switch-case-target");}
  }
  check(method(b.get(OUTER),"handleTouchEvent").getImplementation().getRegisterCount()==14&&method(n.get(OUTER),"handleTouchEvent").getImplementation().getRegisterCount()==14,"register-layout-retained");
  System.out.println("PASS "+unchanged+" other classes decoded-identical; only handleTouchEvent insertions and source-matched shouldFinish policy; all original instructions/control-flow retained");
 }
 public static void main(String[]args)throws Exception{
  DexFile after=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));routes(method(classes(after).get(OUTER),"handleTouchEvent"));
  System.out.println("DEX route checks: "+passed+" pass / "+failed+" fail");check(failed==0,"actual-packaged-lifecycle-routes");
  if(!args[0].equals("--routes-only"))preservation(DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28)),after,DexFileFactory.loadDexFile(new File(args[2]),Opcodes.forApi(28)),Path.of(args[3]));
 }
}
