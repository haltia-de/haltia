import subprocess,pathlib,json,hashlib,sys
p=pathlib.Path(__file__).resolve().parent
cmd=['docker','run','--rm','-v',str(p)+':/evidence','ubuntu:noble','bash','-c','apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends debhelper dpkg-dev build-essential && cd /evidence/source && dpkg-buildpackage -b -us -uc']
with (p/'build.log').open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
result=dict(exit=r.returncode,status='pass' if r.returncode==0 and any(p.glob('*.deb')) else 'fail',artifacts=[dict(file=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in p.glob('*.deb')]);(p/'build.results.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
sys.exit(0 if result['status']=='pass' and result['artifacts'] else (r.returncode or 1))
