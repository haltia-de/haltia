#!/usr/bin/env python3
"""Existing snapshots must be rejected before any Git/GitHub command or overwrite."""
import base64,io,os,pathlib,subprocess,sys,tarfile,tempfile,unittest
BASE=pathlib.Path(__file__).resolve().parent
class SnapshotOwnership(unittest.TestCase):
 def check_existing(self,script,existing):
  with tempfile.TemporaryDirectory(prefix='haltia-snapshot-test-') as tmp:
   root=pathlib.Path(tmp);output=root/'output';output.mkdir();bin=root/'bin';bin.mkdir();calls=root/'calls'
   if existing=='sources':old=output/'sources/text/stale.txt';old.parent.mkdir(parents=True);old.write_text('preserve old snapshot')
   else:old=output/'source-manifest.json';old.write_text('preserve old snapshot')
   payloads=[]
   for compressed in [False,True]:
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w:gz' if compressed else 'w') as archive:
     data=b'new fixture';member=tarfile.TarInfo('fixture-root/new.txt' if compressed else 'new.txt');member.size=len(data);archive.addfile(member,io.BytesIO(data))
    payloads.append(base64.b64encode(buffer.getvalue()).decode())
   code='\n'.join(['#!/usr/bin/env python3','import sys,pathlib,json,base64',"pathlib.Path("+repr(str(calls))+").open('a').write('called')",'args=sys.argv[1:]',"if 'rev-parse' in args:print('1'*40)","elif 'archive' in args:sys.stdout.buffer.write(base64.b64decode("+repr(payloads[0])+'))',"elif args[-1].endswith('/commits/main'):print(json.dumps(dict(sha='1'*40,commit=dict(committer=dict(date='2026-10-29T00:00:00Z')))))",'else:sys.stdout.buffer.write(base64.b64decode('+repr(payloads[1])+'))'])+'\n'
   for name in ['git','gh']:
    fake=bin/name;fake.write_text(code);fake.chmod(0o755)
   env=os.environ.copy();env['PATH']=str(bin)+os.pathsep+env['PATH']
   args=['--source-root',str(root/'repos'),'--output',str(output)] if script=='snapshot-sources.py' else ['--output',str(output)]
   result=subprocess.run([sys.executable,str(BASE/script),*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=10)
   self.assertNotEqual(result.returncode,0,result.stdout);self.assertEqual(old.read_text(),'preserve old snapshot');self.assertFalse(calls.exists(),'Existing snapshot triggered a Git/GitHub command')
 def test_local_existing_sources_rejected(self):self.check_existing('snapshot-sources.py','sources')
 def test_local_existing_manifest_rejected(self):self.check_existing('snapshot-sources.py','manifest')
 def test_github_existing_sources_rejected(self):self.check_existing('snapshot-github-main.py','sources')
 def test_github_existing_manifest_rejected(self):self.check_existing('snapshot-github-main.py','manifest')
if __name__=='__main__':unittest.main(verbosity=2)
