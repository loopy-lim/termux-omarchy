import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.iface.*;
import com.android.tools.smali.dexlib2.iface.instruction.*;
import java.io.File;
import java.util.*;
/** Execute the original incoming GOTO, then the packaged guard; catches labels left on old IGET. */
public final class BranchEntryTest {
 public static void main(String[]args)throws Exception{
  Method m=DexLifecycleTest.method(DexLifecycleTest.classes(DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28))).get(DexLifecycleTest.OUTER),"handleTouchEvent");
  List<Instruction>a=DexLifecycleTest.code(m);int start=DexLifecycleTest.rawStart(a),end=DexLifecycleTest.field(a,"mScroller"),incoming=-1;
  for(int i=0;i<start;i++)if(a.get(i).getOpcode()==Opcode.GOTO&&DexLifecycleTest.target(a,i)>=start&&DexLifecycleTest.target(a,i)<=end){if(incoming>=0)throw new AssertionError("incoming-unique");incoming=i;}
  if(incoming<0)throw new AssertionError("incoming-goto-missing");
  // One real packaged GOTO step, with its actual relative branch offset.
  int destination=DexLifecycleTest.target(a,incoming);
  boolean[]physical=DexLifecycleTest.execute(a,destination,end,1,2,0x100008,1,true);
  if(!Arrays.equals(physical,new boolean[]{false,true,true}))throw new AssertionError("incoming-GOTO-bypassed-raw-guard");
  if(destination!=start)throw new AssertionError("incoming-GOTO-must-target-guard-entry");
  boolean[]other=DexLifecycleTest.execute(a,destination,end,1,2,0x100008,1,false);
  if(!Arrays.equals(other,new boolean[]{true,true,true}))throw new AssertionError("incoming-GOTO-other-strategy-changed");
  System.out.println("PASS original packaged GOTO reaches guard entry and executes physical/other-strategy routes; trackpad fallthrough separately covered by37 lifecycle routes");
 }
}
