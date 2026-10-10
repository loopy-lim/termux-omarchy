"""Verbatim production methods plus real pinned Swipe/Tap/Trackpad strategies.

Android GestureDetector, capture, rendering and native effects are stubbed.
This replay does not prove Android event routing or a physical gesture.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
from tooling import extract, java_tools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true",
                        help="expect the pre-lifecycle source to fail specific regression cases")
    args = parser.parse_args()
    base = ROOT / "input/history/scroll/TouchInputHandler.java"
    source = base if args.baseline else ROOT / "input/src/com/termux/x11/input/TouchInputHandler.java"
    raw = source.read_bytes()
    if not args.baseline:
        assert hashlib.sha256(raw).hexdigest() == "e8ce4ee270fe24e775efb926d4e6df472d170c47285c041b4054049042ee940b"
    text = raw.decode()
    signatures = ["boolean isDexEvent(MotionEvent event)",
                  "public boolean handleTouchEvent(View view0, View view, MotionEvent event)",
                  "private static boolean hasPointerCapture(View view)",
                  "public void setCapturingEnabled(boolean enabled)",
                  "private void moveCursorByOffset(float deltaX, float deltaY)",
                  "private boolean onSwipe()"]
    gestures = ["public boolean onScroll(MotionEvent e1, MotionEvent e2, float distanceX, float distanceY)",
                "public boolean onDown(MotionEvent e)", "public void onTap(int pointerCount, float x, float y)",
                "public void onLongPress(int pointerCount, float x, float y)",
                "private int mouseButtonFromPointerCount(int pointerCount)",
                "private boolean screenPointLiesOutsideImageBoundary(float screenX, float screenY)"]
    methods = {s: extract(text, s) for s in signatures}
    methods.update({s: extract(text, s, text.index("private class GestureListener")) for s in gestures})
    tools = java_tools()
    with tempfile.TemporaryDirectory(prefix="termux-omarchy-lifecycle-") as directory:
        out = Path(directory)
        for path in (HERE / "stubs").rglob("*.java"):
            target = out / "src" / path.relative_to(HERE / "stubs")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        package = out / "src/com/termux/x11/input"
        for name in ("SwipeDetector.java", "TapGestureDetector.java", "InputStrategyInterface.java"):
            path = ROOT / "input/upstream/lorie/src/main/java/com/termux/x11/input" / name
            (package / name).write_bytes(path.read_bytes())
        for name in ("PhysicalTouchpadMotion.java", "LocalPinchZoom.java"):
            (package / name).write_bytes((ROOT / "input/src/com/termux/x11/input" / name).read_bytes())
        replay = (HERE / "Replay.template.java").read_text()
        replay = replay.replace("/*__OUTER_METHODS__*/", "\n\n".join(methods[s] for s in signatures))
        replay = replay.replace("/*__GESTURE_METHODS__*/", "\n\n".join(methods[s] for s in gestures))
        (package / "Replay.java").write_text(replay)
        subprocess.run([tools["javac"], "-Xlint:all", "-d", str(out / "classes"),
                        *map(str, sorted((out / "src").rglob("*.java")))], check=True, timeout=30)
        result = subprocess.run([tools["java"], "-cp", str(out / "classes"),
                                 "com.termux.x11.input.Replay"], capture_output=True, text=True, timeout=15)
        print("\n".join(line for line in result.stdout.splitlines() if not line.startswith("TRACE ")))
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        assert source.read_bytes() == raw, "production source changed during replay"
        if args.baseline:
            assert result.returncode == 1 and "FAIL " in result.stdout, "expected baseline failure missing"
            print("PASS expected RED pre-lifecycle source")
        else:
            assert result.returncode == 0, "lifecycle replay failed"


if __name__ == "__main__":
    main()
