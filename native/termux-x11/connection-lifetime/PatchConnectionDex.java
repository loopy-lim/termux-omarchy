import com.android.tools.smali.baksmali.Adaptors.ClassDefinition;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.baksmali.formatter.BaksmaliWriter;
import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.builder.*;
import com.android.tools.smali.dexlib2.builder.instruction.*;
import com.android.tools.smali.dexlib2.iface.*;
import com.android.tools.smali.dexlib2.iface.instruction.*;
import com.android.tools.smali.dexlib2.immutable.*;
import com.android.tools.smali.dexlib2.immutable.reference.*;
import com.android.tools.smali.dexlib2.writer.pool.DexPool;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class PatchConnectionDex {
    static final String MAIN = "Lcom/termux/x11/MainActivity;";
    static final String HELPER = "Lcom/termux/x11/utils/ConnectionLifetime;";
    static final String BINDER = "Landroid/os/IBinder;", RECIPIENT = "Landroid/os/IBinder$DeathRecipient;";
    static void check(boolean ok, String reason) { if (!ok) throw new AssertionError(reason); }
    static String ref(Instruction i) { return i instanceof ReferenceInstruction ? ((ReferenceInstruction)i).getReference().toString() : ""; }
    static String text(ClassDef c) throws Exception {
        BaksmaliOptions o = new BaksmaliOptions(); o.apiLevel=28; o.sequentialLabels=true; o.accessorComments=false;
        StringWriter s=new StringWriter(); BaksmaliWriter w=new BaksmaliWriter(s);
        ClassDefinition d=new ClassDefinition(o,c); d.writeTo(w); w.close();
        check(!d.hadValidationErrors(), "dex-validation"); return s.toString();
    }
    static Method patch(Method m) {
        MutableMethodImplementation code=new MutableMethodImplementation(m.getImplementation()); int changed=0;
        for(int i=0;i<code.getInstructions().size();i++) {
            Instruction ins=code.getInstructions().get(i);
            if(m.getName().equals("onReceiveConnection") && ref(ins).equals(BINDER+"->linkToDeath("+RECIPIENT+"I)V")) {
                check(code.getRegisterCount()==8 && ins.getOpcode()==Opcode.INVOKE_INTERFACE, "connection-layout");
                FiveRegisterInstruction r=(FiveRegisterInstruction)ins;
                check(r.getRegisterCount()==3 && r.getRegisterC()==3 && r.getRegisterD()==4 && r.getRegisterE()==5, "connection-registers");
                code.replaceInstruction(i, new BuilderInstruction35c(Opcode.INVOKE_STATIC,4,6,3,4,5,0,
                    new ImmutableMethodReference(HELPER,"link",List.of("Ljava/lang/Object;",BINDER,RECIPIENT,"I"),"V")));
                changed++;
            }
            if(m.getName().equals("onDestroy") && ins.getOpcode()==Opcode.RETURN_VOID) {
                check(code.getRegisterCount()==3, "destroy-layout");
                code.addInstruction(i,new BuilderInstruction35c(Opcode.INVOKE_STATIC,1,2,0,0,0,0,
                    new ImmutableMethodReference(HELPER,"release",List.of("Ljava/lang/Object;"),"V")));
                i++; changed++;
            }
        }
        check(changed==1,"one-hook-per-method");
        return new ImmutableMethod(m.getDefiningClass(),m.getName(),m.getParameters(),m.getReturnType(),m.getAccessFlags(),m.getAnnotations(),m.getHiddenApiRestrictions(),code);
    }
    static Map<String,ClassDef> classes(DexFile d) { Map<String,ClassDef> out=new TreeMap<>(); for(ClassDef c:d.getClasses())out.put(c.getType(),c); return out; }
    public static void main(String[] args) throws Exception {
        DexFile original=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28));
        Map<String,ClassDef> before=classes(original);
        String old=text(before.get(MAIN));
        String call="invoke-interface {v3, v4, v5}, "+BINDER+"->linkToDeath("+RECIPIENT+"I)V";
        check(old.contains(call),"actual-unbounded-registration-seam");
        if(args.length==1) throw new AssertionError("actual-installed-DEX-registers-every-broadcast-without-unlink");
        DexFile helper=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));
        List<ClassDef> output=new ArrayList<>(); int changed=0;
        for(ClassDef c:original.getClasses()) {
            if(!c.getType().equals(MAIN)) { output.add(c); continue; }
            List<Method> direct=new ArrayList<>(), virtual=new ArrayList<>();
            for(Method m:c.getDirectMethods())direct.add(m);
            for(Method m:c.getVirtualMethods()) {
                if(m.getName().equals("onReceiveConnection") || m.getName().equals("onDestroy")) { virtual.add(patch(m)); changed++; }
                else virtual.add(m);
            }
            output.add(new ImmutableClassDef(c.getType(),c.getAccessFlags(),c.getSuperclass(),c.getInterfaces(),c.getSourceFile(),c.getAnnotations(),c.getStaticFields(),c.getInstanceFields(),direct,virtual));
        }
        check(changed==2,"two-hooks");
        for(ClassDef c:helper.getClasses()) { check(!before.containsKey(c.getType()) && c.getType().startsWith(HELPER.substring(0,HELPER.length()-1)),"new-helper-only"); output.add(c); }
        check(!Files.exists(Path.of(args[2])),"output-exists");
        DexPool.writeTo(args[2],new ImmutableDexFile(original.getOpcodes(),output));
        Map<String,ClassDef> after=classes(DexFileFactory.loadDexFile(new File(args[2]),Opcodes.forApi(28)));
        for(String type:before.keySet())if(!type.equals(MAIN))check(text(before.get(type)).equals(text(after.get(type))),"unrelated-class-changed");
        for(ClassDef c:helper.getClasses())check(text(c).equals(text(after.get(c.getType()))),"helper-different");
        String actual=text(after.get(MAIN));
        String expected=old.replace(call,"invoke-static {p0, v3, v4, v5}, "+HELPER+"->link(Ljava/lang/Object;"+BINDER+RECIPIENT+"I)V");
        String added="    invoke-static {p0}, "+HELPER+"->release(Ljava/lang/Object;)V\n\n";
        check(actual.contains(added),"release-hook-missing");
        check(actual.replace(added,"").equals(expected),"activity-unrelated-change");
        Files.writeString(Path.of(args[2]+".main.smali"),actual);
        System.out.println("PASS actual DEX: two hooks, " +(before.size()-1)+" classes unchanged, compiled helper identical");
    }
}
