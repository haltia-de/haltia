#!/usr/bin/env python3
"""Test Docker ownership/failure exits through a fake CLI. Never calls real Docker."""
import json,os,pathlib,re,shutil,subprocess,sys,tempfile,unittest
BASE=pathlib.Path(__file__).resolve().parent
FAKE=r"""#!/usr/bin/env python3
import os,sys,json
args=sys.argv[1:]
with open(os.environ['FAKE_DOCKER_LOG'],'a') as out:out.write(json.dumps(args)+'\n')
scenario=os.environ['FAKE_DOCKER_SCENARIO']
if args[0]=='rm' and scenario=='cleanup_failure':sys.exit(19)
if args[0]=='run':
 if scenario=='run_failure':sys.exit(125)
 if scenario=='build_failure':sys.exit(13)
 print('fake-created-container')
if args[0]=='exec':
 if scenario=='setup_failure' and any('apt-get update' in arg for arg in args):sys.exit(17)
 if scenario=='test_failure' and any('gtk_probe.py' in arg for arg in args):sys.exit(7)
 if scenario=='suite_failure' and any('tests/test_' in arg or 'unittest discover' in arg for arg in args):sys.exit(7)
 if any('signal-probe.py' in arg for arg in args):print('SIGNAL_SHUTDOWN_OK',args[-1])
sys.exit(0)
"""
compile(FAKE,'fake_docker','exec')
class Isolation(unittest.TestCase):
 def run_case(self,script,scenario,artifact=True):
  with tempfile.TemporaryDirectory(prefix='haltia-cli-test-') as tmp:
   root=pathlib.Path(tmp);bundle=root/'bundle';shutil.copytree(BASE,bundle,ignore=shutil.ignore_patterns('__pycache__'))
   bin=root/'bin';bin.mkdir();fake=bin/'docker';fake.write_text(FAKE);fake.chmod(0o755);log=root/'calls.jsonl'
   env=os.environ.copy();env.update(PATH=str(bin)+os.pathsep+env['PATH'],FAKE_DOCKER_LOG=str(log),FAKE_DOCKER_SCENARIO=scenario)
   work=root/'work';work.mkdir();key=root/'public-key.gpg';key.write_bytes(b'test public key fixture')
   if script=='run-source-suites.py':
    (work/'source-manifest.json').write_text('{}');tests=work/'sources/files/tests';tests.mkdir(parents=True);(tests/'test_fixture.py').write_text('pass');args=['--workdir',str(work)]
   elif script=='run-functional.py':args=['--workdir',str(work),'--keyring',str(key)]
   else:
    args=[]
    if artifact:(bundle/'paint-candidate/fixture.deb').write_bytes(b'fake package, never installed')
   r=subprocess.run([sys.executable,str(bundle/script),*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=15)
   calls=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
   results_path=(work/'summary.json') if script=='run-functional.py' else ((work/'source.results.json') if script=='run-source-suites.py' else bundle/'paint-candidate/candidate.results.json')
   self.last_results=json.loads(results_path.read_text()) if results_path.exists() else []
   return r.returncode,calls
 def assert_owned_cleanup(self,calls,expected):
  runs=[c[c.index('--name')+1] for c in calls if c[0]=='run' and '--name' in c]
  removals=[c[-1] for c in calls if c[:2]==['rm','-f']]
  self.assertEqual(len(runs),expected);self.assertEqual(removals,runs);self.assertEqual(len(set(runs)),len(runs))
  for name in runs:self.assertRegex(name,r'-[0-9a-f]{16}$')
 def test_functional_creation_failure_never_removes_container(self):
  rc,calls=self.run_case('run-functional.py','run_failure');self.assertNotEqual(rc,0);self.assertFalse(any(c[0]=='rm' for c in calls));self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'run')
 def test_candidate_creation_failure_never_removes_container(self):
  rc,calls=self.run_case('paint-candidate/run-candidate.py','run_failure');self.assertNotEqual(rc,0);self.assertFalse(any(c[0]=='rm' for c in calls));self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'run')
 def test_functional_required_failure_exits_nonzero_and_cleans_owned(self):
  rc,calls=self.run_case('run-functional.py','test_failure');self.assertNotEqual(rc,0);self.assert_owned_cleanup(calls,1)
 def test_candidate_required_failure_exits_nonzero_and_cleans_owned(self):
  rc,calls=self.run_case('paint-candidate/run-candidate.py','test_failure');self.assertNotEqual(rc,0);self.assert_owned_cleanup(calls,3)
 def test_functional_success_uses_distinct_per_run_names(self):
  names=[]
  for unused in range(2):
   rc,calls=self.run_case('run-functional.py','success');self.assertEqual(rc,0);self.assert_owned_cleanup(calls,1);names.extend(c[c.index('--name')+1] for c in calls if c[0]=='run')
  self.assertEqual(len(set(names)),2)
 def test_candidate_success_cleans_only_own_unique_names(self):
  rc,calls=self.run_case('paint-candidate/run-candidate.py','success');self.assertEqual(rc,0);self.assert_owned_cleanup(calls,3)
 def test_functional_setup_failure_cleans_only_owned(self):
  rc,calls=self.run_case('run-functional.py','setup_failure');self.assertNotEqual(rc,0);self.assert_owned_cleanup(calls,1)
 def test_candidate_setup_failure_cleans_only_owned(self):
  rc,calls=self.run_case('paint-candidate/run-candidate.py','setup_failure');self.assertNotEqual(rc,0);self.assert_owned_cleanup(calls,3)
 def test_source_creation_failure_never_removes_container(self):
  rc,calls=self.run_case('run-source-suites.py','run_failure');self.assertNotEqual(rc,0);self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'run')
 def test_source_required_failure_cleans_owned_and_exits_nonzero(self):
  rc,calls=self.run_case('run-source-suites.py','suite_failure');self.assertNotEqual(rc,0);self.assert_owned_cleanup(calls,1)
 def test_source_success_cleans_only_owned(self):
  rc,calls=self.run_case('run-source-suites.py','success');self.assertEqual(rc,0);self.assert_owned_cleanup(calls,1)
 def test_functional_cleanup_failure_is_reported_and_nonzero(self):
  rc,calls=self.run_case('run-functional.py','cleanup_failure');self.assertNotEqual(rc,0);self.assertTrue(any(r.get('check')=='container_cleanup' and r['status']=='fail' for r in self.last_results))
 def test_source_cleanup_failure_is_reported_and_nonzero(self):
  rc,calls=self.run_case('run-source-suites.py','cleanup_failure');self.assertNotEqual(rc,0);self.assertTrue(any(r.get('check')=='container_cleanup' and r['status']=='fail' for r in self.last_results))
 def test_candidate_cleanup_failure_is_reported_and_nonzero(self):
  rc,calls=self.run_case('paint-candidate/run-candidate.py','cleanup_failure');self.assertNotEqual(rc,0);self.assertTrue(any(r.get('check')=='container_cleanup' and r['status']=='fail' for r in self.last_results))
 def test_build_failed_command_exits_nonzero(self):
  rc,calls=self.run_case('paint-candidate/build.py','build_failure');self.assertEqual(rc,13);self.assertFalse(any(c[0]=='rm' for c in calls));self.assertIn('--rm',calls[0])
 def test_build_without_deb_fails(self):
  rc,calls=self.run_case('paint-candidate/build.py','success',artifact=False);self.assertNotEqual(rc,0)
 def test_build_success_boundary(self):
  rc,calls=self.run_case('paint-candidate/build.py','success');self.assertEqual(rc,0)
if __name__=='__main__':unittest.main(verbosity=2)
