import runpy,sys,os,signal,pathlib,json
sys.path.insert(0,'/usr/lib/haltia-paint');ns=runpy.run_path('/usr/lib/haltia-paint/haltia_paint_main.py',run_name='validation_signal')
from gi.repository import GLib,Gtk
app=ns['App']();sent=[]
def stop():
 windows=[w for w in app.get_windows() if w.get_mapped()];assert windows,'No mapped window before signal'
 signum=getattr(signal,'SIG'+sys.argv[1]);sent.append(signum);os.kill(os.getpid(),signum);return False
GLib.timeout_add_seconds(3,stop)
rc=app.run(['haltia-paint']);assert sent and rc==0;print('SIGNAL_SHUTDOWN_OK',sys.argv[1],flush=True)
