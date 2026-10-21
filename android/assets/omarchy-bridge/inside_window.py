"""Generic Android app pixels in an owned GTK3 Wayland window; no private content logs."""
import copy
import os
import time
import inside_wire as wire
import inside_input as inputs


class Session:
    """One authenticated connection, one accepted command and one borrowed frame at a time."""
    def __init__(self,token,window,uid,target,peer,geometry,clock=time.monotonic,compressed=False,initial_url=None):
        wire.text(token,r'[A-Za-z0-9-]{1,64}',64);wire.text(window,r'[0-9a-f]{32}',32)
        wire.integer(uid,1,99999);wire.target(target);wire.geometry(geometry)
        if uid==2000 or target['uid'] in (2000,uid) or target['uid']>=100000:raise ValueError('inside-target-admission')
        if peer['app_uid']!=uid:raise ValueError('inside-peer')
        if type(compressed) is not bool:raise ValueError('inside-compression')
        if initial_url is not None:
            from inside_uri import initial
            initial_url=initial(target,initial_url)
        self.initial_url=initial_url;self.compressed=compressed
        self.open_action='OPEN_URL' if initial_url is not None else 'OPEN_ZLIB' if compressed else 'OPEN'
        wire.integer(peer['app_pid'],1,2**31-1)
        self.token=token;self.window=window;self.uid=uid;self.target=copy.deepcopy(target);self.peer=copy.deepcopy(peer)
        self.geometry=copy.deepcopy(geometry);self.desired=copy.deepcopy(geometry);self.clock=clock
        self.output=wire.Output();self.retirement=wire.Retirement();self.input=inputs.InputState([])
        self.state='GRANT';self.backend=None;self.stamp=None;self.task=None;self.inflight=None;self.deadline=clock()+5
        self.sequence=0;self.frame_sequence=0;self.inputs=[];self.want_focus=False;self.remote_focus=False
        self.needs_retirement=False;self.needs_focus_off=False;self.closing=False
        self.pending_resize_frame=None
    def _send(self,intent):
        self.sequence+=1
        value=dict(stamp=self.stamp,sequence=self.sequence,target=self.target,task_id=self.task['task_id'] if self.task else 0,
            display_id=self.task['display_id'] if self.task else 0,geometry=self.geometry,x=0,y=0,code=0,pressed=False)
        value.update(intent);self.output.put(wire.command(value));self.inflight=copy.deepcopy(value)
        self.deadline=self.clock()+(15 if wire.is_open(value['action']) else 8)
    def _changed(self):return any(self.geometry[k]!=self.desired[k] for k in ('width','height','density'))
    def _enable(self):
        self.input.focused=self.state=='OPEN' and self.remote_focus and self.want_focus and not self.needs_retirement and not self.needs_focus_off and not self._changed() and not self.closing
    def _advance(self):
        if self.inflight is not None or self.state!='OPEN':return
        if self.needs_retirement:self._send(dict(action='RELEASE_ALL'))
        elif self.needs_focus_off:self._send(dict(action='FOCUS',pressed=False))
        elif self.closing:self._send(dict(action='CLOSE'))
        elif self._changed():
            geometry={**self.desired,'epoch':self.geometry['epoch']+1};self._send(dict(action='RESIZE',geometry=geometry))
        elif self.want_focus and not self.remote_focus:self._send(dict(action='FOCUS',pressed=True))
        elif self.inputs:self._send(self.inputs.pop(0))
        self._enable()
    def focus(self,focused):
        if type(focused) is not bool:raise ValueError('inside-focus')
        if focused==self.want_focus:return
        self.want_focus=focused
        if not focused:self._retire()
        self._advance()
    def _retire(self):
        self.pending_resize_frame=None;self.input.retire();self.inputs.clear();self.needs_retirement=True;self.needs_focus_off=True
    def resize(self,width,height,density):
        candidate=dict(epoch=self.geometry['epoch'],width=width,height=height,density=density);wire.geometry(candidate)
        if all(self.desired[k]==candidate[k] for k in ('width','height','density')):return
        self.desired=candidate;self._retire();self._advance()
    def send_input(self,intent):
        if intent is None:return
        if not self.input.focused or self.closing:return
        if intent['action'] not in ('POINTER_MOVE','POINTER_BUTTON','KEY','KEY_REPEAT','SCROLL'):raise ValueError('inside-input-action')
        if intent['action']=='POINTER_MOVE' and self.inputs and self.inputs[-1]['action']=='POINTER_MOVE':self.inputs[-1]=copy.deepcopy(intent)
        else:
            if len(self.inputs)>=64:raise ValueError('inside-input-queue')
            self.inputs.append(copy.deepcopy(intent))
        self._advance()
    def close(self):
        self.closing=True;self.want_focus=False;self._retire()
        if self.task is None:
            self.output.buffer.clear();self.inflight=None;self.state='ABANDONED';return
        self._advance()
    def check_timeout(self,now=None):
        if self.state in ('GRANT','HELLO') or self.inflight is not None:
            if (self.clock() if now is None else now)>self.deadline:raise ValueError('inside-deadline')
    def _observe(self,row,opened=False):
        seen=row['observation'];lease=seen['task'];command=self.inflight
        if command is None or row['request_sequence']!=command['sequence'] or row['geometry']!=command['geometry']:raise ValueError('inside-ack')
        if seen['top_uid']!=self.target['uid'] or not seen['visible'] or not seen['running']:raise ValueError('inside-target-unavailable')
        if lease['stamp']!=self.stamp or lease['target']!=self.target or (not opened and lease!=self.task):raise ValueError('inside-task')
        wire.task(lease);return command,lease,seen
    def receive(self,row,copy_frame=None):
        if self.state=='ABANDONED':raise ValueError('inside-abandoned')
        kind=row['type']
        if kind=='GRANT':
            if self.state!='GRANT' or row['session']!=self.token or any(row[k]!=self.peer[k] for k in ('app_uid','app_pid')) or row['shell_uid']!=2000:raise ValueError('inside-grant')
            wire.integer(row['shell_pid'],1,2**31-1);wire.integer(row['birth']);wire.integer(row['generation'])
            self.backend={k:row[k] for k in ('shell_uid','shell_pid','birth','generation')}
            self.state='HELLO';self.deadline=self.clock()+5
        elif kind=='HELLO':
            if self.state!='HELLO' or any(row[k]!=self.backend[k] for k in ('shell_uid','shell_pid','birth','generation')) or row['session']!=self.token or row['app_uid']!=self.uid or row['caps']!=127:raise ValueError('inside-hello')
            self.backend_birth=row['birth']  # Binder-attested GRANT, not independent shell /proc.
            self.stamp=dict(session=self.token,window=self.window,generation=wire.integer(row['generation']))
            self.input=inputs.InputState(row['keys']);self.state='OPENING'
            opening=dict(action=self.open_action)
            if self.initial_url is not None:opening.update(initial_url=self.initial_url,compact=self.compressed)
            self._send(opening)
        elif kind=='OPENED':
            command,lease,_=self._observe(row,True)
            if self.state!='OPENING' or not wire.is_open(command['action']) or row['inputs_released']:raise ValueError('inside-opened')
            self.task=copy.deepcopy(lease);self.state='OPEN';self.inflight=None;self._advance()
        elif kind=='ACK':
            command,_,seen=self._observe(row);action=command['action']
            if wire.is_open(action) or action=='CLOSE':raise ValueError('inside-ack-action')
            if action in ('RELEASE_ALL','RESIZE') or action=='FOCUS' and not command['pressed']:
                if not row['inputs_released']:raise ValueError('inside-retirement-ack')
            if action=='RELEASE_ALL':self.needs_retirement=False
            elif action=='RESIZE':self.geometry=copy.deepcopy(command['geometry']);self.remote_focus=False
            elif action=='FOCUS':
                if command['pressed'] and not seen['focused']:raise ValueError('inside-focus-ack')
                self.remote_focus=command['pressed']
                if not command['pressed']:self.needs_focus_off=False
            elif not seen['focused']:raise ValueError('inside-input-focus')
            self.inflight=None;self._advance()
            if action=='RESIZE':
                pending=self.pending_resize_frame;self.pending_resize_frame=None
                if pending is not None and copy_frame is not None and pending['task']==self.task and pending['geometry']==self.geometry and self.want_focus and not self._changed() and not self.closing and not self.needs_retirement and not self.needs_focus_off:
                    copy_frame(pending,True)
        elif kind=='FRAME':
            if self.task is None or row['task']!=self.task or row['sequence']<=self.frame_sequence:raise ValueError('inside-frame-lease')
            geometries=[self.geometry]
            if self.inflight and self.inflight['action']=='RESIZE':geometries.append(self.inflight['geometry'])
            if row['geometry'] not in geometries:raise ValueError('inside-frame-geometry')
            wire.geometry(row['geometry'])
            if len(row['data'])!=row['bytes'] or row['bytes']!=row['stride']*row['geometry']['height'] or row['bytes']>wire.MAX_FRAME:raise ValueError('inside-frame-data')
            self.retirement.accept(row);owned=copy.deepcopy({k:v for k,v in row.items() if k!='data'});owned['data']=bytes(memoryview(row['data']))
            display=row['geometry']==self.geometry and not self._changed() and not self.closing
            if copy_frame is not None:copy_frame(owned,display)
            if self.inflight and self.inflight['action']=='RESIZE' and row['geometry']==self.inflight['geometry'] and self.want_focus and not self.closing and not self.needs_retirement and not self.needs_focus_off and all(row['geometry'][k]==self.desired[k] for k in ('width','height','density')):
                self.pending_resize_frame=copy.deepcopy(owned)
            self.output.put(self.retirement.copied(row));self.frame_sequence=row['sequence']
        elif kind=='CLOSED':
            if not self.closing or self.inflight is None or self.inflight['action']!='CLOSE' or row['stamp']!=self.stamp:raise ValueError('inside-close')
            ids=(self.task['task_id'],self.task['display_id']) if self.task else (0,0)
            if (row['task_id'],row['display_id'])!=ids or not all(row[k] for k in ('task_removed','display_removed','inputs_released')) or self.retirement.pending is not None:raise ValueError('inside-close-cleanup')
            self.pending_resize_frame=None;self.input.retire();self.inflight=None;self.state='CLOSED'
        else:raise ValueError('inside-backend-error')


def run(encoded,initial_url=None):
    if initial_url is not None:
        from inside_uri import validate
        initial_url=validate(initial_url)
    import secrets
    import threading
    os.environ['GDK_BACKEND']='wayland'
    import gi
    gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0');gi.require_version('GdkPixbuf','2.0');gi.require_foreign('cairo')
    from gi.repository import Gtk,Gdk,GdkPixbuf,GLib,Gio
    application_id='dev.loopy.android.w'+secrets.token_hex(16)
    GLib.set_prgname(application_id)
    app=Gtk.Application(application_id=application_id,flags=Gio.ApplicationFlags.NON_UNIQUE)

    class View:
        def __init__(self):
            self.window=Gtk.ApplicationWindow(application=app);self.window.set_title('Android 앱');self.window.set_default_size(640,480)
            self.area=Gtk.DrawingArea();self.area.set_can_focus(True);self.area.set_hexpand(True);self.area.set_vexpand(True)
            self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK|Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.SCROLL_MASK|Gdk.EventMask.SMOOTH_SCROLL_MASK|Gdk.EventMask.KEY_PRESS_MASK|Gdk.EventMask.KEY_RELEASE_MASK)
            overlay=Gtk.Overlay();overlay.add(self.area);self.window.add(overlay)
            self.message=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);self.message.set_halign(Gtk.Align.CENTER);self.message.set_valign(Gtk.Align.CENTER)
            self.label=Gtk.Label(label='Android 내부 연결을 준비하는 중입니다.');self.label.set_line_wrap(True)
            self.retry=Gtk.Button(label='다시 연결');self.retry.connect('clicked',lambda *_:self.start());self.message.pack_start(self.label,False,False,0);self.message.pack_start(self.retry,False,False,0);overlay.add_overlay(self.message)
            controls=Gtk.Button(label='Android 연결 관리');controls.connect('clicked',lambda *_:self.controls());self.message.pack_start(controls,False,False,0)
            self.sock=None;self.identity=None;self.session=None;self.decoder=None;self.pixbuf=None;self.image_geometry=None;self.generation=0;self.connecting=False;self.dead=False;self.close_at=None;self.resize_timer=0
            self.view_geometry=None;self.start_pending=False
            self.area.connect('draw',self.draw);self.area.connect('size-allocate',self.size)
            self.area.connect('motion-notify-event',lambda w,e:self.event('move',e))
            self.area.connect('button-press-event',lambda w,e:self.event('button',e,True));self.area.connect('button-release-event',lambda w,e:self.event('button',e,False))
            self.area.connect('scroll-event',lambda w,e:self.event('scroll',e))
            self.area.connect('key-press-event',lambda w,e:self.event('key',e,True));self.area.connect('key-release-event',lambda w,e:self.event('key',e,False))
            self.window.connect('focus-in-event',lambda *_:self.focus(True));self.window.connect('focus-out-event',lambda *_:self.focus(False))
            self.window.connect('delete-event',self.close);self.window.connect('destroy',self.destroy)
            self.window.connect('realize',self.realized);self.window.show_all();self.retry.hide();GLib.timeout_add(16,self.poll)
        def realized(self,*unused):
            native=self.window.get_window();display=self.window.get_display()
            self.wayland=native is not None and native.__gtype__.name=='GdkWaylandWindow' and display.__gtype__.name=='GdkWaylandDisplay'
            self.start()
        def disconnect(self):
            self.generation+=1;self.connecting=False
            if self.session is not None:self.session.input.retire()
            if self.sock is not None:self.sock.close()
            self.sock=None;self.identity=None;self.session=None;self.decoder=None;self.pixbuf=None;self.image_geometry=None;self.area.queue_draw()
        def unavailable(self):
            self.start_pending=False
            self.disconnect()
            if self.close_at is not None:self.window.destroy();return
            self.label.set_text('Android 내부 연결을 사용할 수 없습니다. 연결 서비스를 확인한 뒤 다시 시도하세요.')
            self.message.show_all();self.retry.set_sensitive(bool(getattr(self,'wayland',False)))
        def controls(self):
            try:
                from platform_action import request
                request('/run/loopy',os.environ.get('LOOPY_SESSION'),'inside-backend')
            except Exception:self.label.set_text('현재 세션의 Android 연결 관리 화면을 열 수 없습니다. Loopy 메뉴에서 확인하세요.')
        def start(self):
            if self.dead or self.close_at is not None or self.connecting:return
            if self.view_geometry is None or self.resize_timer:self.start_pending=True;return
            self.start_pending=False
            self.disconnect()
            if not getattr(self,'wayland',False):self.unavailable();return
            self.connecting=True;generation=self.generation
            self.label.set_text('Android 내부 연결을 준비하는 중입니다.');self.message.show_all();self.retry.hide()
            def acquire():
                sock=None
                try:
                    token=os.environ.get('LOOPY_SESSION','');target=wire.catalog('/run/loopy',token,encoded)
                    sock,identity=wire.connect(token)
                    result=(sock,identity,token,target)
                except Exception:
                    if sock is not None:sock.close()
                    result=None
                GLib.idle_add(self.connected,generation,result)
            threading.Thread(target=acquire,name='loopy-inside-connect',daemon=True).start()
        def connected(self,generation,result):
            if self.dead or generation!=self.generation or self.close_at is not None:
                if result is not None:result[0].close()
                return False
            self.connecting=False
            if result is None:self.unavailable();return False
            if self.resize_timer or self.view_geometry is None:
                result[0].close();self.start_pending=True;return False
            try:
                self.sock,self.identity,token,target=result;wire.check_peer(self.sock,self.identity)
                self.session=Session(token,application_id.rsplit('.w',1)[1],os.getuid(),target,self.identity,self.view_geometry,compressed=True,initial_url=initial_url)
                self.decoder=wire.Decoder();self.session.focus(bool(self.window.is_active()))
            except Exception:self.unavailable()
            return False
        def flush(self):
            if self.sock is not None:
                wire.check_peer(self.sock,self.identity);self.session.output.flush(self.sock)
        def poll(self):
            if self.dead:return False
            try:
                if self.sock is not None:
                    wire.check_peer(self.sock,self.identity)
                    for _ in range(128):
                        try:data=self.sock.recv(65536)
                        except BlockingIOError:break
                        if not data:
                            self.decoder.finish()
                            if self.session.state=='CLOSED':self.window.destroy();return False
                            raise ValueError('inside-eof')
                        for row in self.decoder.feed(data):
                            if row['type']=='ACK' and self.session.inflight and self.session.inflight['action']=='RESIZE':
                                self.pixbuf=None;self.image_geometry=None;self.area.queue_draw()
                            self.session.receive(row,self.copy_frame)
                            if self.session.state=='OPEN':self.message.hide()
                    self.flush();self.session.check_timeout()
                    if self.session.state=='CLOSED' and not self.session.output.pending:self.window.destroy();return False
                if self.close_at is not None and time.monotonic()>self.close_at:self.window.destroy();return False
            except Exception:self.unavailable()
            return not self.dead
        def copy_frame(self,row,display):
            if not display:return
            g=row['geometry'];owned=GLib.Bytes.new(row['data'])
            pixbuf=GdkPixbuf.Pixbuf.new_from_bytes(owned,GdkPixbuf.Colorspace.RGB,True,8,g['width'],g['height'],row['stride'])
            if pixbuf is None:raise ValueError('inside-pixel-copy')
            self.pixbuf=pixbuf;self.image_geometry=copy.deepcopy(g);self.area.queue_draw()
        def draw(self,widget,cr):
            cr.set_source_rgb(.08,.08,.08);cr.paint()
            if self.pixbuf is not None:
                allocation=widget.get_allocation();p=self.pixbuf
                left,top,scale=inputs.viewport(allocation.width,allocation.height,p.get_width(),p.get_height())
                cr.save();cr.translate(left,top);cr.scale(scale,scale);Gdk.cairo_set_source_pixbuf(cr,p,0,0);cr.paint();cr.restore()
            return False
        def focus(self,active):
            try:
                if self.session is not None:self.session.focus(active);self.flush()
                if active:self.area.grab_focus()
            except Exception:self.unavailable()
            return False
        def size(self,widget,allocation):
            if self.resize_timer:GLib.source_remove(self.resize_timer)
            self.resize_timer=GLib.timeout_add(150,self.resized)
        def resized(self):
            self.resize_timer=0
            if self.dead:return False
            if self.session is None:self.view_geometry=None
            try:
                allocation=self.area.get_allocation();factor=self.area.get_scale_factor()
                width,height=allocation.width*factor,allocation.height*factor;density=160*factor
                if self.session is None and (width<1 or height<1):return False
                geometry=dict(epoch=1,width=width,height=height,density=density);wire.geometry(geometry);self.view_geometry=geometry
                if self.session is not None:self.session.resize(width,height,density);self.flush()
                elif self.start_pending:self.start()
            except Exception:self.unavailable()
            return False
        def event(self,kind,event,pressed=False):
            try:
                if self.session is None or not self.session.input.focused or not inputs.display_matches(self.image_geometry,self.session.geometry):return False
                wire.check_peer(self.sock,self.identity);state=self.session.input;allocation=self.area.get_allocation();g=self.session.geometry
                if kind=='key':
                    hardware=inputs.success_value(event.get_keycode());intent=state.key(hardware,pressed)
                else:
                    point=inputs.coords(event.get_coords())
                    if point is None:return False
                    arguments=(*point,allocation.width,allocation.height,g['width'],g['height'])
                    if kind=='move':intent=state.move(*arguments)
                    elif kind=='button':
                        button=inputs.gdk_button(inputs.success_value(event.get_button()))
                        if pressed:self.area.grab_focus()
                        intent=state.button(button,pressed,*arguments)
                    else:
                        delta=inputs.scroll_delta(event.get_scroll_direction(),event.get_scroll_deltas())
                        if delta is None:return False
                        intent=state.scroll(*delta,*arguments)
                self.session.send_input(intent);self.flush()
            except Exception:self.unavailable()
            return True
        def close(self,*unused):
            if self.close_at is not None:return True
            self.close_at=time.monotonic()+5
            if self.session is None or self.session.task is None:self.window.destroy();return True
            try:self.session.close();self.flush()
            except Exception:self.window.destroy()
            return True
        def destroy(self,*unused):
            self.dead=True;self.start_pending=False
            if self.resize_timer:GLib.source_remove(self.resize_timer);self.resize_timer=0
            self.disconnect();app.quit()

    app.connect('activate',lambda *_:View());return app.run([])


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Android internal window');parser.add_argument('--component',required=True)
    value=parser.parse_args();return run(value.component)


if __name__=='__main__':raise SystemExit(main())
