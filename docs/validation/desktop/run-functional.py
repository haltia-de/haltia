#!/usr/bin/env python3
"""Isolated installed-deb GTK acceptance and optional source tests.
Requires Docker; use a dedicated work directory containing gtk_probe.py, the public
keyring key.gpg, and optional sources/{text,calendar,files,mail,firefox,camera,kit}.
Never mounts the host home or graphical/session sockets.
"""
import argparse,pathlib,subprocess,json,os,uuid,sys
parser=argparse.ArgumentParser();parser.add_argument('--workdir',type=pathlib.Path,required=True);parser.add_argument('--keyring',type=pathlib.Path,required=True);parser.add_argument('--image',default='ubuntu:26.04');args=parser.parse_args();p=args.workdir.resolve();p.mkdir(parents=True,exist_ok=True);p.chmod(0o700)
import shutil;shutil.copyfile(args.keyring,p/'key.gpg') if args.keyring.resolve()!=p/'key.gpg' else None
name='haltia-functional-'+uuid.uuid4().hex[:16]
created=False
setup="""set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates gpgv
cp /evidence/key.gpg /usr/share/keyrings/haltia.gpg
printf 'deb [signed-by=/usr/share/keyrings/haltia.gpg] https://haltia-de.github.io/packages/apt resolute main\n' >/etc/apt/sources.list.d/haltia.list
apt-get update
apt-get install -y --no-install-recommends haltia-weather haltia-news haltia-paint haltia-music haltia-messenger haltia-video python3-haltia-kit xvfb xauth dbus-x11
"""
results=[]
def call(cmd,path,timeout=600):
 with path.open('w') as output:
  try:return subprocess.run(cmd,stdout=output,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:return 124
try:
 subprocess.run(['docker','run','-d','--name',name,'-v',str(p)+':/evidence',args.image,'sleep','infinity'],check=True,stdout=subprocess.DEVNULL)
 created=True
 rc=call(['docker','exec',name,'bash','-c',setup],p/'install.log');assert rc==0,'Container dependency install failed; see install.log'
 subprocess.run(['docker','network','disconnect','bridge',name],check=True)
 for app in ['weather','news','paint','music','messenger','video']:
  for phase in ['change','restart']:
   env=['env','HOME=/tmp/profiles/'+app,'XDG_CONFIG_HOME=/tmp/profiles/'+app+'/config','XDG_DATA_HOME=/tmp/profiles/'+app+'/data','XDG_CACHE_HOME=/tmp/profiles/'+app+'/cache','NO_AT_BRIDGE=1','XDG_CURRENT_DESKTOP=Validation']
   cmd=['docker','exec',name]+env+['timeout','--kill-after=2','25','xvfb-run','-a','-s','-screen 0 1280x1024x24','dbus-run-session','--','python3','/evidence/gtk_probe.py',app,'--output','/evidence/screens','--phase',phase]
   rc=call(cmd,p/(app+'-'+phase+'.log'),timeout=35);results.append(dict(app=app,phase=phase,exit=rc,status='pass' if rc==0 else 'fail'));print(app,phase,rc,flush=True)
   (p/'summary.json').write_text(json.dumps(results,indent=2))
 if (p/'sources').exists():
  commands={'files':['python3 tests/test_library.py','python3 tests/test_choosing.py'],'mail':['sh tests/run.sh -v'],'firefox':['python3 -m unittest discover -s tests -v'],'camera':['sh tests/run.sh -v'],'text':['python3 -m py_compile haltia-text'],'calendar':['python3 -m py_compile haltia-calendar']}
  for app,tests in commands.items():
   for number,command in enumerate(tests):
    script='cd /evidence/sources/'+app+' && '+command
    cmd=['docker','exec',name,'env','HOME=/tmp/source-profiles/'+app,'XDG_CONFIG_HOME=/tmp/source-profiles/'+app+'/config','XDG_DATA_HOME=/tmp/source-profiles/'+app+'/data','PYTHONPATH=/evidence/sources/kit','bash','-c',script]
    rc=call(cmd,p/('source-'+app+'-'+str(number)+'.log'),timeout=90);results.append(dict(app=app,phase='source_test' if app not in ('text','calendar') else 'compile_only_no_test_suite',command=command,exit=rc,status='pass' if rc==0 else 'fail'));print('source',app,number,rc,flush=True)
    (p/'summary.json').write_text(json.dumps(results,indent=2))
finally:
 if created:
  cleanup=subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL)
  results.append(dict(check='container_cleanup',status='pass' if cleanup.returncode==0 else 'fail',exit=cleanup.returncode))
  (p/'summary.json').write_text(json.dumps(results,indent=2))
sys.exit(1 if any(result['status']!='pass' for result in results) else 0)
