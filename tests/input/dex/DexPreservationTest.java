import com.android.tools.smali.baksmali.Adaptors.ClassDefinition;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.baksmali.formatter.BaksmaliWriter;
import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.iface.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Compare decoded executable semantics, annotations and debug metadata across all classes. */
public final class DexPreservationTest {
    static String disassemble(ClassDef c) throws Exception {
        BaksmaliOptions o=new BaksmaliOptions();o.apiLevel=28;o.sequentialLabels=true;o.accessorComments=false;
        StringWriter text=new StringWriter();BaksmaliWriter writer=new BaksmaliWriter(text);
        ClassDefinition definition=new ClassDefinition(o,c);definition.writeTo(writer);writer.close();
        if(definition.hadValidationErrors())throw new AssertionError("invalid DEX class: "+c.getType());
        return text.toString();
    }
    static String excludeDispatch(String text) {
        return text.replaceFirst("(?s)\\.method public handleTouchEvent\\(Landroid/view/View;Landroid/view/View;Landroid/view/MotionEvent;\\)Z.*?\\.end method","");
    }
    public static void main(String[] args) throws Exception {
        DexFile a=DexFileFactory.loadDexFile(new File(args[0]),Opcodes.forApi(28));
        DexFile b=DexFileFactory.loadDexFile(new File(args[1]),Opcodes.forApi(28));
        Map<String,ClassDef> after=new HashMap<>();for(ClassDef c:b.getClasses())after.put(c.getType(),c);
        if(after.size()!=a.getClasses().size()+1)throw new AssertionError("unexpected class count");
        int same=0,changed=0;
        for(ClassDef c:a.getClasses()) {
            ClassDef next=after.remove(c.getType());if(next==null)throw new AssertionError("class removed");
            String beforeText=disassemble(c),afterText=disassemble(next);
            if(beforeText.equals(afterText)){same++;continue;}
            if(!c.getType().equals("Lcom/termux/x11/input/TouchInputHandler;"))throw new AssertionError("unexpected class change: "+c.getType());
            if(!excludeDispatch(beforeText).equals(excludeDispatch(afterText)))throw new AssertionError("other input methods or fields changed");
            Files.writeString(Path.of(args[2],"TouchInputHandler-before.smali"),beforeText);
            Files.writeString(Path.of(args[2],"TouchInputHandler-after.smali"),afterText);changed++;
        }
        if(changed!=1 || after.size()!=1 || !after.containsKey("Lcom/termux/x11/input/LocalPinchZoom;"))throw new AssertionError("unexpected DEX change set");
        ClassDef policy=after.values().iterator().next();
        DexFile compiled=DexFileFactory.loadDexFile(new File(args[3]),Opcodes.forApi(28));
        if(compiled.getClasses().size()!=1 || !disassemble(policy).equals(disassemble(compiled.getClasses().iterator().next())))
            throw new AssertionError("packaged policy differs from the compiled source");
        Files.writeString(Path.of(args[2],"LocalPinchZoom.smali"),disassemble(policy));
        System.out.println("PASS "+same+" original classes unchanged; only handleTouchEvent and one new pure policy class differ");
    }
}
