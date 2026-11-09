import sys,io,contextlib,json
from pathlib import Path
import numpy as np
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from calibration_phase_reference import _mixed_slopes
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_NeTi_recalib.json','--multi_region_calib','True','--use_full_transported_phase','True','--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
with contextlib.redirect_stdout(io.StringIO()):
 b=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_NeTi_recalib.json','--multi_region_calib','False','--optimization_region','full','--exp_directs','[0,120,240]']);b.use_stored_zero=False;main.configure_calibration_args(b);single=Optimiser(**calibration_batch.optimizer_parameters(b))
count=0;maximum=0.;angle_max=0.
for d in (0,120,240):
 for radius,frame in o.processed_Data['circ'][d].items():
  if radius<=0:continue
  frame=np.asarray(frame);o.multi_region_parameters['use_full_transported_phase']=False;old=o._assemble_multiregion_parameters(frame.T,d)[-1]
  o.multi_region_parameters['use_full_transported_phase']=True;new=o._assemble_multiregion_parameters(frame.T,d)[-1]
  _,full_angle=single._Strain_2_Cur(keys=None,calib_shape='circ',calib_Data=frame,weight=single.weights[d],slope=single.slopes[d],direct=d)
  full=_mixed_slopes(o,frame,d);target=np.r_[0.,np.cumsum(full[1:]*np.diff(o.samp_dist))]+o.global_phases_set
  for name in ('end15cm',):
   j=list(o.global_point_ids).index(o.multi_region_parameters['regions'][name]['support_point_ids'][0]);error=abs(np.asarray(new['final_theta_dynamic'])[0,j]-target[j]);maximum=max(maximum,float(error));assert error<1e-10
   angle_error=abs(np.angle(np.exp(1j*(new['final_angle'][j]-full_angle[j]))));angle_max=max(angle_max,float(angle_error));assert angle_error<1e-10
  j=list(o.global_point_ids).index(o.multi_region_parameters['regions']['end5cm']['support_point_ids'][0])
  upstream=new['end15cm'];k=upstream['support_point_ids'].index(int(o.global_point_ids[j]));expected=upstream['effective_support_slopes'][k]
  assert abs(new['slope_map'][j]-expected)<1e-12
  theta=np.asarray(new['final_theta_dynamic'])[0];assert abs(theta[j]-theta[j-1]-expected*(o.samp_dist[j]-o.samp_dist[j-1]))<1e-10
  anchors={list(o.global_point_ids).index(x['first_point_id']) for x in new['full_mixed_phase_anchors']};owned=set(o.multi_region_parameters['regions']['full']['owned_point_ids'])
  for j,pt in enumerate(o.global_point_ids):
   if j not in anchors and pt not in owned:assert abs(new['slope_map'][j]-old['slope_map'][j])<1e-12
  assert new['final_weight']==old['final_weight'];count+=1
out={'maximum_angle_difference_vs_single_full_rad':angle_max,'frames':count,'maximum_anchor_error_rad':maximum,'local_internal_slopes_unchanged':True,'weights_unchanged':True};Path('docs/full_mixed_phase_anchor_check.json').write_text(json.dumps(out,indent=2));print(out)
