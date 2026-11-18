"""Constrained 11B1 layout screening and normal-reconstruction refinement."""
import contextlib,io,json,sys,time,copy,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
OUT=R/'docs/11B1_NeTi_240_least_squares';OUT.mkdir(exist_ok=True)
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

selected=json.loads((R/'docs/11B1_NeTi_seven_global_trial/status.json').read_text(encoding='utf-8'))['rows']
selected=[r for r in selected if r['segmentation']==[3,2,2,3,4,2,2]]
state['rows']=selected;state['stage']='per_level_full_geometry_refinement';save()
for row in selected:
 seg=row['segmentation'];o=setup(seg);row['coarse_refined']=copy.deepcopy(row.get('refined',{}))

 d=240
 from scipy.optimize import least_squares
 b=row['refined'][str(d)]
 s0=np.asarray(b['slopes']);w0=np.asarray(b['weights']);angle=b['rot_ang']
 x0=np.zeros(s0.size+w0.size+1)
 best=[np.inf,None,None]
 def evaluate(x):
  o.slopes[d]=s0+10*x[:s0.size].reshape(s0.shape)
  o.weights[d]=np.clip(w0*np.exp(x[s0.size:-1]),.1,5.)
  o.rot_ang=angle+10*x[-1]
  m=metrics(o,d)
  score=np.linalg.norm(list(m.values()),ord=8)
  if score<best[0]:best[:]=[score,x.copy(),m]
  pt=list(o.point_errors_avg['circ'].values());tip=list(o.end_errors['circ'].values())
  return np.asarray(pt+tip)
 evaluate(x0)
 bounds=np.r_[np.full(s0.size,6.),np.full(w0.size,.8),3.]
 for weight in (2.,5.,10.):
  def residual(x):
   e=evaluate(x);e[len(e)//2:]*=weight
   return e
  fit=least_squares(residual,best[1],bounds=(-bounds,bounds),max_nfev=100,x_scale='jac',ftol=1e-10,xtol=1e-10)
  print(weight,best[2],flush=True)
 evaluate(best[1])
 row['refined']['240']={'weights':o.weights[d].tolist(),'slopes':o.slopes[d].tolist(),'rot_ang':o.rot_ang,'metrics':best[2]}
 row['per_radius']['240']={str(k):float(v) for k,v in o.end_errors['circ'].items()}
 state['stage']='full_240_complete';save()
