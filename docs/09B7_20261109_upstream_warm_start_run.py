import concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]
os.chdir(R)
tag='09B7_20261109_upstream_warm_start'
state={'started':time.strftime('%Y-%m-%d %H:%M:%S'),'stage':'optimizing','results':{}}
def save(): (R/'docs'/f'{tag}_status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
common=['--sensor_params','params/09B7_20261106_single_limits_candidate.json','--multi_region_calib','True','--optimization_regions',"['full','end15cm','end5cm']",'--full_point_calib','True','--end15cm_point_calib','True','--end5cm_point_calib','True']
env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
def run(name,args):
 with open(R/f'{tag}_{name}.log','w',encoding='utf-8') as f:
  p=subprocess.run([sys.executable,'docs/09B7_compat_dispatch.py',*args],stdout=f,stderr=subprocess.STDOUT,env=env)
 if p.returncode: raise RuntimeError(f'{name} exit={p.returncode}')
def optimize(d):
 run(f'direct{d}',['main.py','--task','optim',*common,'--direct',str(d)])
try:
 save()
 before=set(R.glob('calibration_results/09B7*/results.json'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(optimize,[0,120,240]))
 for f in set(R.glob('calibration_results/09B7*/results.json'))-before:
  data=json.loads(f.read_text(encoding='utf-8'))
  if data.get('task')=='optim':state['results'][str(data['direct'])]=str(f.relative_to(R))
 assert len(state['results'])==3
 save()
 output=f'params/{tag}_candidate.json'
 run('merge',['tools/sensor_parameter_package.py','--results',*[state['results'][str(d)] for d in (0,120,240)],'--output',output])
 state.update(stage='merged_requires_validation',candidate=output);save()
except Exception as e:
 state.update(stage='failed',error=str(e));save();raise
