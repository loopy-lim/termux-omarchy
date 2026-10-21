#!/usr/bin/env python3
"""Sample actual SurfaceFlinger presentation timestamps, without reading pixels."""
import argparse,json,re,shlex,statistics,subprocess,time
from pathlib import Path

def summary(times):
    ordered=sorted(set(times))
    gaps=[(b-a)/1e6 for a,b in zip(ordered,ordered[1:])]
    if not gaps:return {'frames':len(ordered),'status':'NO_PRESENTATION_DATA'}
    return {'frames':len(ordered),'durationSeconds':(ordered[-1]-ordered[0])/1e9,
            'fps':(len(ordered)-1)*1e9/(ordered[-1]-ordered[0]),
            'p50ms':statistics.median(gaps),'p95ms':sorted(gaps)[int(.95*len(gaps))],
            'maxMs':max(gaps),'gapsOver34ms':sum(g>34 for g in gaps),
            'status':'PASS' if sorted(gaps)[int(.95*len(gaps))]<34 and max(gaps)<150 else 'BELOW_TARGET'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--serial',required=True);p.add_argument('--seconds',type=int,default=30);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not 5<=a.seconds<=120:p.error('seconds must be 5..120')
    if a.output.exists():p.error('output already exists')
    def shell(args):return subprocess.check_output(['adb','-s',a.serial,'shell',shlex.join(args)],timeout=10,text=True)
    layers=shell(['dumpsys','SurfaceFlinger','--list']).splitlines()
    candidates=[]
    for line in layers:
        if 'SurfaceView[com.termux.x11/com.termux.x11.MainActivity](BLAST)#' in line:
            candidates.append(re.sub(r'^RequestedLayerState\{','',line).split(' parentId=')[0])
    if len(candidates)!=1:raise RuntimeError('unique Termux:X11 presentation layer required')
    layer=candidates[0];frames={};start=time.monotonic();samples=0;initial=set()
    while time.monotonic()-start<a.seconds:
        raw=shell(['dumpsys','SurfaceFlinger','--latency',layer]);rows=[]
        for line in raw.splitlines()[1:]:
            parts=line.split()
            if len(parts)!=3:continue
            desired,present,ready=map(int,parts)
            if 0<present<9223372036854775807 and 0<ready<9223372036854775807:rows.append((present,ready,desired))
        if samples==0:initial={r[0] for r in rows}
        for present,ready,desired in rows:
            if present not in initial:frames[present]=(ready,desired)
        samples+=1;time.sleep(.5)
    result=dict(schema=1,serial=a.serial,layer=layer,sampledSeconds=time.monotonic()-start,samples=samples,
                presentation=summary(frames),pixelCapture=False,physicalInputLatencyMeasured=False)
    if frames:
        delays=sorted((present-ready)/1e6 for present,(ready,_) in frames.items())
        result['readyToPresentMs']={'p50':statistics.median(delays),'p95':delays[int(len(delays)*.95)],'max':max(delays)}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
