import contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
source=R/'params/11B1_NeTi_expanded.json';p=json.loads(source.read_text(encoding='utf-8'))
def make(r,m):
 a=main.parse_main_args(json.loads((R/'docs/11B1_NeTi_status.json').read_text(encoding='utf-8'))['argv']+['--task','recon','--sensor_params',str(source),'--multi_region_calib',str(m),'--optimization_region',r,'--exp_directs','[0,120,240]','--end5cm_independent_weights','False','--end5cm_independent_weight_score','False','--end5cm_coverage_aware_weights','False']);a.use_stored_zero=False
 c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 full=make('full',True);local={r:make(r,False) for r in ('end15cm','end5cm')}
ids=list(full.global_point_ids);cfg=full.multi_region_parameters;report={}
for d in (0,120,240):
 blocks={r:cfg['regions'][r] for r in cfg['region_order']}
 originals={r:(b['slopes'][d].copy(),b['weights'][d].copy()) for r,b in blocks.items()}
 samples=[]
 for name,o in [('full',full),*local.items()]:
  for radius in o.radii[d]['circ']:
   if name=='full':frame=np.asarray(full.processed_Data['circ'][d][radius]);crop=0.
   else:
    frame=np.asarray(full.processed_Data['circ'][d][0]).copy();idx=[ids.index(v) for v in o.global_point_ids];frame[idx]=np.asarray(o.processed_Data['circ'][d][radius]);crop=o.calibration_context['crop_origin_m']
   samples.append((name,radius,frame,crop))
 count=[0];best=[float('inf'),None,None]
 def assign(x):
  full.rot_ang=0.0
  for i,(r,b) in enumerate(blocks.items()):
   s,w=originals[r];b['slopes'][d]=s.copy();b['slopes'][d][:,0]+=x[1+i];b['weights'][d]=np.clip(w*np.exp(x[4+i]),.6,5.)
 def evaluate(x):
  assign(x);vals={r:[[],[]] for r in blocks}
  for name,radius,frame,crop in samples:
   s,curve,_,diag=_reconstruct_frame(full,frame,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000.)
   e=np.linalg.norm(curve-ideal,axis=1)/(s[-1]-crop);vals[name][0].append(float(e[s>=crop-1e-12].mean()));vals[name][1].append(float(e[-1]))
  metrics={r:{'point_ratio':float(np.mean(v[0])),'end_ratio':float(np.mean(v[1]))} for r,v in vals.items()}
  errors=[v for m in metrics.values() for v in m.values()];score=max(errors)+float(np.mean(errors))
  if score<best[0]:best[:]=[score,np.asarray(x).copy(),metrics]
  count[0]+=1
  if count[0]%50==0:print(d,count[0],best[0],flush=True)
  return score
 x=np.zeros(7);x[0]=0.0;evaluate(x);baseline=best[2]
 for trial in range(0):
  old=best[0];minimize(evaluate,best[1],method='Powell',bounds=[(-1e-8,1e-8)]+[(-50,50)]*3+[(-.7,.7)]*3,options={'maxiter':15,'maxfev':1100,'xtol':1e-3,'ftol':1e-5})
  if old-best[0]<1e-5:break
 assign(best[1]);report[str(d)]={'baseline':baseline,'selected':best[2],'variables':best[1].tolist(),'evaluations':count[0]}
 for r,b in blocks.items():p['regions'][r]['slopes'][str(d)]=b['slopes'][d].tolist();p['regions'][r]['weights'][str(d)]=b['weights'][d].tolist()
 # Rotation is reported per direction; package retains shared rotation until unified replay is checked.
 p['provenance']['assembly_refinement']=report
 (R/'params/11B1_NeTi_best_tested.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
 (R/'docs/11B1_NeTi_best_tested_replay.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print('COMPLETED',d,json.dumps(report[str(d)]),flush=True)




