"""Refine full's unowned tail coefficients, leaving merged inference unchanged."""
import contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
source=ROOT/'params/09B7_20261102_joint_candidate.json'
fragment=ROOT/'docs/09B7-20261102-jointweights-feasible-direct120.json'
p=json.loads(source.read_text(encoding='utf-8'));f=json.loads(fragment.read_text(encoding='utf-8'))
assert not p['multi_region']['use_full_transported_phase']
assert p['regions']['full']['owned_point_ids']==list(range(1,16))
assert p['regions']['full']['local_segmentation']==[2,2,3,2,4,2,2,3,2]
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(source),'--multi_region_calib','False','--optimization_region','full','--direct','120','--exp_directs','[0,120,240]'])
 a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a))
base=o.slopes[120].copy();best=[float('inf'),None,None,None];calls=[0]
class TargetReached(Exception):pass
def evaluate(delta):
 s=base.copy();s[:,6:9]+=np.asarray(delta).reshape(6,3);o.slopes[120]=s
 rs,dist=o.reconstruct_shapes(calib_shape='circ',direct=120,verbose=False)
 o._compute_error(interp_dist=dist,rs={'circ':rs})
 metrics={'point':float(o.avg_point_err['calib']),'end':float(o.avg_end_err['calib'])}
 nonzero={'point':float(np.mean([v for r,v in o.point_errors_avg['circ'].items() if r>0])),'end':float(np.mean([v for r,v in o.end_errors['circ'].items() if r>0]))}
 score=max(metrics.values())
 if score<best[0]:best[:]=[score,np.asarray(delta).copy(),metrics,nonzero]
 ideals=o._construct_ideals(calib_shape='circ',interp_dist=dist-dist[0],val_len=float(dist[-1]-dist[0]));parts=[]
 for radius,curve in rs.items():
  error=(np.asarray(curve)-np.asarray(ideals[radius]))/(dist[-1]-dist[0]);idx=np.unique(np.linspace(0,len(dist)-1,40).astype(int))
  parts.append(error[idx].reshape(-1)/np.sqrt(len(idx)*len(rs)));parts.append(3*error[-1]/np.sqrt(len(rs)))
 calls[0]+=1
 if calls[0]%25==0:print(calls[0],metrics,flush=True)
 if score<=.0098:raise TargetReached()
 return np.r_[np.concatenate(parts),.00001*np.asarray(delta)]
try:least_squares(evaluate,np.zeros(18),bounds=(-30.,30.),max_nfev=50,ftol=1e-7,xtol=1e-7,gtol=1e-7,diff_step=1e-4)
except TargetReached:pass
s=base.copy();s[:,6:9]+=best[1].reshape(6,3)
assert np.array_equal(s[:,:6],base[:,:6])
f['full_slopes']=s.tolist();f['metrics_nonzero_replay']['standalone/full']=best[3]
f['full_static_tail_refine']={'source':str(source),'changed_columns':[6,7,8],'formal_metric_basis':'all available full calibration radii, including straight state','metrics':best[2],'merged_parameters_unchanged_by_ownership':True}
out=ROOT/'docs/09B7-20261102-jointweights-final-direct120.json';out.write_text(json.dumps(f,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'output':str(out),'metrics':best[2]}),flush=True)
