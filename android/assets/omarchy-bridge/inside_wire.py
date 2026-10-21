"""Bounded LIG1/LIP1/LIA1/LIR1 transport. Pixels and private input are never persisted."""
import base64
import copy
import os
import re
import socket
import stat
import struct
import zlib

MAX_CONTROL=4096
MAX_FRAME=64*1024*1024
MAX_BODY=MAX_FRAME+4104
ACTIONS={name:i+1 for i,name in enumerate(('OPEN','RESIZE','FOCUS','POINTER_MOVE','POINTER_BUTTON','KEY','RELEASE_ALL','CLOSE','KEY_REPEAT','SCROLL','OPEN_ZLIB','OPEN_URL'))}
TYPES={1:'HELLO',2:'OPENED',3:'ACK',4:'FRAME',5:'CLOSED',6:'ERROR',7:'FRAME_ZLIB'}


def is_open(action):return action in ('OPEN','OPEN_ZLIB','OPEN_URL')


def integer(value,lo=1,hi=2**63-1):
    if type(value) is not int or not lo<=value<=hi:raise ValueError('inside-integer')
    return value


def text(value,pattern,maximum):
    if type(value) is not str or len(value)>maximum or not re.fullmatch(pattern,value):raise ValueError('inside-text')
    raw=value.encode('ascii');return struct.pack('>H',len(raw))+raw


def stamp(value):
    return text(value['session'],r'[A-Za-z0-9-]{1,64}',64)+text(value['window'],r'[0-9a-f]{32}',32)+struct.pack('>q',integer(value['generation']))


def target(value):
    if value['uid']==2000:raise ValueError('inside-target-uid')
    return text(value['component'],r'[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+',512)+struct.pack('>i',integer(value['uid'],1,2**31-1))


def geometry(value):
    return struct.pack('>qiii',integer(value['epoch']),integer(value['width'],1,4096),integer(value['height'],1,4096),integer(value['density'],72,640))


def task(value):
    return stamp(value['stamp'])+target(value['target'])+struct.pack('>ii',integer(value['task_id'],1,2**31-1),integer(value['display_id'],1,2**31-1))


def packet(body):
    if not 0<len(body)<=MAX_CONTROL:raise ValueError('inside-control-size')
    return struct.pack('>i',len(body))+body


def command(value):
    action=value['action'];number=ACTIONS.get(action)
    if number is None:raise ValueError('inside-action')
    tail=b''
    if action=='OPEN_URL':
        from inside_uri import initial
        uri=initial(value['target'],value.get('initial_url')).encode('ascii')
        compact=value.get('compact')
        if type(compact) is not bool:raise ValueError('inside-compression')
        tail=struct.pack('>BH',int(compact),len(uri))+uri
    elif value.get('initial_url') is not None or 'compact' in value:
        raise ValueError('inside-uri-action')
    tid,did=value['task_id'],value['display_id'];integer(tid,0,2**31-1);integer(did,0,2**31-1)
    if (tid==0)!=(did==0) or (is_open(action) and tid!=0) or (not is_open(action) and action!='CLOSE' and tid==0):raise ValueError('inside-resource')
    g=value['geometry'];x,y,code,pressed=value['x'],value['y'],value['code'],value['pressed']
    integer(x,0,4095);integer(y,0,4095);integer(code,0,767)
    if type(pressed) is not bool:raise ValueError('inside-pressed')
    if action in ('POINTER_MOVE','POINTER_BUTTON','SCROLL'):
        if x>=g['width'] or y>=g['height']:raise ValueError('inside-pointer')
        if action=='POINTER_BUTTON':integer(code,1,5)
        elif code!=0 or pressed:raise ValueError('inside-pointer-action')
    else:
        if x or y:raise ValueError('inside-coordinate')
        if action in ('KEY','KEY_REPEAT'):
            integer(code,1,767)
            if action=='KEY_REPEAT' and not pressed:raise ValueError('inside-repeat')
        elif code or (action!='FOCUS' and pressed):raise ValueError('inside-command-value')
    body=struct.pack('>IBB',0x4c495031,1,number)+stamp(value['stamp'])+struct.pack('>q',integer(value['sequence']))+target(value['target'])+struct.pack('>ii',tid,did)+geometry(g)+struct.pack('>iiiB',x,y,code,int(pressed))
    if action=='SCROLL' and value['scroll_x']==0 and value['scroll_y']==0:raise ValueError('inside-scroll')
    if action=='SCROLL':body+=struct.pack('>ii',integer(value['scroll_x'],-120000,120000),integer(value['scroll_y'],-120000,120000))
    return packet(body+tail)


def release(value):
    return packet(struct.pack('>IB',0x4c494131,1)+task(value['task'])+geometry(value['geometry'])+struct.pack('>q',integer(value['sequence'])))


class Cursor:
    def __init__(self,raw):self.raw=raw;self.at=0
    def take(self,size):
        if self.at+size>len(self.raw):raise ValueError('inside-truncated')
        raw=self.raw[self.at:self.at+size];self.at+=size;return raw
    def unpack(self,fmt):return struct.unpack('>'+fmt,self.take(struct.calcsize('>'+fmt)))
    def i(self,lo=1,hi=2**31-1):return integer(self.unpack('i')[0],lo,hi)
    def q(self,lo=1):return integer(self.unpack('q')[0],lo)
    def byte(self,mask):
        value=self.unpack('B')[0]
        if value&~mask:raise ValueError('inside-flags')
        return value
    def text(self,pattern,maximum):
        size=self.unpack('H')[0]
        if not 0<size<=maximum:raise ValueError('inside-text-size')
        try:value=self.take(size).decode('ascii')
        except UnicodeError:raise ValueError('inside-text') from None
        text(value,pattern,maximum);return value
    def stamp(self):return dict(session=self.text(r'[A-Za-z0-9-]{1,64}',64),window=self.text(r'[0-9a-f]{32}',32),generation=self.q())
    def target(self):
        value=dict(component=self.text(r'[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+',512),uid=self.i());target(value);return value
    def geometry(self):return dict(epoch=self.q(),width=self.i(1,4096),height=self.i(1,4096),density=self.i(72,640))
    def task(self):return dict(stamp=self.stamp(),target=self.target(),task_id=self.i(),display_id=self.i())
    def observation(self):
        value=dict(task=self.task(),top_uid=self.i());flags=self.byte(7)
        value.update(visible=bool(flags&1),running=bool(flags&2),focused=bool(flags&4));return value
    def done(self):
        if self.at!=len(self.raw):raise ValueError('inside-trailing')


def metadata(kind,raw):
    c=Cursor(raw);row=dict(type=TYPES[kind])
    if kind==1:
        row.update(session=c.text(r'[A-Za-z0-9-]{1,64}',64),app_uid=c.i(),shell_uid=c.i(),shell_pid=c.i(),birth=c.q(),generation=c.q(),caps=c.i())
        count=c.unpack('H')[0]
        if count>256 or row['shell_uid']!=2000 or row['app_uid']==2000 or row['caps']!=127:raise ValueError('inside-capabilities')
        keys=[integer(c.unpack('H')[0],1,767) for _ in range(count)]
        if keys!=sorted(set(keys)):raise ValueError('inside-key-capabilities')
        row['keys']=keys
    elif kind in (2,3):
        row.update(observation=c.observation(),geometry=c.geometry(),request_sequence=c.q(),inputs_released=bool(c.byte(1)))
        if kind==2 and row['inputs_released']:raise ValueError('inside-opened-release')
    elif kind in (4,7):
        row.update(task=c.task(),geometry=c.geometry(),sequence=c.q(),stride=c.i(),bytes=c.q(),format=c.i())
        g=row['geometry']
        if row['format']!=1 or not g['width']*4<=row['stride']<=g['width']*4+4096 or row['bytes']!=row['stride']*g['height'] or row['bytes']>MAX_FRAME:raise ValueError('inside-frame-layout')
        if kind==7:row['encoded_bytes']=integer(c.q(),1,row['bytes']-1)
    elif kind==5:
        row.update(stamp=c.stamp(),task_id=c.i(0),display_id=c.i(0));flags=c.byte(7)
        if (row['task_id']==0)!=(row['display_id']==0):raise ValueError('inside-closed-resource')
        row.update(task_removed=bool(flags&1),display_removed=bool(flags&2),inputs_released=bool(flags&4))
    else:row.update(request_sequence=c.q(0),code=integer(c.unpack('B')[0],1,13))
    c.done();return row


def grant_metadata(raw):
    c=Cursor(raw)
    if c.unpack('IB')!=(0x4c494731,1):raise ValueError('inside-grant-version')
    row=dict(type='GRANT',session=c.text(r'[A-Za-z0-9-]{1,64}',64),app_uid=c.i(),app_pid=c.i(),shell_uid=c.i(),shell_pid=c.i(),birth=c.q(),generation=c.q())
    if row['app_uid']==2000 or row['shell_uid']!=2000 or row['app_pid']==row['shell_pid']:raise ValueError('inside-grant-identity')
    c.done();return row


class Decoder:
    def __init__(self):self.buffer=bytearray();self.granted=False
    def feed(self,data):
        if type(data) is not bytes or len(data)>65536:raise ValueError('inside-chunk')
        self.buffer.extend(data);rows=[];frames=0
        while len(self.buffer)>=4:
            length=struct.unpack_from('>i',self.buffer)[0]
            if not 8<=length<=MAX_BODY:raise ValueError('inside-body-size')
            if not self.granted:
                if length<40 or length>MAX_CONTROL:raise ValueError('inside-grant-size')
                if len(self.buffer)<9:break
                if struct.unpack_from('>IB',self.buffer,4)!=(0x4c494731,1):raise ValueError('inside-grant-required')
                if len(self.buffer)<4+length:break
                rows.append(grant_metadata(bytes(self.buffer[4:4+length])));del self.buffer[:4+length];self.granted=True;continue
            if len(self.buffer)<12:break
            magic,version,kind,size=struct.unpack_from('>IBBH',self.buffer,4)
            if magic!=0x4c495231 or version!=1 or kind not in TYPES or size>MAX_CONTROL or length<8+size:raise ValueError('inside-header')
            if kind not in (4,7) and length!=8+size:raise ValueError('inside-nonframe-payload')
            if len(self.buffer)<12+size:break
            row=metadata(kind,bytes(self.buffer[12:12+size]))
            payload=row['encoded_bytes'] if kind==7 else row['bytes'] if kind==4 else 0
            if length!=8+size+payload:raise ValueError('inside-payload-size')
            if len(self.buffer)<4+length:break
            if kind in (4,7):
                if frames:raise ValueError('inside-frame-batch')
                frames+=1;pixels=bytes(self.buffer[12+size:4+length])
                if kind==7:
                    try:
                        decoder=zlib.decompressobj(15);pixels=decoder.decompress(pixels,row['bytes']+1)
                    except zlib.error:raise ValueError('inside-compressed-frame') from None
                    if len(pixels)!=row['bytes'] or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('inside-compressed-frame')
                    del row['encoded_bytes'];row['type']='FRAME'
                row['data']=pixels
            del self.buffer[:4+length];rows.append(row)
        if len(self.buffer)>MAX_BODY+4:raise ValueError('inside-buffer-size')
        return rows
    def finish(self):
        if self.buffer:raise ValueError('inside-truncated')


class Output:
    def __init__(self):self.buffer=bytearray();self.granted=False
    @property
    def pending(self):return bool(self.buffer)
    def put(self,data):
        if type(data) is not bytes or len(data)>4100 or len(self.buffer)+len(data)>262144:raise ValueError('inside-output-bound')
        self.buffer.extend(data)
    def flush(self,sock):
        for _ in range(32):
            if not self.buffer:return
            try:count=sock.send(self.buffer)
            except BlockingIOError:return
            if count<=0:raise OSError('inside-output-closed')
            del self.buffer[:count]


class Retirement:
    def __init__(self):self.pending=None
    def accept(self,frame):
        if self.pending is not None:raise ValueError('inside-frame-pending')
        self.pending=copy.deepcopy({k:frame[k] for k in ('task','geometry','sequence')})
    def copied(self,frame):
        header={k:frame[k] for k in ('task','geometry','sequence')}
        if header!=self.pending:raise ValueError('inside-retirement-mismatch')
        raw=release(self.pending);self.pending=None;return raw


def catalog(directory,token,encoded):
    text(token,r'[A-Za-z0-9-]{1,64}',64);text(encoded,r'[A-Za-z0-9_-]{1,1400}',1400)
    try:
        raw=base64.b64decode(encoded+'='*(-len(encoded)%4),altchars=b'-_',validate=True)
        component=raw.decode('ascii')
    except (ValueError,UnicodeError):raise ValueError('inside-component') from None
    if base64.urlsafe_b64encode(raw).decode().rstrip('=')!=encoded:raise ValueError('inside-component-encoding')
    text(component,r'[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+',512)
    directory=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        if os.fstat(directory).st_uid!=os.getuid():raise ValueError('inside-catalog-owner')
        name='apps-'+token+'.tsv';fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory)
        with os.fdopen(fd,'rb') as source:
            first=os.fstat(source.fileno())
            if not stat.S_ISREG(first.st_mode) or first.st_uid!=os.getuid() or first.st_size>65536:raise ValueError('inside-catalog')
            data=source.read(65537);last=os.fstat(source.fileno())
        current=os.stat(name,dir_fd=directory,follow_symlinks=False)
        ident=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
        if len(data)>65536 or ident(first)!=ident(last) or ident(last)!=ident(current):raise ValueError('inside-catalog-changed')
        matches=[]
        for line in data.decode('utf-8').splitlines():
            fields=line.split('\t')
            if len(fields)!=3 or not re.fullmatch('[0-9]{1,10}',fields[2]):raise ValueError('inside-catalog-schema')
            if fields[0]==component:matches.append(integer(int(fields[2]),1,2**31-1))
        if len(matches)!=1:raise ValueError('inside-catalog-target')
        value=dict(component=component,uid=matches[0]);target(value);return value
    finally:os.close(directory)


def birth(data,pid):
    if type(data) is not str or len(data)>4096:raise ValueError('inside-peer-stat')
    head,tail=data.rsplit(') ',1);number,_=head.split(' (',1);fields=tail.split()
    if int(number)!=pid or len(fields)<20 or fields[0] in ('Z','X','x'):raise ValueError('inside-peer-stat')
    return integer(int(fields[19]))


def peer_birth(pid,uid=2000):
    integer(pid,1,2**31-1);path='/proc/'+str(pid)
    with open(path+'/stat') as source:first=birth(source.read(4097),pid)
    if os.stat(path).st_uid!=uid:raise ValueError('inside-peer-owner')
    with open(path+'/stat') as source:last=birth(source.read(4097),pid)
    if first!=last or os.stat(path).st_uid!=uid:raise ValueError('inside-peer-replaced')
    return last


def socket_identity(sock,app_pid):
    # The connected kernel peer is the actual Loopy app hub, not the shell behind Binder.
    integer(app_pid,1,2**31-1)
    pid,uid,_=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    if uid!=os.getuid() or pid!=app_pid:raise ValueError('inside-app-peer')
    identity=os.fstat(sock.fileno())
    if not stat.S_ISSOCK(identity.st_mode):raise ValueError('inside-socket-type')
    return dict(app_pid=pid,app_uid=uid,socket_dev=identity.st_dev,socket_ino=identity.st_ino)


def check_peer(sock,identity):
    if socket_identity(sock,identity['app_pid'])!=identity:raise ValueError('inside-socket-replaced')


def connect(token):
    # Hub authenticates shell Binder UID/PID and writes GRANT before handing this FD over.
    # No direct cross-domain socket or independent app-denied shell /proc claim is made.
    text(token,r'[A-Za-z0-9-]{1,64}',64)
    value=os.environ.get('LOOPY_ANDROID_PID','')
    if not re.fullmatch(r'[1-9][0-9]{0,9}',value):raise ValueError('inside-app-pid')
    app_pid=integer(int(value),1,2**31-1);sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        sock.settimeout(2);sock.connect('\0loopy-inside-app-'+token)
        identity=socket_identity(sock,app_pid);sock.setblocking(False);return sock,identity
    except BaseException:sock.close();raise
