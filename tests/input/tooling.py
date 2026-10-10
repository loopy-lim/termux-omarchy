"""Host test tools; JAVA_HOME or PATH, never a workstation-specific location."""
import os
from pathlib import Path
import shutil
import subprocess


def java_tools():
    home = os.environ.get("JAVA_HOME")
    result = {}
    for tool in ("java", "javac"):
        candidate = str(Path(home) / "bin" / tool) if home else shutil.which(tool)
        if not candidate or not Path(candidate).is_file():
            raise RuntimeError("JDK 17+ required: set JAVA_HOME or add java/javac to PATH")
        result[tool] = candidate
    return result


def lint_flags(javac):
    help_result = subprocess.run([javac, "--help-lint"], capture_output=True, text=True, timeout=10)
    return ["-Xlint:all,-this-escape" if "this-escape" in help_result.stdout else "-Xlint:all", "-Werror"]


def extract(text, signature, start=0):
    at = text.index(signature, start)
    brace = text.index('{', at)
    depth, state, i = 0, 'code', brace
    while i < len(text):
        c, pair = text[i], text[i:i+2]
        if state == 'line':
            if c == '\n': state = 'code'
        elif state == 'block':
            if pair == '*/': state = 'code'; i += 1
        elif state in ('string', 'char'):
            if c == '\\': i += 1
            elif c == ('"' if state == 'string' else "'"): state = 'code'
        elif pair == '//': state = 'line'; i += 1
        elif pair == '/*': state = 'block'; i += 1
        elif c == '"': state = 'string'
        elif c == "'": state = 'char'
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return text[at:i+1]
        i += 1
    raise ValueError('method-braces')
