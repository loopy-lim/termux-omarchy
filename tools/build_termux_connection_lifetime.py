#!/usr/bin/env python3
"""Build an additive lifecycle fix atop the installed custom X11 APK; no device mutation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK = Path('/Users/loopy/Library/Android/sdk')
JAVA = Path('/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin')
BASE = ROOT / 'build/termux-x11-keybridge-direct-input-20261010-01/artifact/LoopyOmarchy-TermuxX11-keybridge-direct-input-candidate-20261010-01.apk'
SOURCE = ROOT / 'native/termux-x11/connection-lifetime'
OUT = ROOT / 'build/termux-x11-connection-lifetime-20261012'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    assert sha(BASE) == '64ed17827121d6118bb001ce1bc85ba030d475a5f32f6f57a695d83abaa7fd71'
    OUT.mkdir(exist_ok=False)
    for name in ('classes', 'helper-dex'): (OUT/name).mkdir()
    pins = json.loads((ROOT/'build/termux-x11-trackpad-lifecycle-20261009-01/toolchain-pins.json').read_text())
    assert all(sha(Path(p)) == h for p,h in pins['sha256'].items())
    cp = pins['classpath']; android=SDK/'platforms/android-36/android.jar'; build=SDK/'build-tools/36.1.0'
    env=os.environ.copy(); env['JAVA_HOME']=str(JAVA.parent)
    def run(name, args, red=False):
        result=subprocess.run(list(map(str,args)),capture_output=True,env=env,timeout=90)
        (OUT/(name+'.txt')).write_bytes(result.stdout+result.stderr)
        assert (result.returncode != 0) if red else (result.returncode == 0), name
        print(name+': '+('EXPECTED_RED' if red else 'PASS'),flush=True)
        return result.stdout.decode()
    run('compile-helper',[JAVA/'javac','--release','8','-cp',android,'-d',OUT/'classes',SOURCE/'ConnectionLifetime.java'])
    run('compile-patcher',[JAVA/'javac','-cp',cp,'-d',OUT/'classes',SOURCE/'PatchConnectionDex.java'])
    run('dex-helper',[build/'d8','--min-api','26','--lib',android,'--output',OUT/'helper-dex',*sorted((OUT/'classes/com/termux/x11/utils').glob('*.class'))])
    with zipfile.ZipFile(BASE) as z: (OUT/'original.dex').write_bytes(z.read('classes.dex'))
    tool=[JAVA/'java','-cp',str(OUT/'classes')+':'+cp,'PatchConnectionDex',OUT/'original.dex']
    run('installed-dex-red',tool,red=True)
    run('patch-and-verify',tool+[OUT/'helper-dex/classes.dex',OUT/'patched.dex'])
    signature=lambda n: bool(re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))',n,re.I))
    with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(OUT/'unsigned.apk','x') as dst:
        for item in src.infolist():
            if not signature(item.filename): dst.writestr(copy.copy(item),(OUT/'patched.dex').read_bytes() if item.filename=='classes.dex' else src.read(item))
    run('align',[build/'zipalign','-P','16','4',OUT/'unsigned.apk',OUT/'aligned.apk'])
    signing=ROOT/'build/termux-x11-trackpad-zoom-20261009-01/inputs'
    config=(signing/'official-public-signing.gradle').read_text()
    env['LOOPY_PUBLIC_STORE_PASSWORD']=re.search(r"storePassword '([^']+)'",config)[1]
    env['LOOPY_PUBLIC_KEY_PASSWORD']=re.search(r"keyPassword '([^']+)'",config)[1]
    apk=OUT/'LoopyOmarchy-TermuxX11-connection-lifetime.apk'
    run('sign',[build/'apksigner','sign','--ks',signing/'termux-public-dev-keystore.jks','--ks-key-alias',re.search(r"keyAlias '([^']+)'",config)[1],'--ks-pass','env:LOOPY_PUBLIC_STORE_PASSWORD','--key-pass','env:LOOPY_PUBLIC_KEY_PASSWORD','--out',apk,OUT/'aligned.apk'])
    cert=run('verify-signature',[build/'apksigner','verify','--verbose','--print-certs',apk])
    assert re.findall(r'Signer #\d+ certificate SHA-256 digest: ([a-f0-9]+)',cert)==['b6da01480eefd5fbf2cd3771b8d1021ec791304bdd6c4bf41d3faabad48ee5e1']
    run('verify-alignment',[build/'zipalign','-c','-P','16','4',apk])
    with zipfile.ZipFile(BASE) as a,zipfile.ZipFile(apk) as b:
        names={n for n in a.namelist() if not signature(n)}
        assert names=={n for n in b.namelist() if not signature(n)}
        changed=[n for n in names if a.read(n)!=b.read(n)]
        assert changed==['classes.dex']
    receipt=dict(status='HOST_VERIFIED',baseSHA256=sha(BASE),apkSHA256=sha(apk),changedPayloads=changed,unchangedPayloadCount=len(names)-1,deviceVerified=False,sources={str(p.relative_to(ROOT)):sha(p) for p in [*SOURCE.glob('*.java'),Path(__file__)]})
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__': main()
