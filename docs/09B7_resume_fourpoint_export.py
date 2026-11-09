import json,os,subprocess,sys
from pathlib import Path
R=Path.cwd();tag='09B7_20261103_fourpoint';status=R/'docs'/f'{tag}_status.json';state=json.loads(status.read_text());results={int(k):v for k,v in state['optim_results'].items()};env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8')
def save():status.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
def run(name,argv):
 with open(f'{tag}_{name}.log','w',encoding='utf-8') as f:subprocess.run([sys.executable,'docs/09B7_compat_dispatch.py',*argv],stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
if True:
 output=f'params/{tag}_candidate.json';run('merge',['tools/sensor_parameter_package.py','--results',*[results[d] for d in (0,120,240)],'--output',output]);state['candidate']=output;save()
 run('validation',['tools/calibration_validation.py','--sensor-params',output,'--score-results',state['score'],'--json-output',f'docs/{tag}_validation.json','--markdown-output',f'docs/{tag}_validation.md','--package-output',f'params/{tag}_checked.json'])
 state['stage']='first_pass_complete_requires_review';save()