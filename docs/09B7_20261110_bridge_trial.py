import sys,json,io,contextlib,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import main,calibration_batch
from optimiser import Optimiser
from scipy.optimize import lsq_linear
source='params/09B7_20261110_boundary14_candidate.json';p=json.loads(Path(source).read_text(encoding='utf-8'));report={}
for d,name in [(0,'end15cm'),(120,'end5cm')]:
 with contextlib.redirect_stdout(io.StringIO()):
  a=main.parse_main_args(['--task','recon','--sensor_params',source,'--multi_region_calib','True','--direct',str(d),'--full_segmentation','[2,5,2,4,1,1,2,2,3]','--start_value','19','--end_value','6','--use_stored_zero','False'])
  main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
 block=o.multi_region_parameters['regions'][name];idx=list(o.global_point_ids).index(block['support_point_ids'][0]);gap=o.samp_dist[idx]-o.samp_dist[idx-1];X=[];y=[];old=[]
 for r,frame in o.processed_Data['circ'][d].items():
  if float(r)<=0:continue
  dg=o._assemble_multiregion_parameters(np.asarray(frame).T,d)[-1];angles=np.asarray(dg['final_angle']);jump=np.angle(np.exp(1j*(angles[idx]-angles[idx-1])))
  X.append(np.asarray(dg[name]['slope_masses'])[:,0]*gap);y.append(-jump);old.append(float(np.degrees(jump)))
 X=np.asarray(X);y=np.asarray(y);n=X.shape[1]
 fit=lsq_linear(np.vstack([X,.002*np.eye(n)]),np.r_[y,np.zeros(n)],bounds=(-80,80))
 p['regions'][name].setdefault('bridge_slope_corrections',{})[str(d)]=fit.x.tolist()
 after=np.degrees(np.angle(np.exp(1j*(np.deg2rad(old)+X@fit.x))))
 report[str(d)]={'region':name,'max_before_deg':max(abs(np.array(old))),'max_after_deg':max(abs(after)),'per_sample_after_deg':after.tolist(),'corrections_rad_per_m':fit.x.tolist()}
 print(d,report[str(d)],flush=True)
p['shared_parameters']['runtime_control_parameters']['full_segmentation']=[2,5,2,4,1,1,2,2,3]
p['multi_region']['deployment_ready']=False
Path('params/09B7_20261110_bridge_trial.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
Path('docs/09B7_20261110_bridge_trial.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
