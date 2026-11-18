import json, os, sys, subprocess, time
from pathlib import Path
R=Path(__file__).resolve().parents[1];os.chdir(R)
sys.path.insert(0,str(R))
import main
preset=[510,521,532,543,554,565,576,587,607,627,647,667,687,707,807,907,1107,1307]
base=json.loads(Path('docs/09B8_20261110_split_configuration.json').read_text(encoding='utf-8'))
regions=base['regions']
seg=[2,2,2,1,2,2,2,1,2,2]
regions['full']['segmentation']=seg
regions['end15cm']['segmentation']=[2,2,2,1,2,2]
regions['end5cm']['segmentation']=[2,2]
# Local partitions are derived from the shared full-length partition.
argv=['--sensor_id','11B1_NeTi','--calibration_data_root','./1113-11B1-自研（1+3）18点79.7cmFBG+镍钛管','--start_value','114','--end_value','8','--samp_dist_preset',repr(preset),'--full_segmentation',repr(seg),'--calibration_regions',repr(regions),'--weights','None','--slopes','None','--use_stored_zero','False','--multi_region_calib','True','--exp_directs','[0,120,240]','--rot_ang','0','--method','L-BFGS-B','--max_iter','30','--full_point_calib','True','--end15cm_point_calib','True','--end5cm_point_calib','True','--use_full_transported_phase','True']
argv += ['--end5cm_independent_weights','False','--end5cm_independent_weight_score','False','--end5cm_coverage_aware_weights','False']
state={'stage':'initializing','results':{},'argv':argv}
def save():Path('docs/11B1_NeTi_status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
def run(label,args):
 with open('docs/11B1_NeTi_'+label+'.log','w',encoding='utf-8') as f:
  p=subprocess.run([sys.executable,*args],stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1'))
 if p.returncode:raise RuntimeError(label+' failed; see log')
try:
 save()
 for region in ['end5cm']:run('init_'+region,['main.py','--task','init','--optimization_region',region,*argv])
 state['stage']='optimizing';save()
 for d in [0,120,240]:
  before=set(R.glob('calibration_results/11B1_NeTi*/results.json'))
  run('optim_'+str(d),['main.py','--task','optim','--direct',str(d),*argv])
  found=set(R.glob('calibration_results/11B1_NeTi*/results.json'))-before
  assert len(found)==1,found
  state['results'][str(d)]=str(next(iter(found)).relative_to(R));save()
 run('merge',['tools/sensor_parameter_package.py','--results',*state['results'].values(),'--output','params/11B1_NeTi_candidate.json'])
 state['stage']='merged_requires_validation';save()
except Exception as e:
 state.update(stage='failed',error=str(e));save();raise




