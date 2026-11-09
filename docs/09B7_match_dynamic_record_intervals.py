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

files=['params/09B7_dynamic_smooth_score_trial.json','params/09B7_absolute_assembly_dynamic_candidate.json','params/09B7_NeTi_new.json','params/09B7_absolute_assembly_reoptim_candidate.json','params/09B7_absolute_assembly_reoptim_round2.json']
results=[]
for filename in files:
 if not Path(filename).exists():continue
 package=json.loads(Path(filename).read_text(encoding='utf-8'))
 for mode in ('full_interval','level0_interval'):
  o.multi_region_parameters=o._normalise_multiregion_parameters(package);o.multi_region_parameters['use_full_transported_phase']=mode!='legacy';errors=[];kerrors=[]
  for i in (300,800,1400,2000,2400,2500,2800,2864,3000):
   _,_,frame,_=o._process_centreData(raw[i].copy());dg=o._assemble_multiregion_parameters(frame.T,0)[-1];angle=np.asarray(dg['final_angle'])
   if mode=='both_full':
    slopes=np.asarray(dg['slope_map']);full=_mixed_slopes(o,frame,0);target=o.global_phases_set+np.r_[0.,np.cumsum(full[1:]*np.diff(o.samp_dist))];j=17;phase=np.asarray(dg['final_theta_dynamic'])[0];angle[j:]+=target[j]-phase[j]
   if mode in ('full_interval','level0_interval'):
    j=17;current=np.asarray(dg['slope_map']);full=_mixed_slopes(o,frame,0)
    labels=o._local_segment_labels(o.multi_region_parameters['regions']['full']['local_segmentation'])
    desired=full[j] if mode=='full_interval' else o.slopes[0][0,labels[j]]
    angle[j:]+=(desired-current[j])*(o.samp_dist[j]-o.samp_dist[j-1])
   mask=krec[i]>5
   if mask.any():errors.extend(abs(np.degrees(np.angle(np.exp(1j*(angle-record[i])))))[mask]);kerrors.extend(abs(np.asarray(dg['final_magnitude'])-krec[i]))
  if errors:results.append({'file':filename,'mode':mode,'median_deg':float(np.median(errors)),'max_deg':float(np.max(errors)),'curvature_max_diff':float(np.max(kerrors))})
results=sorted(results,key=lambda x:x['max_deg']);print(json.dumps(results,indent=2));Path('docs/09B7_dynamic_record_interval_match.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
