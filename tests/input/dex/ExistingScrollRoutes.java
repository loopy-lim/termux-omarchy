import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.iface.*;
import com.android.tools.smali.dexlib2.iface.instruction.*;
import java.io.File;
import java.util.*;
public final class ExistingScrollRoutes {
 public static void main(String[]args)throws Exception{
  DexFile d=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28));Method m=null;
  for(ClassDef c:d.getClasses())if(c.getType().equals(DexScrollTest.OWNER))m=DexScrollTest.scroll(c);
  if(m==null)throw new AssertionError("existing-scroll");List<Instruction>a=DexScrollTest.instructions(m);
  DexScrollTest.check(DexScrollTest.guard(a,1,2,0x100008,1,true),"existing-single-move");
  int[][]no={{0,2,0x100008,1},{2,2,0x100008,1},{3,2,0x100008,1},{1,0,0x100008,1},{1,1,0x100008,1},{1,3,0x100008,1},{1,6,0x100008,1},{1,7,0x100008,1},{1,2,0x1002,1},{1,2,0x10100a,1},{1,2,0x2002,3},{1,2,0x20004,3},{1,2,0,1},{1,2,0x100008,0},{1,2,0x100008,2},{1,2,0x100008,3}};
  for(int[]v:no)DexScrollTest.check(!DexScrollTest.guard(a,v[0],v[1],v[2],v[3],true),"existing-ineligible");
  DexScrollTest.check(!DexScrollTest.guard(a,1,2,0x100008,1,false),"existing-other-strategy");System.out.println("PASS 18 existing packaged onScroll guard routes using original DexScrollTest interpreter");
 }
}
