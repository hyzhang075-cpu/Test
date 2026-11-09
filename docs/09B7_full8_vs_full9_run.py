"""Controlled comparison: identical initialization and objectives, two full partitions."""
import copy,json,os,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R));os.chdir(R)
from tools.sensor_parameter_package import package_parser_defaults
source='params/09B7_20261109_interval_candidate.json'
base=package_parser_defaults(json.loads(Path(source).read_text(encoding='utf-8')))
tag='09B7_full8_vs_full9';state={'started':time.strftime('%Y-%m-%d %H:%M:%S'),'runs':[]}
def save():Path('docs/'+tag+'_status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
for name,seg in [('full9',[2,5,2,4,1,1,2,2,3]),('full8',[2,5,2,4,2,2,2,3])]:
 profiles=copy.deepcopy(base['calibration_regions'])
 for r,b in profiles.items():
  b['segmentation']=seg if r=='full' else ([2,2,3] if r=='end15cm' else [2,3])
  for k in ('weights','slopes','global_point_ids','global_segment_ids','owned_point_ids','coverage_aware_weights'):b.pop(k,None)
 for d in (0,120,240):
  log=Path(f'{tag}_{name}_direct{d}.log');before=set(Path('calibration_results').glob('09B7*/results.json'))
  args=['main.py','--task','optim','--sensor_params',source,'--multi_region_calib','True','--optimization_regions',"['full','end15cm','end5cm']",'--full_point_calib','True','--end15cm_point_calib','True','--end5cm_point_calib','True','--use_full_transported_phase','True','--use_stored_zero','False','--full_segmentation',repr(seg),'--calibration_regions',repr(profiles),'--weights','None','--slopes','None','--direct',str(d)]
  item={'scheme':name,'direct':d,'status':'running','log':str(log),'argv':args};state['runs'].append(item);save()
  with log.open('w',encoding='utf-8') as f:ret=subprocess.run([sys.executable,'docs/09B7_compat_dispatch.py',*args],stdout=f,stderr=subprocess.STDOUT,env=env).returncode
  item['status']='complete' if ret==0 else 'failed';item['returncode']=ret
  item['results']=[str(f) for f in set(Path('calibration_results').glob('09B7*/results.json'))-before if json.loads(f.read_text(encoding='utf-8')).get('direct')==d];save()
  if ret:raise SystemExit(ret)
state['stage']='comparison_optimization_complete';save()
