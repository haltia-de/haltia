import subprocess,pathlib,json,hashlib,shutil,uuid,sys
p=pathlib.Path(__file__).resolve().parent;root=p.parent;package=next(p.glob('*.deb'));results=[]
for suite,image in [('noble','ubuntu:noble'),('resolute','ubuntu:26.04'),('trixie','debian:trixie')]:
 name='haltia-paint-candidate-'+suite+'-'+uuid.uuid4().hex[:16]
 created=False
 setup="""set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates gpgv
cp /evidence/key.gpg /usr/share/keyrings/haltia.gpg
printf 'deb [signed-by=/usr/share/keyrings/haltia.gpg] https://haltia-de.github.io/packages/apt SUITE main\n' >/etc/apt/sources.list.d/haltia.list
apt-get update
apt-get install -y --no-install-recommends /evidence/paint-candidate/PACKAGE xvfb xauth dbus-x11
""".replace('SUITE',suite).replace('PACKAGE',package.name)
 def call(cmd,log,timeout=600):
  with (p/log).open('w') as out:
   try:return subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,timeout=timeout).returncode
   except subprocess.TimeoutExpired:return 124
 try:
  subprocess.run(['docker','run','-d','--name',name,'-v',str(root)+':/evidence',image,'sleep','infinity'],check=True,stdout=subprocess.DEVNULL)
  created=True
  rc=call(['docker','exec',name,'bash','-c',setup],suite+'.install.log');results.append(dict(suite=suite,check='local_unsigned_candidate_install',status='pass' if rc==0 else 'fail',exit=rc,sha256=hashlib.sha256(package.read_bytes()).hexdigest()));print(suite,'install',rc,flush=True)
  if rc:continue
  subprocess.run(['docker','network','disconnect','bridge',name],check=True)
  env=['env','HOME=/tmp/profile','XDG_CONFIG_HOME=/tmp/profile/config','XDG_DATA_HOME=/tmp/profile/data','XDG_CACHE_HOME=/tmp/profile/cache','NO_AT_BRIDGE=1','XDG_CURRENT_DESKTOP=Validation']
  for phase in ['change','restart']:
   cmd=['docker','exec',name]+env+['timeout','--kill-after=2','25','xvfb-run','-a','-s','-screen 0 1280x1024x24','dbus-run-session','--','python3','/evidence/functional/gtk_probe.py','paint','--output','/evidence/paint-candidate/'+suite+'-screens','--phase',phase]
   rc=call(cmd,suite+'.'+phase+'.log',40);results.append(dict(suite=suite,check='gtk_'+phase,status='pass' if rc==0 else 'fail',exit=rc));print(suite,phase,rc,flush=True)
  for signum in ['TERM','INT']:
   cmd=['docker','exec',name]+env+['timeout','--kill-after=2','12','xvfb-run','-a','dbus-run-session','--','python3','/evidence/paint-candidate/signal-probe.py',signum]
   rc=call(cmd,suite+'.SIG'+signum+'.log',20);log=(p/(suite+'.SIG'+signum+'.log')).read_text();results.append(dict(suite=suite,check='SIG'+signum,status='pass' if rc==0 and 'SIGNAL_SHUTDOWN_OK' in log else 'fail',exit=rc));print(suite,'SIG'+signum,rc,flush=True)
 finally:
  if created:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL)
  (p/'candidate.results.json').write_text(json.dumps(results,indent=2))

sys.exit(1 if any(result['status']!='pass' for result in results) else 0)
