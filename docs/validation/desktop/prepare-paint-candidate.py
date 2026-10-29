#!/usr/bin/env python3
"""Prepare an exact committed source archive and locally build/test its unsigned deb.
Does not modify the source checkout, version, tags or published repositories.
"""
import argparse,hashlib,io,json,pathlib,shutil,subprocess,sys,tarfile
parser=argparse.ArgumentParser();parser.add_argument('--repo',type=pathlib.Path,required=True);parser.add_argument('--commit',required=True);parser.add_argument('--workdir',type=pathlib.Path,required=True);parser.add_argument('--keyring',type=pathlib.Path,required=True);parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
base=pathlib.Path(__file__).resolve().parent;work=args.workdir.resolve();work.mkdir(parents=True,exist_ok=True);work.chmod(0o700);candidate=work/'paint-candidate';candidate.mkdir(exist_ok=True)
if (candidate/'source').exists():raise SystemExit('Choose a fresh workdir: candidate/source already exists')
commit=subprocess.check_output(['git','-C',str(args.repo),'rev-parse','--verify',args.commit+'^{commit}'],text=True).strip();archive=subprocess.check_output(['git','-C',str(args.repo),'archive',commit]);(candidate/'source.tar').write_bytes(archive);source=candidate/'source';source.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(source,filter='data')
(candidate/'source.json').write_text(json.dumps(dict(commit=commit,archive_sha256=hashlib.sha256(archive).hexdigest(),release_status='local unsigned candidate, not a published release'),indent=2))
shutil.copyfile(args.keyring,work/'key.gpg');(work/'functional').mkdir(exist_ok=True);shutil.copyfile(base/'gtk_probe.py',work/'functional/gtk_probe.py')
for name in ['build.py','run-candidate.py','signal-probe.py']:shutil.copyfile(base/'paint-candidate'/name,candidate/name)
if not args.prepare_only:
 subprocess.run([sys.executable,str(candidate/'build.py')],check=True)
 status=json.loads((candidate/'build.results.json').read_text())
 if status['status']!='pass':raise SystemExit('Candidate build failed; see build.log')
 subprocess.run([sys.executable,str(candidate/'run-candidate.py')],check=True)
