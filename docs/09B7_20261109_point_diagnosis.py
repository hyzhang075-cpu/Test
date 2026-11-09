import sys,json,io,contextlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path.cwd()))
import main,calibration_batch
from optimiser import Optimiser
out={}
for d in (0,120,240):
 with contextlib.redirect_stdout(io.StringIO()):
  a=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_20261109_upstream_warm_start_candidate.json','--multi_region_calib','True','--direct',str(d),'--exp_directs','[0,120,240]','--full_segmentation','[2,5,2,4,2,2,2,3]'])
  a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
 samples={}
 for radius,frame in o.processed_Data['circ'][d].items():
  mag,ang,wt,sl,dg=o._assemble_multiregion_parameters(np.asarray(frame).T,d)
  phase=np.degrees(np.asarray(dg['final_theta_dynamic'])[0]);direction=np.degrees(ang)
  samples[str(radius)]=[{'point':int(pt),'phase_deg':float(phase[j]),'curvature':float(mag[j]),'direction_deg':float(direction[j]),'slope':float(sl[j])} for j,pt in enumerate(o.global_point_ids)]
 out[str(d)]={'rot_ang':float(o.rot_ang),'samples':samples}
 print('DIRECT',d,'rot_ang',o.rot_ang,'radius200',json.dumps(samples.get('200',samples.get('200.0')),ensure_ascii=False),flush=True)
Path('docs/09B7_20261109_warm_point_diagnostics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')


