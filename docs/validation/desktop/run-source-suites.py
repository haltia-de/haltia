#!/usr/bin/env python3
"""Run complete existing source suites in fresh archived sources with current kit.
The workdir must contain sources/ and source-manifest.json; it is mounted into a
one-use container. No host home, session sockets, hardware or user apps are mounted.
"""
import argparse,json,pathlib,subprocess,sys,uuid
parser=argparse.ArgumentParser();parser.add_argument('--workdir',type=pathlib.Path,required=True);parser.add_argument('--image',default='ubuntu:26.04');args=parser.parse_args();p=args.workdir.resolve();assert (p/'source-manifest.json').is_file();name='haltia-source-suites-'+uuid.uuid4().hex[:16];created=False;results=[]
def call(cmd,filename,timeout=600):
 with (p/filename).open('w') as out:
  try:return subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:return 124
try:
 subprocess.run(['docker','run','-d','--name',name,'-v',str(p)+':/evidence',args.image,'sleep','infinity'],check=True,stdout=subprocess.DEVNULL);created=True
 setup='apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 gir1.2-poppler-0.18 gir1.2-gstreamer-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good python3-pil python3-mpv python3-mutagen libmpv2 ffmpeg xvfb xauth dbus-x11'
 rc=call(['docker','exec',name,'bash','-c',setup],'install.log');assert rc==0,'Container dependency install failed'
 subprocess.run(['docker','network','disconnect','bridge',name],check=True)
 commands={repo:['python3 '+str(path.relative_to(p/'sources'/repo))+' -v' for path in sorted((p/'sources'/repo/'tests').glob('test_*.py'))] for repo in ['files']}
 commands.update(mail=['sh tests/run.sh -v'],firefox=['python3 -m unittest discover -s tests -v'],camera=['sh tests/run.sh -v'],text=['python3 -m unittest discover -s tests -v'],calendar=['sh tests/run.sh'],kit=['python3 -m unittest discover -s tests -v'])
 for repo,tests in commands.items():
  assert tests,'No tests found for '+repo
  for index,test in enumerate(tests):
   env=['env','HOME=/tmp/profiles/'+repo,'XDG_CONFIG_HOME=/tmp/profiles/'+repo+'/config','XDG_DATA_HOME=/tmp/profiles/'+repo+'/data','XDG_CACHE_HOME=/tmp/profiles/'+repo+'/cache','XDG_STATE_HOME=/tmp/profiles/'+repo+'/state','PYTHONPATH=/evidence/sources/kit','NO_AT_BRIDGE=1']
   cmd=['docker','exec',name]+env+['timeout','--kill-after=2','90','xvfb-run','-a','dbus-run-session','--','bash','-c','cd /evidence/sources/'+repo+' && '+test]
   rc=call(cmd,repo+'-'+str(index)+'.log',100);results.append(dict(repo=repo,command=test,exit=rc,status='pass' if rc==0 else 'fail'));print(repo,index,rc,flush=True);(p/'source.results.json').write_text(json.dumps(results,indent=2))
finally:
 if created:
  cleanup=subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL)
  results.append(dict(check='container_cleanup',status='pass' if cleanup.returncode==0 else 'fail',exit=cleanup.returncode))
  (p/'source.results.json').write_text(json.dumps(results,indent=2))
sys.exit(1 if any(row['status']!='pass' for row in results) else 0)
