"""Owned GTK action and clipboard witness; never log clipboard text.

Run through the current Sway session, then focus this window before Alt+C/V.
The fixture sets a known baseline and writes only booleans to its /tmp record.
"""
import gi,os,json
from pathlib import Path
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,GLib
marker='LOOPY_COPY_TEST'
proof={'pid':os.getpid(),'uid':os.getuid(),'ctrl_c_received':False,'ctrl_v_received':False,'paste_matches_fixture':False}
def record():Path('/tmp/loopy-clipboard-fixture-result.json').write_text(json.dumps(proof))
w=Gtk.Window(title='Loopy clipboard fixture');w.set_default_size(620,320)
w.connect('destroy',Gtk.main_quit)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_border_width(16);w.add(box)
label=Gtk.Label(label='복사 테스트 · 선택된 문장을 Alt+C로 복사한 후 Alt+V로 붙여넣기');label.set_line_wrap(True);box.pack_start(label,False,False,0)
v=Gtk.TextView();b=v.get_buffer();b.set_text(marker);b.select_range(b.get_start_iter(),b.get_end_iter());box.pack_start(v,True,True,0)
def empty():
 proof['clipboard_matches_fixture']=Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()==marker
 b.set_text('');label.set_text('복사 키 수신 · 이제 Alt+V로 붙여넣기');record();return False
def key(_v,e):
 if e.state & Gdk.ModifierType.CONTROL_MASK:
  if e.keyval in (Gdk.KEY_c,Gdk.KEY_C):
   proof['ctrl_c_received']=True;proof['copy_modifiers']=int(e.state);proof['copy_has_selection']=b.get_has_selection();record();GLib.idle_add(empty)
  elif e.keyval in (Gdk.KEY_v,Gdk.KEY_V):proof['ctrl_v_received']=True;proof['paste_modifiers']=int(e.state);record()
 return False
def inserted(_b,_iter,text,_length):
 if proof['ctrl_v_received'] and text==marker:proof['paste_matches_fixture']=True;label.set_text('복사·붙여넣기 통과');record()
v.connect('copy-clipboard',lambda _v: (proof.update(copy_action=True),record()));v.connect('paste-clipboard',lambda _v: (proof.update(paste_action=True),record()));v.connect('key-press-event',key);b.connect('insert-text',inserted);Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text('LOOPY_EMPTY_BASELINE',-1);w.show_all();v.grab_focus();record();Gtk.main()
