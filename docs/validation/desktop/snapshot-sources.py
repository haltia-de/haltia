#!/usr/bin/env python3
"""Copy committed sources without .git for offline source-suite validation."""
import argparse,subprocess,tarfile,io,json,hashlib
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True);manifest=[]
if (args.output/'sources').exists() or (args.output/'source-manifest.json').exists():raise SystemExit('Choose a fresh output directory: snapshot artifacts already exist')
for name in ['text','calendar','files','mail','firefox','camera','kit']:
 repo=args.source_root/name;head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip();data=subprocess.check_output(['git','-C',str(repo),'archive',head]);dest=args.output/'sources'/name;dest.mkdir(parents=True,exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(dest,filter='data')
 manifest.append(dict(repo=name,commit=head,archive_sha256=hashlib.sha256(data).hexdigest()))
(args.output/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
