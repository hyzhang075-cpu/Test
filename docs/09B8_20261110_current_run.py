import json,os,sys,subprocess,concurrent.futures,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];os.chdir(R)
tag='09B8_20261110_current';state={'stage':'starting','started':time.strftime('%Y-%m-%d %H:%M:%S'),'results':{}}
def save():Path('docs/'+tag+'_status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
common=json.loads(Path('docs/09B8_20261106_initial_configuration.json').read_text(encoding='utf-8'))['argv']
common+=['--full_point_calib','True','--end15cm_point_calib','True','--end5cm_point_calib','True','--use_full_transported_phase','True','--full_preserve_first_point','False','--full_absolute_direction','False','--end5cm_independent_weights','False','--end5cm_independent_weight_score','False','--end5cm_coverage_aware_weights','False','--centre_fibre','True','--method','L-BFGS-B','--weight_bounds','[0.6,5.0]','--slope_upper_bound','80','--max_iter','30','--min_loss_diff','1e-8','--rot_ang','8']
env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
def run(label,args):
 with open(tag+'_'+label+'.log','w',encoding='utf-8') as log:
  code_text = 'import main,sys\noriginal=main.build_argument_parser\ndef parser():\n p=original();p.set_defaults(sensing_ranges={1:(583,1048),3:(678,1146),4:(749,1215)});return p\nmain.build_argument_parser=parser\nmain.main()'
  command=([sys.executable,'-c',code_text,*args[1:]] if args[0]=='main.py' else [sys.executable,'docs/09B7_compat_dispatch.py',*args])
  code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT,env=env)
 if code:raise RuntimeError(label+' exit='+str(code))
def optimize(d):
 before=set(R.glob('calibration_results/09B8*/results.json'))
 run('optim_direct'+str(d),['main.py','--task','optim',*common,'--direct',str(d)])
 found=[]
 for f in set(R.glob('calibration_results/09B8*/results.json'))-before:
  p=json.loads(f.read_text(encoding='utf-8'))
  if p.get('task')=='optim' and p.get('direct')==d and all(b['status']=='complete' for b in p['regions'].values()):found.append(f)
 assert len(found)==1,(d,found)
 return d,str(found[0].relative_to(R))
try:
 save();before=set(R.glob('calibration_results/09B8*/results.json'))
 run('score',['main.py','--task','score',*common,'--direct','0'])
 scores=set(R.glob('calibration_results/09B8*/results.json'))-before;assert len(scores)==1
 state['score']=str(next(iter(scores)).relative_to(R));state['stage']='optimizing';save()
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for d,f in pool.map(optimize,[0,120,240]):state['results'][str(d)]=f;save()
 output='params/'+tag+'_candidate.json'
 run('merge',['tools/sensor_parameter_package.py','--results',*[state['results'][str(d)] for d in (0,120,240)],'--output',output])
 state.update(stage='merged_requires_validation',candidate=output);save()
except Exception as e:
 state.update(stage='failed',error=str(e));save();raise
