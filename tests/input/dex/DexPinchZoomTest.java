import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcodes;
import com.android.tools.smali.dexlib2.iface.*;
import com.android.tools.smali.dexlib2.iface.instruction.*;
import com.android.tools.smali.dexlib2.iface.reference.*;
import java.io.File;
import java.util.*;

/** Execute the real APK's pinch-dispatch block with literal Android source fixtures. */
public class DexPinchZoomTest {
    static final String OWNER = "Lcom/termux/x11/input/TouchInputHandler;";
    static Method target(DexFile dex) {
        for (ClassDef c : dex.getClasses()) if (c.getType().equals(OWNER))
            for (Method m : c.getMethods()) if (m.getName().equals("handleTouchEvent")) return m;
        throw new AssertionError("actual pinch dispatch method missing");
    }
    static Reference reference(Instruction i) {
        return i instanceof ReferenceInstruction ? ((ReferenceInstruction)i).getReference() : null;
    }
    static boolean reachesZoom(Method m, int source) throws Exception {
        List<Instruction> code = new ArrayList<>();
        Map<Integer,Integer> positions = new HashMap<>();
        int address = 0, start = -1;
        for (Instruction i : m.getImplementation().getInstructions()) {
            positions.put(address,code.size()); code.add(i); address += i.getCodeUnits();
            Reference r = reference(i);
            if (i.getOpcode().name.equals("instance-of") && r instanceof TypeReference
                    && ((TypeReference)r).getType().endsWith("$NullInputStrategy;")) start = code.size()+1;
        }
        if (start < 0 || !code.get(start-1).getOpcode().name.equals("if-nez"))
            throw new AssertionError("existing direct-touch exclusion changed");
        int[] addresses = new int[code.size()]; address=0;
        for(int n=0;n<code.size();n++){addresses[n]=address;address+=code.get(n).getCodeUnits();}
        int nullTarget=positions.get(addresses[start-1]+((OffsetInstruction)code.get(start-1)).getCodeOffset());
        Reference nr=reference(code.get(nullTarget));
        if(!(nr instanceof FieldReference) || !((FieldReference)nr).getName().equals("mTapDetector"))
            throw new AssertionError("direct touch no longer skips zoom only");
        int[] registers=new int[m.getImplementation().getRegisterCount()];
        int result=0;
        for(int pc=start, steps=0;steps<32;steps++) {
            Instruction i=code.get(pc);Reference r=reference(i);String op=i.getOpcode().name;
            if(r instanceof FieldReference && ((FieldReference)r).getName().equals("mTapDetector")) return false;
            if(r instanceof MethodReference) {
                MethodReference call=(MethodReference)r;
                if(call.getDefiningClass().equals("Landroid/view/ScaleGestureDetector;")
                        && call.getName().equals("onTouchEvent")) return true;
                if(call.getName().equals("getSource") && call.getDefiningClass().equals("Landroid/view/MotionEvent;")) result=source;
                else if(call.getDefiningClass().equals("Lcom/termux/x11/input/LocalPinchZoom;")
                        && call.getName().equals("shouldHandle")) {
                    int reg=((FiveRegisterInstruction)i).getRegisterC();
                    result=(Boolean)Class.forName("com.termux.x11.input.LocalPinchZoom")
                        .getMethod("shouldHandle",int.class).invoke(null,registers[reg]) ? 1 : 0;
                } else throw new AssertionError("unexpected call in actual zoom gate: "+call);
            } else if(op.equals("move-result")) registers[((OneRegisterInstruction)i).getRegisterA()]=result;
            else if(op.equals("if-eqz")) {
                if(registers[((OneRegisterInstruction)i).getRegisterA()]==0) {
                    pc=positions.get(addresses[pc]+((OffsetInstruction)i).getCodeOffset());continue;
                }
            } else if(!op.equals("iget-object")) throw new AssertionError("unexpected zoom gate opcode: "+op);
            pc++;
        }
        throw new AssertionError("zoom dispatch did not finish within bound");
    }
    public static void main(String[] args) throws Exception {
        DexFile dex=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28));
        Method m=target(dex);
        int[] sources={0x1002,0x100008,0x2002,0x20004,0x10100a,0x3002,0x21006,0,2,0x4002};
        boolean[] wants={true,false,false,false,false,false,false,false,false,false};
        int failed=0;
        for(int n=0;n<sources.length;n++){
            boolean actual=reachesZoom(m,sources[n]);
            if(actual!=wants[n]){System.out.println("FAIL source=0x"+Integer.toHexString(sources[n])+" zoom="+actual+" want="+wants[n]);failed++;}
        }
        if(failed>0)throw new AssertionError(failed+" unexpected local zoom routes");
        System.out.println("PASS 10 literal source routes; existing direct-touch exclusion preserved");
    }
}
