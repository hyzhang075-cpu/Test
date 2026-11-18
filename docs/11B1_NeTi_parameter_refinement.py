"""Constrained 11B1 layout screening and normal-reconstruction refinement."""
import contextlib,io,json,sys,time,copy,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
OUT=R/'docs/11B1_NeTi_parameter_refinement';OUT.mkdir(exist_ok=True)
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

original=json.loads((R/'docs/11B1_NeTi_layout_search/status.json').read_text(encoding='utf-8'))
selected=[r for r in original['rows'] if r.get('refined') and len(r['refined'])==3]
state['rows']=selected;state['stage']='per_level_full_geometry_refinement';save()
for row in selected:
 seg=row['segmentation'];o=setup(seg);row['coarse_refined']=copy.deepcopy(row.get('refined',{}))
 for d in (0,120,240):
  state['active']={'segmentation':seg,'direct':d};save()
  o.direct=d;o.slopes_shape=o.slopes[d].shape;o._get_freeze_idx();o.max_iter=15
  # Preserve the calibrated geometric seed; refine against normal replay directly.
  previous=row.get('refined',{}).get(str(d));
  if previous:o.slopes[d]=np.asarray(previous['slopes']);o.weights[d]=np.asarray(previous['weights'])
  s0=o.slopes[d].copy();w0=np.asarray(o.weights[d]).copy();best=[float('inf'),None,None];n=[0]
  def assign(x):
   o.slopes[d]=s0+np.asarray(x[:s0.size]).reshape(s0.shape);o.weights[d]=np.clip(w0*np.exp(x[s0.size:]),.1,5.)
  def loss(x):
   assign(x);m=metrics(o,d);v=max(m.values())+.15*sum(m.values())
   if v<best[0]:best[:]=[v,np.asarray(x).copy(),m]
   n[0]+=1
   if n[0]%100==0:print('REFINE',seg,d,n[0],best[2],flush=True)
   return v
  x=np.zeros(s0.size+len(w0));loss(x)
  for attempt in range(3):
   previous=best[0]
   minimize(loss,best[1],method='L-BFGS-B',bounds=[(-40,40)]*s0.size+[(-.8,.8)]*len(w0),options={'maxiter':250,'maxfun':12000,'ftol':1e-12,'gtol':1e-7,'eps':1e-5})
   if max(best[2].values())<.01 or previous-best[0]<1e-6:break
  assign(best[1]);row['refined'][str(d)]={'metrics':best[2],'weights':o.weights[d].tolist(),'slopes':o.slopes[d].tolist(),'evaluations':n[0],'passed':max(best[2].values())<.01};save()
 row['full_passed']=all(v['passed'] for v in row['refined'].values());save()
 print('LAYOUT_DONE',seg,row['full_passed'],flush=True)
state['stage']='full_screen_and_refinement_complete_requires_local_fit_and_assembly';save()



