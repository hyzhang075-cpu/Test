import sys,json,io,contextlib
from pathlib import Path
import numpy as np
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from calibration_phase_reference import _mixed_slopes
z=np.load('docs/09B7_dynamic_112516_arrays.npz');raw=z['raw_data'];record=z['angle'];krec=z['magnitude'];time=z['timestamp']-z['timestamp'][0]
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_dynamic_smooth_score_trial.json','--multi_region_calib','True','--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
angles=[];theta=[];slopes=[];weights=[];fullangles=[];mags=[]
for f in raw:
 _,_,frame,_=o._process_centreData(f.copy());dg=o._assemble_multiregion_parameters(frame.T,0)[-1];angles.append(dg['final_angle']);theta.append(np.asarray(dg['final_theta_dynamic'])[0]);slopes.append(dg['slope_map']);weights.append(dg['final_weight']);mags.append(dg['final_magnitude']);full=_mixed_slopes(o,frame,0);sg,sl=o._generate_dynamic_segments(full);al=o._calculate_dynamic_angles(mode='recon',segments=sg,seg_slopes=sl);_,angle=o._calculate_curvature_and_angle(epsilon=frame.T,alpha_dynamic=al);fullangles.append(angle)
angles=np.asarray(angles);theta=np.asarray(theta);slopes=np.asarray(slopes);weights=np.asarray(weights);fullangles=np.asarray(fullangles);mags=np.asarray(mags)
wrap=lambda x:np.rad2deg(np.angle(np.exp(1j*x)))
report={'frames':len(raw),'seconds':float(time[-1]),'max_record_angle_difference_deg':float(np.max(abs(wrap(angles-record)))),'max_record_curvature_difference':float(np.max(abs(mags-krec))),'points':{},'events':[]}
for j in range(14,22):
 active=(krec[1:,j]>5)&(krec[:-1,j]>5);jump=abs(wrap(np.diff(record[:,j])));idx=np.flatnonzero(active & (jump>30));report['points'][str(j+1)]={'active_frames':int(np.sum(krec[:,j]>5)),'jump_over30_count':len(idx),'jump_max_deg':float(max(jump[active])) if active.any() else None}
 if j in (15,16,17,18,19,20):
  for i in idx[np.argsort(jump[idx])[-3:]]:
   report['events'].append({'point':j+1,'time_s':float(time[i+1]),'frame':int(i+1),'direction_jump_deg':float(wrap(record[i+1,j]-record[i,j])),'phase_jump_deg':float(np.degrees(theta[i+1,j]-theta[i,j])),'k_before_after':krec[i:i+2,j].tolist(),'point_slope_before_after':slopes[i:i+2,j].tolist(),'point_weight_before_after':weights[i:i+2,j].tolist(),'raw_change_norm':float(np.linalg.norm(raw[i+1]-raw[i]))})
report['events']=sorted(report['events'],key=lambda x:x['time_s']);print(json.dumps(report,indent=2),flush=True)
np.savez_compressed('docs/09B7_dynamic_112516_replay.npz',angle=angles,phase=theta,slope=slopes,weight=weights,full_angle=fullangles,magnitude=mags,time=time)
Path('docs/09B7_dynamic_112516_diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
