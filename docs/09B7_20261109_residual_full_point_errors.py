import sys,json,io,contextlib,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import main,calibration_batch
from optimiser import Optimiser
out={}
for d in (0,120,240):
 with contextlib.redirect_stdout(io.StringIO()):
  a=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_20261109_residual_restart_candidate.json','--multi_region_calib','False','--optimization_region','full','--full_segmentation','[2,5,2,4,2,2,2,3]','--start_value','19','--end_value','6','--use_stored_zero','False','--direct',str(d),'--exp_directs','[0,120,240]'])
  main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
  curves,s=o.reconstruct_shapes(calib_shape='circ',direct=d,verbose=False);ideals=o._construct_ideals(calib_shape='circ',interp_dist=s-s[0],val_len=float(s[-1]-s[0]))
 samples={}
 for radius,c in curves.items():
  if float(radius)<=0:continue
  e=np.linalg.norm(np.asarray(c)-ideals[radius],axis=1)/(s[-1]-s[0])*100
  samples[str(radius)]=np.interp(o.samp_dist,s,e).tolist()
 avg=np.mean(list(samples.values()),axis=0);out[str(d)]={'point_mean_percent':avg.tolist(),'samples':samples}
 print(d,'ALL',np.round(avg,3).tolist(),flush=True)
Path('docs/09B7_20261109_residual_full_point_errors.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
