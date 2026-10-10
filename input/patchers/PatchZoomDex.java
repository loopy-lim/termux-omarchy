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

/** Pinned DEX repair: preserve the installed native/manifest patches and every other method. */
public final class PatchZoomDex {
    static final String OWNER="Lcom/termux/x11/input/TouchInputHandler;";
    static final String POLICY="Lcom/termux/x11/input/LocalPinchZoom;";
    static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
    static Reference ref(Instruction i){return i instanceof ReferenceInstruction?((ReferenceInstruction)i).getReference():null;}
    static Method patched(Method m) {
        MutableMethodImplementation code=new MutableMethodImplementation(m.getImplementation());
        require(code.getRegisterCount()==14,"unexpected-register-layout");
        List<BuilderInstruction> instructions=code.getInstructions();
        int index=-1,count=0;
        for(int n=0;n<instructions.size();n++) {
            Reference r=ref(instructions.get(n));
            if(r instanceof FieldReference && ((FieldReference)r).getName().equals("mZoomer")) {index=n;count++;}
        }
        require(count==1 && index>0 && index+2<instructions.size(),"unexpected-zoom-count");
        Instruction load=instructions.get(index),invoke=instructions.get(index+1),after=instructions.get(index+2);
        require(load.getOpcode()==Opcode.IGET_OBJECT && ((TwoRegisterInstruction)load).getRegisterA()==0
                && ((TwoRegisterInstruction)load).getRegisterB()==10,"unexpected-zoom-receiver");
        require(instructions.get(index-1).getOpcode()==Opcode.IF_NEZ,"missing-direct-touch-guard");
        require(ref(after) instanceof FieldReference && ((FieldReference)ref(after)).getName().equals("mTapDetector"),"unexpected-post-zoom-route");
        require(invoke.getOpcode()==Opcode.INVOKE_VIRTUAL && ref(invoke) instanceof MethodReference,"unexpected-zoom-invoke");
        MethodReference called=(MethodReference)ref(invoke);
        require(called.getDefiningClass().equals("Landroid/view/ScaleGestureDetector;")
                && called.getName().equals("onTouchEvent") && called.getReturnType().equals("Z")
                && called.getParameterTypes().toString().equals("[Landroid/view/MotionEvent;]"),"unexpected-zoom-method");
        require(((FiveRegisterInstruction)invoke).getRegisterCount()==2
                && ((FiveRegisterInstruction)invoke).getRegisterC()==0
                && ((FiveRegisterInstruction)invoke).getRegisterD()==13,"unexpected-zoom-arguments");
        Label skip=code.newLabelForIndex(index+2);
        // v0 is dead before its original receiver load and on the existing skip target.
        code.addInstruction(index++,new BuilderInstruction35c(Opcode.INVOKE_VIRTUAL,1,13,0,0,0,0,
                new ImmutableMethodReference("Landroid/view/MotionEvent;","getSource",List.of(),"I")));
        code.addInstruction(index++,new BuilderInstruction11x(Opcode.MOVE_RESULT,0));
        code.addInstruction(index++,new BuilderInstruction35c(Opcode.INVOKE_STATIC,1,0,0,0,0,0,
                new ImmutableMethodReference(POLICY,"shouldHandle",List.of("I"),"Z")));
        code.addInstruction(index++,new BuilderInstruction11x(Opcode.MOVE_RESULT,0));
        code.addInstruction(index,new BuilderInstruction21t(Opcode.IF_EQZ,0,skip));
        return new ImmutableMethod(m.getDefiningClass(),m.getName(),m.getParameters(),m.getReturnType(),
                m.getAccessFlags(),m.getAnnotations(),m.getHiddenApiRestrictions(),code);
    }
    public static void main(String[] args) throws Exception {
        require(args.length==3,"arguments");
        byte[] bytes=Files.readAllBytes(Path.of(args[0]));
        require(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes))
                .equals("8b40ebd0632868f8cec7093249c5b4f5ced6c1fe5f938fca91f36025a37c4d7f"),"input-dex-identity");
        require(!Files.exists(Path.of(args[2])),"output-exists");
        DexFile original=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28));
        DexFile helper=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));
        require(helper.getClasses().size()==1,"unexpected-policy-classes");
        ClassDef policy=helper.getClasses().iterator().next();require(policy.getType().equals(POLICY),"policy-class-identity");
        List<ClassDef> classes=new ArrayList<>();int changed=0;
        for(ClassDef c:original.getClasses()) {
            require(!c.getType().equals(POLICY),"already-patched");
            if(!c.getType().equals(OWNER)){classes.add(c);continue;}
            List<Method> virtuals=new ArrayList<>();
            for(Method m:c.getVirtualMethods()) {
                if(m.getName().equals("handleTouchEvent") && m.getParameterTypes().toString()
                        .equals("[Landroid/view/View;, Landroid/view/View;, Landroid/view/MotionEvent;]")) {
                    virtuals.add(patched(m));changed++;
                } else virtuals.add(m);
            }
            classes.add(new ImmutableClassDef(c.getType(),c.getAccessFlags(),c.getSuperclass(),c.getInterfaces(),
                    c.getSourceFile(),c.getAnnotations(),c.getStaticFields(),c.getInstanceFields(),c.getDirectMethods(),virtuals));
        }
        require(changed==1,"target-method-count");classes.add(policy);
        DexPool.writeTo(args[2],new ImmutableDexFile(original.getOpcodes(),classes));
        System.out.println("PASS one method guarded, one pure policy class added; registers and existing routes preserved");
    }
}
