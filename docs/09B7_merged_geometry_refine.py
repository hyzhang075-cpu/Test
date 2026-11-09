"""Bounded parameter trial; original source and full coefficients stay unchanged."""
import contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
SOURCE=ROOT/'params/09B7_20261102_merged_geometry_trial.json'
p=json.loads(SOURCE.read_text(encoding='utf-8'))
rot=json.loads((ROOT/'docs/09B7-20261102-local-rotation-audit.json').read_text(encoding='utf-8'))
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(SOURCE),'--multi_region_calib',str(m),'--optimization_region',r,'--exp_directs','[0,120,240]']);a.use_stored_zero=False
 c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 full=make('full',True);local={r:make(r,False) for r in ('end15cm','end5cm')}
ids=list(full.global_point_ids);dist=np.asarray(full.samp_dist);cfg=full.multi_region_parameters;report={}
for d in (0,120,240):
 b15=cfg['regions']['end15cm'];b5=cfg['regions']['end5cm']
 s15=b15['slopes'][d].copy();s5=b5['slopes'][d].copy();w15=b15['weights'][d].copy();w5=b5['weights'][d].copy()
 samples=[]
 for name,o in [('full',full),*local.items()]:
  for radius in o.radii[d]['circ']:
   if radius<=0:continue
   if name=='full':frame=np.asarray(full.processed_Data['circ'][d][radius]);crop=0.
   else:
    frame=np.asarray(full.processed_Data['circ'][d][0]).copy();idx=[ids.index(v) for v in o.global_point_ids];frame[idx]=np.asarray(o.processed_Data['circ'][d][radius]);crop=o.calibration_context['crop_origin_m']
   samples.append((name,radius,frame,crop))
 def assign(x):
  b15['slopes'][d]=s15.copy();b15['slopes'][d][:,0]+=x[0]
  b5['slopes'][d]=s5.copy();b5['slopes'][d][:,0]+=x[1];b5['slopes'][d][:,1]+=x[2]
  b15['weights'][d]=np.clip(w15*np.exp(x[3]),.1,8.)
  b5['weights'][d]=np.clip(w5.reshape(3,-1)*np.exp(np.asarray(x[4:7]))[:,None],.1,8.).reshape(-1)
 count=[0];best=[float('inf'),None,None]
 def evaluate(x,verbose=False):
  assign(x);vals={r:[[],[]] for r in ('full','end15cm','end5cm')};phase={r:[] for r in local}
  for name,radius,frame,crop in samples:
   s,curve,_,diag=_reconstruct_frame(full,frame,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000.)
   e=np.linalg.norm(curve-ideal,axis=1)/(s[-1]-crop)
   vals[name][0].append(float(e[s>=crop-1e-12].mean()));vals[name][1].append(float(e[-1]))
   if name!='full':
    j=ids.index(local[name].global_point_ids[0]);pred=full.global_phases_set+np.dot(np.asarray(diag['slope_map'])[1:j+1],np.diff(dist[:j+1]))
    ref=p['provenance']['local_global_phases_set'][name][str(d)]+np.deg2rad(rot[name][str(d)]['rot_ang']-full.rot_ang)
    phase[name].append(float(abs(np.angle(np.exp(1j*(pred-ref))))))
  metrics={r:{'point':float(np.mean(v[0])),'end':float(np.mean(v[1]))} for r,v in vals.items()}
  phase_max={r:float(np.rad2deg(max(v))) for r,v in phase.items()}
  ratios=[v/(.01 if r=='full' else .1) for r,m in metrics.items() for v in m.values()]
  ratios.extend(v/30 for v in phase_max.values())
  score=max(ratios)+.05*float(np.mean(ratios))
  result={'metrics':metrics,'aligned_phase_max_deg':phase_max,'max_target_ratio':max(ratios)}
  if score<best[0]:best[:]=[score,np.asarray(x).copy(),result]
  count[0]+=1
  if count[0]%25==0 or verbose:print(json.dumps({'direct':d,'evaluations':count[0],**result}),flush=True)
  return score
 evaluate(np.zeros(7),True)
 bounds=[(-50,50),(-70,70),(-70,70),(-1.5,1.1),(-2.,1.1),(-1.5,1.1),(-1.5,1.1)]
 minimize(evaluate,np.zeros(7),method='Powell',bounds=bounds,options={'maxiter':35,'maxfev':2200,'xtol':1e-3,'ftol':1e-4})
 assign(best[1]);report[str(d)]={'parameters':best[1].tolist(),**best[2]}
 for name,b in [('end15cm',b15),('end5cm',b5)]:
  p['regions'][name]['slopes'][str(d)]=b['slopes'][d].tolist();p['regions'][name]['weights'][str(d)]=b['weights'][d].tolist()
 print(json.dumps({'direct':d,'selected':report[str(d)]}),flush=True)
 # Save each completed direction, but never mark an unfinished trial deployable.
 p['provenance']['merged_geometry_refinement']={'report':'docs/09B7-20261102-merged-refine.json','source':str(SOURCE),'phase_basis':'local references aligned by independently fitted local replay rotation, not raw stored phase difference','complete_directions':list(report)}
 p['shared_parameters']['optimization_hyperparameters']['weight_bounds']=[.1,8.]
 p['shared_parameters']['optimization_hyperparameters']['slope_upper_bound']=250.
 (ROOT/'params/09B7_20261102_merged_refine_candidate.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'docs/09B7-20261102-merged-refine.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
