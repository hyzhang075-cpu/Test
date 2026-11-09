"""Run README workflow against current main defaults, without editing algorithms."""
import concurrent.futures,json,os,re,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];os.chdir(R)
tag='09B7_20261103_fourpoint';env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8');state={'started':time.strftime('%Y-%m-%d %H:%M:%S'),'stages':[]}
status=R/'docs'/f'{tag}_status.json'
def save():status.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
def run(name,argv):
 log=R/f'{tag}_{name}.log';print('START',name,flush=True)
 with log.open('w',encoding='utf-8') as f:
  p=subprocess.run([sys.executable,'docs/09B7_compat_dispatch.py',*argv],stdout=f,stderr=subprocess.STDOUT,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if p.returncode:raise RuntimeError(f'{name} failed ({p.returncode}): {log}')
 print('DONE',name,flush=True);return log
common=['--multi_region_calib','True','--use_full_transported_phase','False','--weights','None','--slopes','None']
try:
 for region in ('full','end15cm','end5cm'):
  run('init_'+region,['main.py','--task','init','--optimization_region',region,*common]);state['stages'].append('init_'+region);save()
 before=set(R.glob('calibration_results/09B7*/results.json'))
 run('score',['main.py','--task','score',*common]);new=set(R.glob('calibration_results/09B7*/results.json'))-before
 scores=[f for f in new if json.loads(f.read_text(encoding='utf-8')).get('task')=='score'];assert len(scores)==1;state['score']=str(scores[0].relative_to(R));save()
 log=run('ang',['main.py','--task','ang','--multi_region_calib','False','--optimization_region','full','--weights','None','--slopes','None','--rot_ang','0','--ang_range','90','--ang_step','1'])
 match=re.search(r'最优旋转角度:\s*([-+\d.eE]+)',log.read_text(encoding='utf-8'));assert match;angle=float(match.group(1));state['initial_rot_ang']=angle;save()
 before=set(R.glob('calibration_results/09B7*/results.json'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  list(pool.map(lambda d:run('optim_direct'+str(d),['main.py','--task','optim',*common,'--direct',str(d),'--rot_ang',str(angle)]),(0,120,240)))
 new=set(R.glob('calibration_results/09B7*/results.json'))-before;results={}
 for f in new:
  data=json.loads(f.read_text(encoding='utf-8'))
  if data.get('task')=='optim':results[int(data['direct'])]=str(f.relative_to(R))
 assert set(results)=={0,120,240};state['optim_results']=results;save()
 output=f'params/{tag}_candidate.json';run('merge',['tools/sensor_parameter_package.py','--results',*[results[d] for d in (0,120,240)],'--output',output]);state['candidate']=output;save()
 run('validation',['tools/calibration_validation.py','--sensor-params',output,'--score-results',state['score'],'--json-output',f'docs/{tag}_validation.json','--markdown-output',f'docs/{tag}_validation.md','--package-output',f'params/{tag}_checked.json'])
 state['stage']='first_pass_complete_requires_review';save()
except Exception as e:
 state['stage']='failed';state['error']=str(e);save();raise
