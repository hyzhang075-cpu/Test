"""Refine weights without changing any slope or measured phase reference."""
import contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
source=ROOT/'params/09B7_20261102_raw_phase_candidate.json';p=json.loads(source.read_text(encoding='utf-8'))
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(source),'--multi_region_calib','False','--optimization_region','full','--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a))
base=o.weights[0].copy();best=[float('inf'),None,None];calls=0
class Done(Exception):pass
def loss(x):
 global calls
 o.weights[0]=base*np.exp(x);rs,s=o.reconstruct_shapes(calib_shape='circ',direct=0,verbose=False);o._compute_error(interp_dist=s,rs={'circ':rs});m={'point':float(o.avg_point_err['calib']),'end':float(o.avg_end_err['calib'])}
 if max(m.values())<best[0]:best[:]=[max(m.values()),x.copy(),m]
 calls+=1
 if calls%10==0:print(calls,m,flush=True)
 if max(m.values())<.0097:raise Done()
 ideals=o._construct_ideals(calib_shape='circ',interp_dist=s-s[0],val_len=float(s[-1]-s[0]));parts=[]
 for r,c in rs.items():
  e=(np.asarray(c)-ideals[r])/(s[-1]-s[0]);idx=np.linspace(0,len(s)-1,30).astype(int);parts.extend([e[idx].reshape(-1)/np.sqrt(len(idx)),3*e[-1]])
 return np.r_[np.concatenate(parts),.0001*x]
try:least_squares(loss,np.zeros(len(base)),bounds=(-.3,.3),max_nfev=30,diff_step=1e-4)
except Done:pass
p['regions']['full']['weights']['0']=(base*np.exp(best[1])).tolist();p['provenance']['original_phase_refinement']['full0_weight_refine']=best[2];source.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');print(best[2],flush=True)
