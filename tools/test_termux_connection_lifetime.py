#!/usr/bin/env python3
"""Exercise the duplicate-broadcast leak and the exact APK helper lifecycle."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
JAVA=Path(os.environ.get('JAVA_HOME','/Applications/Android Studio.app/Contents/jbr/Contents/Home'))/'bin'
with tempfile.TemporaryDirectory(prefix='loopy-connection-test-') as directory:
    sources=[ROOT/'native/termux-x11/connection-lifetime/ConnectionLifetime.java',
             *sorted((ROOT/'tests/termux-x11-connection-lifetime').rglob('*.java'))]
    subprocess.run([str(JAVA/'javac'),'-d',directory,*map(str,sources)],check=True)
    command=[str(JAVA/'java'),'-cp',directory,'ConnectionLifetimeTest']
    red=subprocess.run([*command,'legacy'],capture_output=True,text=True)
    assert red.returncode and 'duplicate-broadcast-registration-growth: 60000' in red.stderr
    print('PASS baseline reproduces 60000 retained death registrations')
    subprocess.run(command,check=True)
