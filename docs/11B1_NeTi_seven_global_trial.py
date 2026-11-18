"""Constrained 11B1 layout screening and normal-reconstruction refinement."""
import contextlib,io,json,sys,time,copy,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
OUT=R/'docs/11B1_NeTi_seven_global_trial';OUT.mkdir(exist_ok=True)
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

selected=json.loads((R/'docs/11B1_NeTi_lowdim_search/status.json').read_text(encoding='utf-8'))['rows']
selected=[r for r in selected if r['segmentation']==[3,2,2,3,4,2,2]]
state['rows']=selected;state['stage']='per_level_full_geometry_refinement';save()
for row in selected:
 seg=row['segmentation'];o=setup(seg);row['coarse_refined']=copy.deepcopy(row.get('refined',{}))
 for d in (240,0,120):
  state['active']={'segmentation':seg,'direct':d};save()
  o.direct=d;o.slopes_shape=o.slopes[d].shape;o._get_freeze_idx();o.max_iter=15
  # Preserve the calibrated geometric seed; refine against normal replay directly.
  previous=row.get('refined',{}).get(str(d));
  if previous:o.slopes[d]=np.asarray(previous['slopes']);o.weights[d]=np.asarray(previous['weights'])
  s0=o.slopes[d].copy();w0=np.asarray(o.weights[d]).copy();best=[float('inf'),None,None];n=[0]
  def assign(x):
   o.slopes[d]=s0+np.asarray(x[:len(seg)])[None,:]
   o.weights[d]=np.clip(w0*np.exp(x[-2]),.1,5.)
   o.rot_ang=angle+x[-1]
  def loss(x):
   assign(x);m=metrics(o,d);v=float(np.linalg.norm(np.asarray(list(m.values())),ord=8))
   if v<best[0]:best[:]=[v,np.asarray(x).copy(),m]
   n[0]+=1
   if n[0]%100==0:
    state['live']={'segmentation':seg,'direct':d,'evaluations':n[0],'metrics':best[2]};save();print('REFINE',seg,d,n[0],best[2],flush=True)
   return v
  angle=float(previous['rot_ang'])
  x=np.zeros(len(seg)+2);loss(x)
  rng=np.random.default_rng(1700+d)
  from scipy.optimize import differential_evolution
  bounds=[(-60,60)]*len(seg)+[(-.7,.7),(-90,90)]
  # Search the entire bounded offset space as well as the incumbent basin.
  for seed in (17,29):
   fit=differential_evolution(loss,bounds,seed=seed+d,x0=best[1],maxiter=55,popsize=7,polish=False)
   for start in (fit.x,best[1].copy()):
    minimize(loss,start,method='L-BFGS-B',bounds=bounds,options={'maxiter':120,'ftol':1e-13,'eps':1e-5})
  assign(best[1]);metrics(o,d)
  row.setdefault('per_radius',{})[str(d)]={str(k):float(v) for k,v in o.end_errors['circ'].items()}
  assign(best[1]);row['refined'][str(d)]={'metrics':best[2],'rot_ang':float(o.rot_ang),'weights':o.weights[d].tolist(),'slopes':o.slopes[d].tolist(),'evaluations':n[0],'passed':max(best[2].values())<.01};save()
 row['full_passed']=all(v['passed'] for v in row['refined'].values());save()
 print('LAYOUT_DONE',seg,row['full_passed'],flush=True)
state['stage']='full_screen_and_refinement_complete_requires_local_fit_and_assembly';save()




