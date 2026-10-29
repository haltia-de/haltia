#!/usr/bin/env python3
"""Archive exact live GitHub main commits without touching existing worktrees."""
import argparse,concurrent.futures,datetime,hashlib,io,json,pathlib,subprocess,tarfile
parser=argparse.ArgumentParser();parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args();p=args.output.resolve();p.mkdir(parents=True,exist_ok=True);p.chmod(0o700)
if (p/'sources').exists():raise SystemExit('Choose a fresh output directory: sources already exists')
def snapshot(name):
 endpoint='repos/haltia-de/'+name;info=json.loads(subprocess.check_output(['gh','api',endpoint+'/commits/main'],timeout=35));sha=info['sha'];data=subprocess.check_output(['gh','api',endpoint+'/tarball/'+sha],timeout=60);dest=p/'sources'/name;dest.mkdir(parents=True)
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
  for member in archive.getmembers():
   bits=member.name.split('/',1)
   if len(bits)==1:continue
   member.name=bits[1];archive.extract(member,dest,filter='data')
 return dict(repo=name,commit=sha,commit_date=info['commit']['committer']['date'],archive_sha256=hashlib.sha256(data).hexdigest(),source='GitHub API commits/main then tarball/exact-sha')
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(snapshot,['files','mail','firefox','camera','text','calendar','kit']))
(p/'source-manifest.json').write_text(json.dumps(dict(snapshot_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=rows),indent=2))
