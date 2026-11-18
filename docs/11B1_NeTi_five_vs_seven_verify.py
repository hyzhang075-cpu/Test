"""Constrained 11B1 layout screening and normal-reconstruction refinement."""
import contextlib,io,json,sys,time,copy,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
OUT=R/'docs/11B1_NeTi_five_vs_seven_replay';OUT.mkdir(exist_ok=True)
state={'stage':'loading','rows':[]};
def save():
 (OUT/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
def parts(n):
 if n==0:yield []
 for k in range(2,n+1):
  for rest in parts(n-k):yield [k]+rest
layouts=[a+b+c for a in parts(7) for b in parts(7) for c in parts(4) if 5<=len(a+b+c)<=7]
layouts.sort(key=lambda s:(len(s),sum(x*x for x in s),s))
state['layout_count']=len(layouts);save()
argv=json.loads((R/'docs/11B1_NeTi_five_segment_status.json').read_text(encoding='utf-8'))['argv']
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(argv+['--task','recon','--multi_region_calib','False','--optimization_region','full','--use_full_transported_phase','False','--sensor_params',str(R/'params/11B1_NeTi_preserved_five_segment/11B1_NeTi_five_segment_candidate.json')]);a.use_stored_zero=False
 ctx=main.configure_calibration_args(a);base=Optimiser(**optimizer_parameters(a))
seed=json.loads((R/'params/11B1_NeTi_preserved_five_segment/11B1_NeTi_five_segment_candidate.json').read_text(encoding='utf-8'))['regions']['full']
base.weights={int(d):np.asarray(v) for d,v in seed['weights'].items()}
base.slopes={int(d):np.asarray(v) for d,v in seed['slopes'].items()}
def setup(seg):
 o=copy.copy(base);o.weights=copy.deepcopy(base.weights);o.segmentation=seg;o.num_segments=len(seg);o.base_segments=o._calculate_segments(o.total_points)
 old=np.repeat(np.arange(len(base.segmentation)),base.segmentation)
 new=np.repeat(np.arange(len(seg)),seg)
 o.slopes={d:np.column_stack([base.slopes[d][:,old[new==j]].mean(axis=1) for j in range(len(seg))]) for d in o.exp_directs};o.slopes_shape=o.slopes[0].shape
 o.multi_region_parameters=None;o.assembled_phase_context=None;o._get_freeze_idx();return o

def metrics(o,d):
 rs={}
 for shape in o.calib_shapes:rs[shape],s=o.reconstruct_shapes(calib_shape=shape,direct=d,verbose=False)
 o._compute_error(s,rs)
 return {'point_ratio':float(o.avg_point_err['calib']),'end_ratio':float(o.avg_end_err['calib'])}


results=json.loads((R/'docs/11B1_NeTi_five_vs_seven/status.json').read_text(encoding='utf-8'))
report=[]
for row in results['rows']:
 o=setup(row['segmentation'])
 for d in (0,120,240):
  b=row['refined'][str(d)];o.slopes[d]=np.asarray(b['slopes']);o.weights[d]=np.asarray(b['weights']);o.rot_ang=b['rot_ang'];m=metrics(o,d)
  delta=max(abs(m[k]-b['metrics'][k]) for k in m)
  report.append({'segmentation':row['segmentation'],'direct':d,'metrics':m,'max_difference':delta,'rot_ang':o.rot_ang})
  print(report[-1],flush=True)
(OUT/'replay.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
