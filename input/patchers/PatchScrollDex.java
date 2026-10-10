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

/** Add one recovery guard to the pinned, already zoom-patched APK. */
public final class PatchScrollDex {
    static final String OUTER="Lcom/termux/x11/input/TouchInputHandler;";
    static final String OWNER=OUTER.substring(0,OUTER.length()-1)+"$GestureListener;";
    static final String POLICY="Lcom/termux/x11/input/PhysicalTouchpadMotion;";
    static final String STRATEGY="Lcom/termux/x11/input/InputStrategyInterface;";
    static void require(boolean ok,String why){if(!ok)throw new IllegalArgumentException(why);}
    static Method patched(Method m){
        MutableMethodImplementation code=new MutableMethodImplementation(m.getImplementation());
        require(code.getRegisterCount()==10,"register-layout");
        List<BuilderInstruction> old=code.getInstructions();
        require(old.get(0).getOpcode()==Opcode.INVOKE_VIRTUAL
            && ((ReferenceInstruction)old.get(0)).getReference().toString().equals("Landroid/view/MotionEvent;->getPointerCount()I")
            && ((FiveRegisterInstruction)old.get(0)).getRegisterC()==7,"original-prologue");
        require(m.getImplementation().getTryBlocks().isEmpty(),"unexpected-try-block");
        Label original=code.newLabelForIndex(0);
        List<BuilderInstruction> added=List.of(
            new BuilderInstruction22c(Opcode.IGET_OBJECT,1,5,new ImmutableFieldReference(OWNER,"this$0",OUTER)),
            new BuilderInstruction35c(Opcode.INVOKE_STATIC,1,1,0,0,0,0,new ImmutableMethodReference(OUTER,"access$600",List.of(OUTER),STRATEGY)),
            new BuilderInstruction11x(Opcode.MOVE_RESULT_OBJECT,1),
            new BuilderInstruction22c(Opcode.INSTANCE_OF,1,1,new ImmutableTypeReference("Lcom/termux/x11/input/InputStrategyInterface$TrackpadInputStrategy;")),
            new BuilderInstruction21t(Opcode.IF_EQZ,1,original),
            new BuilderInstruction35c(Opcode.INVOKE_STATIC,1,7,0,0,0,0,new ImmutableMethodReference(POLICY,"shouldResume",List.of("Landroid/view/MotionEvent;"),"Z")),
            new BuilderInstruction11x(Opcode.MOVE_RESULT,1),
            new BuilderInstruction21t(Opcode.IF_EQZ,1,original),
            new BuilderInstruction22c(Opcode.IGET_OBJECT,1,5,new ImmutableFieldReference(OWNER,"this$0",OUTER)),
            new BuilderInstruction11n(Opcode.CONST_4,3,0),
            new BuilderInstruction35c(Opcode.INVOKE_STATIC,2,1,3,0,0,0,new ImmutableMethodReference(OUTER,"access$1302",List.of(OUTER,"Z"),"Z")));
        int at=0;for(BuilderInstruction i:added)code.addInstruction(at++,i);
        return new ImmutableMethod(m.getDefiningClass(),m.getName(),m.getParameters(),m.getReturnType(),
            m.getAccessFlags(),m.getAnnotations(),m.getHiddenApiRestrictions(),code);
    }
    public static void main(String[] args)throws Exception{
        require(args.length==3,"arguments");
        require(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[0]))))
            .equals("93635e7b0b0c5dd3f07fa4a002654a2afde9343346fcaa59dcbe332cd4ef724b"),"input-dex-sha");
        require(!Files.exists(Path.of(args[2])),"output-exists");
        DexFile original=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28));
        DexFile compiled=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));
        require(compiled.getClasses().size()==1,"policy-class-count");
        ClassDef policy=compiled.getClasses().iterator().next();require(policy.getType().equals(POLICY),"policy-class");
        List<ClassDef> classes=new ArrayList<>();int changed=0;
        for(ClassDef c:original.getClasses()){
            require(!c.getType().equals(POLICY),"already-patched");
            if(!c.getType().equals(OWNER)){classes.add(c);continue;}
            List<Method> methods=new ArrayList<>();
            for(Method m:c.getVirtualMethods()){
                if(m.getName().equals("onScroll")&&m.getParameterTypes().toString().equals("[Landroid/view/MotionEvent;, Landroid/view/MotionEvent;, F, F]")){
                    methods.add(patched(m));changed++;
                }else methods.add(m);
            }
            classes.add(new ImmutableClassDef(c.getType(),c.getAccessFlags(),c.getSuperclass(),c.getInterfaces(),c.getSourceFile(),c.getAnnotations(),
                c.getStaticFields(),c.getInstanceFields(),c.getDirectMethods(),methods));
        }
        require(changed==1,"target-count");classes.add(policy);
        DexPool.writeTo(args[2],new ImmutableDexFile(original.getOpcodes(),classes));
        System.out.println("PASS one onScroll guard, one physical-touchpad policy; original registers retained");
    }
}
