import json,os,sys,subprocess,concurrent.futures,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];os.chdir(R)
tag='09B8_20261110_first_joint';state={'stage':'starting','started':time.strftime('%Y-%m-%d %H:%M:%S'),'results':{}}
def save():Path('docs/'+tag+'_status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
common=['--sensor_params','params/09B8_20261110_first_joint_seed.json','--calibration_data_root','./09B8数据','--start_value','-32','--end_value','9','--full_segmentation','[3,4,2,4,2,3,2,2]','--multi_region_calib','True','--use_full_transported_phase','True','--full_point_calib','True','--end15cm_point_calib','True','--end5cm_point_calib','True','--full_preserve_first_point','True','--full_absolute_direction','False','--use_stored_zero','False','--method','L-BFGS-B','--max_iter','30','--min_loss_diff','1e-8','--exp_directs','[0,120,240]','--rot_ang','8']
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
 package=json.loads(Path(output).read_text(encoding='utf-8'))
 config=json.loads(Path(state['results']['0']).read_text(encoding='utf-8'))['regions']['full']['configuration']
 for group,values in package['shared_parameters'].items():
  for key in list(values):
   if key in config:values[key]=config[key]
 runtime=package['shared_parameters']['runtime_control_parameters']
 runtime.update(calibration_data_root='./09B8数据',full_segmentation=[3,4,2,4,2,3,2,2],segmentation=None,folder_path=None,radii=None,thresholds=None,straight_trim=None,weights=None,slopes=None)
 package['shared_parameters']['hardware_parameters']['ideal_len']=None
 package['shared_parameters']['reconstruction_parameters']['end_weights']=None
 package['shared_parameters']['reconstruction_parameters']['end_start']=None
 Path(output).write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
 state.update(stage='merged_requires_validation',candidate=output);save()
except Exception as e:
 state.update(stage='failed',error=str(e));save();raise
