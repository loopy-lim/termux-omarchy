#!/usr/bin/env python3
"""Compile the actual production method bodies, replacing only Android effects with fakes."""
import argparse,hashlib,json,pathlib,subprocess,sys,tempfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from tooling import java_tools
TOOLS=java_tools()
BASE=pathlib.Path(__file__).resolve().parents[3]

def extract(text,signature,start=0):
    at=text.index(signature,start);brace=text.index('{',at);depth=0;state='code';i=brace
    while i<len(text):
        c=text[i];n=text[i:i+2]
        if state=='line':
            if c=='\n':state='code'
        elif state=='block':
            if n=='*/':state='code';i+=1
        elif state in ('string','char'):
            if c=='\\':i+=1
            elif c==('"' if state=='string' else "'"):state='code'
        elif n=='//':state='line';i+=1
        elif n=='/*':state='block';i+=1
        elif c=='"':state='string'
        elif c=="'":state='char'
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[at:i+1]
        i+=1
    raise ValueError('method-braces')

def main():
    a=argparse.ArgumentParser();a.add_argument('--source',type=pathlib.Path,default=BASE/'input/src/com/termux/x11/input/TouchInputHandler.java');args=a.parse_args()
    work=tempfile.TemporaryDirectory(prefix='termux-omarchy-scroll-')
    text=args.source.read_text();scroll=extract(text,'public boolean onScroll(MotionEvent e1, MotionEvent e2, float distanceX, float distanceY)',text.index('private class GestureListener'))
    swipe=extract(text,'private boolean onSwipe()')
    out=pathlib.Path(work.name)
    android=out/'android/view';android.mkdir(parents=True)
    (android/'InputDevice.java').write_text('package android.view; public final class InputDevice { public static final int SOURCE_TOUCHPAD=0x100008,SOURCE_TOUCHSCREEN=0x1002; }\n')
    (android/'MotionEvent.java').write_text('''package android.view;
public final class MotionEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2,ACTION_CANCEL=3,TOOL_TYPE_FINGER=1;
 private final int count,action,source,tool;
 public MotionEvent(int c,int a,int s,int t){count=c;action=a;source=s;tool=t;}
 public int getPointerCount(){return count;} public int getActionMasked(){return action&255;}
 public int getActionIndex(){return (action>>8)&255;} public int getSource(){return source;} public int getToolType(int i){if(i<0||i>=count)throw new AssertionError("invalid tool index");return tool;}
 public float getX(){return 10;} public float getY(){return 20;}
}
''')
    template=(BASE/'tests/input/scroll/ScrollHarness.template').read_text()
    policy='import com.termux.x11.input.PhysicalTouchpadMotion;' if 'PhysicalTouchpadMotion.' in scroll else ''
    java=template.replace('/*__POLICY_IMPORT__*/',policy).replace('/*__PRODUCTION_ON_SWIPE__*/',swipe).replace('/*__PRODUCTION_ON_SCROLL__*/',scroll)
    (out/'ScrollHarness.java').write_text(java)
    sources=[android/'InputDevice.java',android/'MotionEvent.java',out/'ScrollHarness.java']
    if policy:sources.append(BASE/'input/src/com/termux/x11/input/PhysicalTouchpadMotion.java')
    subprocess.run([TOOLS['javac'],'-Xlint:all','-d',str(out/'classes'),*map(str,sources)],check=True,timeout=30)
    r=subprocess.run([TOOLS['java'],'-cp',str(out/'classes'),'ScrollHarness'],text=True,capture_output=True,timeout=10)
    (out/'result.txt').write_text(r.stdout+r.stderr)
    (out/'receipt.json').write_text(json.dumps({'sourceSHA256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'productionOnScrollSHA256':hashlib.sha256(scroll.encode()).hexdigest(),'productionOnSwipeSHA256':hashlib.sha256(swipe.encode()).hexdigest(),'methodBodySource':'verbatim extracted from supplied production source','exitCode':r.returncode},indent=2)+'\n')
    print(r.stdout,end='');work.cleanup();raise SystemExit(r.returncode)
if __name__=='__main__':main()
