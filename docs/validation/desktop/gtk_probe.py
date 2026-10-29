#!/usr/bin/env python3
"""Exercise installed GTK entrypoints offline. Run under Xvfb in a disposable container."""
import argparse,json,os,pathlib,runpy,sys,time,traceback
parser=argparse.ArgumentParser();parser.add_argument('app');parser.add_argument('--output',type=pathlib.Path,required=True);parser.add_argument('--phase',choices=['change','restart'],default='change');args=parser.parse_args()
appname=args.app;out=args.output;out.mkdir(parents=True,exist_ok=True)
root=next(r for r in [pathlib.Path('/usr/lib/haltia-'+appname),pathlib.Path('/usr/share/haltia-'+appname)] if r.exists());sys.path.insert(0,str(root))
ns=runpy.run_path(str(root/('haltia_'+appname+'_main.py')),run_name='validation_probe')
import gi
gi.require_version('Gtk','3.0');from gi.repository import Gtk,Gdk,GLib
if appname=='news' and args.phase=='change':ns['save_feeds']([('Offline validation','https://example.invalid/feed','')])
cls={'weather':'Weather','news':'News','paint':'App','music':'Music','messenger':'Max','video':'Video'}[appname]
app=ns[cls]();results=[];start=time.monotonic();ticks=0

def widgets(w):
 yield w
 if isinstance(w,Gtk.Container):
  for child in w.get_children():yield from widgets(child)

def visible(w):return w.get_visible() and w.get_mapped()
def snapshot(label):
 wins=[w for w in app.get_windows() if visible(w)];assert wins,'No mapped application window'
 win=wins[0];gw=win.get_window();width,height=win.get_size();image=Gdk.pixbuf_get_from_window(gw,0,0,width,height);assert image;image.savev(str(out/(appname+'-'+args.phase+'-'+label+'.png')),'png',[],[])
 texts=[w.get_text() for w in widgets(win) if isinstance(w,Gtk.Label) and visible(w)]
 buttons=[{'label':w.get_label(),'tooltip':w.get_tooltip_text()} for w in widgets(win) if isinstance(w,Gtk.Button) and visible(w)]
 results.append(dict(check=label,status='pass',elapsed_ms=round((time.monotonic()-start)*1000),labels=texts,buttons=buttons))
 (out/(appname+'-'+args.phase+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2))
 return win

def press_gear():
 target=app.paint if appname=='paint' else app
 names={'weather':'gear','news':'gear_btn','paint':'settings_button','music':'gear','messenger':'gear'}
 if appname=='video':
  candidates=[w for w in widgets(app.get_windows()[0]) if isinstance(w,Gtk.Button) and visible(w) and w.get_image() and w.get_image().get_icon_name()[0]=='emblem-system-symbolic']
  assert candidates,'Settings icon not found';button=candidates[0]
 else:button=getattr(target,names[appname])
 assert visible(button) and button.get_sensitive(),'Settings not user-accessible';button.clicked()

def tick():
 global ticks
 ticks+=1
 try:
  if ticks==2:snapshot('home');press_gear()
  if ticks==4:
   win=snapshot('settings')
   if appname=='weather':
    app.search.set_text('Validation offline')
   elif appname=='news':
    entry=next(w for w in widgets(win) if isinstance(w,Gtk.Entry) and visible(w));entry.set_text('https://example.invalid/')
    button=next(w for w in widgets(win) if isinstance(w,Gtk.Button) and visible(w) and w.get_label()=='Найти');button.clicked()
   else:
    # Only local safe controls: sound/vibration or display; never login, calls or web access.
    switches=[w for w in widgets(win) if isinstance(w,Gtk.Switch) and visible(w) and w.get_sensitive()]
    safe={'music':0,'messenger':0,'video':None,'paint':None}.get(appname)
    if safe is not None and switches:
     sw=switches[safe];statefile=out/(appname+'-switch.json')
     if args.phase=='change':sw.set_active(not sw.get_active());statefile.write_text(json.dumps({'expected':sw.get_active()}))
     else:assert sw.get_active()==json.loads(statefile.read_text())['expected'],'UI switch state lost after restart'
     results.append(dict(check='ui_switch_'+args.phase,status='pass',state=sw.get_active()))
  if ticks==8:
   win=snapshot('after-interaction')
   if appname=='weather':assert app.city_note.get_text()=='Нет связи с Gismeteo','Offline search error not shown'
   if appname=='news':
    if args.phase=='change':
     remove=next(w for w in widgets(win) if isinstance(w,Gtk.Button) and visible(w) and w.get_label()=='Убрать');remove.clicked()
    else:assert not ns['load_feeds'](),'Source removed through UI returned after restart'
   snapshot('after-local-change')
  if ticks==10:
   target=app.paint if appname=='paint' else app
   names={'weather':'back','news':'back_btn','paint':'back_button','music':'back_btn','messenger':'back'}
   if appname in names:
    button=getattr(target,names[appname]);assert visible(button) and button.get_sensitive();button.clicked()
   else:
    candidates=[w for w in widgets(app.get_windows()[0]) if isinstance(w,Gtk.Button) and visible(w) and (w.get_label() or '')=='←']
    if candidates:candidates[0].clicked()
  if ticks==12:
   win=snapshot('returned')
   if appname!='paint':app.quit();return False
   buttons=[w for w in widgets(win) if isinstance(w,Gtk.Button) and visible(w) and w.get_style_context().has_class('card')]
   if app.paint.stack.get_visible_child_name()!='board':
    assert buttons,'No built-in picture card visible';buttons[0].clicked()
  if appname=='paint' and ticks==15:
   snapshot('picture');board=app.paint.board;assert board and board.regions
   statefile=out/'paint-region.json'
   if args.phase=='restart':
    saved=json.loads(statefile.read_text());assert board.pic['id']==saved['picture'] and saved['region'] in board.filled,'Painted region lost after restart'
    results.append(dict(check='paint_region_restart',status='pass',picture=board.pic['id'],region=saved['region']))
   else:
    index=next(i for i in range(len(board.regions)) if i not in board.filled);region=board.regions[index];app.paint.swatches[region.n][0].clicked()
    for kind,signal in [(Gdk.EventType.BUTTON_PRESS,'button-press-event'),(Gdk.EventType.BUTTON_RELEASE,'button-release-event')]:
     event=Gdk.Event.new(kind);event.button=1;event.x=region.x*board.scale-round(board.ox);event.y=region.y*board.scale-round(board.oy);event.window=board.get_window();event.set_device(Gdk.Display.get_default().get_default_seat().get_pointer());board.emit(signal,event)
    assert index in board.filled,'GTK pointer events did not paint selected region'
    statefile.write_text(json.dumps({'picture':board.pic['id'],'region':index}));results.append(dict(check='gtk_paint_region',status='pass',picture=board.pic['id'],region=index))
  if appname=='paint' and ticks==18:
   snapshot('painted');saved=json.loads((out/'paint-region.json').read_text());assert saved['region'] in ns['load_progress'](app.paint.board.pic),'Painted region not saved'
   app.quit();return False
 except Exception as exc:
  results.append(dict(check='interaction',status='fail',error=str(exc),traceback=traceback.format_exc()));(out/(appname+'-'+args.phase+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2));app.quit();return False
 return True
GLib.timeout_add_seconds(1,tick)
app_exit=app.run(['haltia-'+appname])
required={'home','settings','after-interaction','after-local-change','returned'}
if appname in ('music','messenger'):required.add('ui_switch_'+args.phase)
if appname=='paint':required.update({'picture','painted','gtk_paint_region' if args.phase=='change' else 'paint_region_restart'})
completed={row['check'] for row in results if row.get('status')=='pass'}
missing=sorted(required-completed)
results.append(dict(check='application_exit',status='pass' if app_exit==0 else 'fail',exit=app_exit))
results.append(dict(check='required_checks',status='pass' if not missing else 'fail',missing=missing))
(out/(appname+'-'+args.phase+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2))
sys.exit(1 if any(r['status']=='fail' for r in results) else 0)
