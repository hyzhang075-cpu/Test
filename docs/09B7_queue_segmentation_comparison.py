"""Queue matched-budget segmentation trials after the baseline run."""
import json,os,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];os.chdir(R)
state=R/'docs/09B7_20261103_fourpoint_status.json'
while True:
 p=json.loads(state.read_text(encoding='utf-8'))
 if p.get('stage')=='failed':raise RuntimeError('Baseline workflow failed; inspect baseline status before proceeding')
 if p.get('stage')=='first_pass_complete_requires_review':break
 time.sleep(10)
for scheme in ('B','C'):
 env=dict(os.environ,FBG_SEGMENTATION_SCHEME=scheme)
 with open(f'09B7_20261103_fourpoint_{scheme}_workflow.log','w',encoding='utf-8') as f:
  result=subprocess.run([sys.executable,'docs/09B7_readme_segmentation_worker.py'],env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError(f'Scheme {scheme} failed; stop rather than mixing incomplete results')
print('All three segmentation trials completed; reports require numerical comparison.',flush=True)
