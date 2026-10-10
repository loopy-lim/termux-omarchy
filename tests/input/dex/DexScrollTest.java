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

/** Check every original class and execute the actual new APK guard with fixed fixtures. */
public final class DexScrollTest {
    static final String OWNER="Lcom/termux/x11/input/TouchInputHandler$GestureListener;";
    static final String POLICY="Lcom/termux/x11/input/PhysicalTouchpadMotion;";
    static void check(boolean ok,String why){if(!ok)throw new AssertionError(why);}
    static String disassemble(ClassDef c)throws Exception{
        BaksmaliOptions o=new BaksmaliOptions();o.apiLevel=28;o.sequentialLabels=true;o.accessorComments=false;
        StringWriter s=new StringWriter();BaksmaliWriter w=new BaksmaliWriter(s);
        ClassDefinition d=new ClassDefinition(o,c);d.writeTo(w);w.close();check(!d.hadValidationErrors(),"DEX validation");return s.toString();
    }
    static List<Instruction> instructions(Method m){List<Instruction> r=new ArrayList<>();m.getImplementation().getInstructions().forEach(r::add);return r;}
    static Reference ref(Instruction i){return i instanceof ReferenceInstruction?((ReferenceInstruction)i).getReference():null;}
    static String fingerprint(Instruction i){
        StringBuilder s=new StringBuilder(i.getOpcode().name).append(':').append(i.getCodeUnits());
        if(i instanceof OneRegisterInstruction)s.append(" A").append(((OneRegisterInstruction)i).getRegisterA());
        if(i instanceof TwoRegisterInstruction)s.append(" B").append(((TwoRegisterInstruction)i).getRegisterB());
        if(i instanceof ThreeRegisterInstruction)s.append(" C").append(((ThreeRegisterInstruction)i).getRegisterC());
        if(i instanceof FiveRegisterInstruction){FiveRegisterInstruction f=(FiveRegisterInstruction)i;s.append(" N").append(f.getRegisterCount()).append(':').append(f.getRegisterC()).append(',').append(f.getRegisterD()).append(',').append(f.getRegisterE()).append(',').append(f.getRegisterF()).append(',').append(f.getRegisterG());}
        if(i instanceof RegisterRangeInstruction){RegisterRangeInstruction r=(RegisterRangeInstruction)i;s.append(" R").append(r.getStartRegister()).append(':').append(r.getRegisterCount());}
        if(i instanceof WideLiteralInstruction)s.append(" L").append(((WideLiteralInstruction)i).getWideLiteral());
        if(i instanceof OffsetInstruction)s.append(" O").append(((OffsetInstruction)i).getCodeOffset());
        if(i instanceof ReferenceInstruction)s.append(" X").append(((ReferenceInstruction)i).getReference());
        if(i instanceof DualReferenceInstruction)s.append(" Y").append(((DualReferenceInstruction)i).getReference2());
        if(i instanceof SwitchPayload)for(SwitchElement e:((SwitchPayload)i).getSwitchElements())s.append(" S").append(e.getKey()).append(':').append(e.getOffset());
        return s.toString();
    }
    static Method scroll(ClassDef c){for(Method m:c.getMethods())if(m.getName().equals("onScroll"))return m;throw new AssertionError("scroll missing");}
    static String excludingScroll(String text){return text.replaceFirst("(?s)\\.method public onScroll\\(Landroid/view/MotionEvent;Landroid/view/MotionEvent;FF\\)Z.*?\\.end method","");}
    static boolean guard(List<Instruction> code,int count,int action,int source,int tool,boolean trackpad)throws Exception{
        Object[] r=new Object[10];Object outer=new Object(),strategy=new Object();r[5]=new Object();
        r[7]=Class.forName("android.view.MotionEvent").getConstructor(int.class,int.class,int.class,int.class).newInstance(count,action,source,tool);
        Object result=null;boolean cleared=false;int address=0;Map<Integer,Integer> locations=new HashMap<>();int[] addresses=new int[code.size()];
        for(int i=0;i<code.size();i++){addresses[i]=address;locations.put(address,i);address+=code.get(i).getCodeUnits();}
        for(int pc=0,steps=0;steps<16;steps++){
            if(pc==11)return cleared;
            check(pc>=0&&pc<11,"guard jumped outside prefix");Instruction i=code.get(pc);Reference ref=ref(i);String op=i.getOpcode().name;
            if(op.equals("iget-object")){check(ref instanceof FieldReference&&((FieldReference)ref).getName().equals("this$0"),"only outer receiver read");r[((TwoRegisterInstruction)i).getRegisterA()]=outer;}
            else if(op.equals("invoke-static")){
                MethodReference m=(MethodReference)ref;FiveRegisterInstruction f=(FiveRegisterInstruction)i;
                if(m.getName().equals("access$600")){check(r[f.getRegisterC()]==outer,"strategy owner");result=strategy;}
                else if(m.getDefiningClass().equals(POLICY)&&m.getName().equals("shouldResume"))result=(Boolean)Class.forName("com.termux.x11.input.PhysicalTouchpadMotion").getMethod("shouldResume",Class.forName("android.view.MotionEvent")).invoke(null,r[f.getRegisterC()])?1:0;
                else if(m.getName().equals("access$1302")){check(r[f.getRegisterC()]==outer&&Integer.valueOf(0).equals(r[f.getRegisterD()]),"clear only suppression false");cleared=true;result=0;}
                else throw new AssertionError("unexpected guard call");
            }else if(op.equals("move-result-object")||op.equals("move-result"))r[((OneRegisterInstruction)i).getRegisterA()]=result;
            else if(op.equals("instance-of")){check(ref.toString().endsWith("$TrackpadInputStrategy;"),"strategy guard type");r[((TwoRegisterInstruction)i).getRegisterA()]=trackpad?1:0;}
            else if(op.equals("const/4"))r[((OneRegisterInstruction)i).getRegisterA()]=((NarrowLiteralInstruction)i).getNarrowLiteral();
            else if(op.equals("if-eqz")){if(Integer.valueOf(0).equals(r[((OneRegisterInstruction)i).getRegisterA()])){pc=locations.get(addresses[pc]+((OffsetInstruction)i).getCodeOffset());continue;}}
            else throw new AssertionError("unexpected guard opcode "+op);
            pc++;
        }throw new AssertionError("guard steps bound");
    }
    public static void main(String[] args)throws Exception{
        DexFile before=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28)),after=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));
        Map<String,ClassDef> next=new HashMap<>();for(ClassDef c:after.getClasses())next.put(c.getType(),c);
        check(after.getClasses().size()==before.getClasses().size()+1,"class count");int same=0,changed=0;Method oldScroll=null,newScroll=null;
        for(ClassDef c:before.getClasses()){
            ClassDef n=next.remove(c.getType());check(n!=null,"original class removed");String a=disassemble(c),b=disassemble(n);
            if(a.equals(b)){same++;continue;}
            check(c.getType().equals(OWNER),"unrelated class changed");check(excludingScroll(a).equals(excludingScroll(b)),"other inner methods/fields/debug metadata changed");
            oldScroll=scroll(c);newScroll=scroll(n);Files.writeString(Path.of(args[3],"GestureListener-before.smali"),a);Files.writeString(Path.of(args[3],"GestureListener-after.smali"),b);changed++;
        }
        check(changed==1&&next.size()==1&&next.containsKey(POLICY),"only one new policy");
        DexFile policy=DexFileFactory.loadDexFile(new File(args[2]),Opcodes.forApi(28));check(policy.getClasses().size()==1,"compiled policy count");
        check(disassemble(next.get(POLICY)).equals(disassemble(policy.getClasses().iterator().next())),"packaged policy differs from compiled real source");
        List<Instruction> a=instructions(oldScroll),b=instructions(newScroll);
        check(newScroll.getImplementation().getRegisterCount()==oldScroll.getImplementation().getRegisterCount(),"register count changed");
        check(b.size()==a.size()+11,"prefix instruction count");int units=0;for(int i=0;i<11;i++)units+=b.get(i).getCodeUnits();check(units==22,"prefix alignment");
        for(int i=0;i<a.size();i++)check(fingerprint(a.get(i)).equals(fingerprint(b.get(i+11))),"original suffix instruction changed at "+i);
        check(guard(b,1,2,0x100008,1,true),"physical single MOVE resumes");
        int[][] no={{0,2,0x100008,1},{2,2,0x100008,1},{3,2,0x100008,1},{1,0,0x100008,1},{1,1,0x100008,1},{1,3,0x100008,1},{1,6,0x100008,1},{1,7,0x100008,1},{1,2,0x1002,1},{1,2,0x10100a,1},{1,2,0x2002,3},{1,2,0x20004,3},{1,2,0,1},{1,2,0x100008,0},{1,2,0x100008,2},{1,2,0x100008,3}};
        for(int[] v:no)check(!guard(b,v[0],v[1],v[2],v[3],true),"ineligible actual DEX route");
        check(!guard(b,1,2,0x100008,1,false),"other strategy unchanged");
        System.out.println("PASS "+same+" original classes unchanged; only onScroll 11-instruction prefix + one source-matched policy; original suffix exact; 18 actual APK guard routes");
    }
}
