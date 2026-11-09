"""Trial only two regional first-segment slope offsets; no algorithm changes."""
import sys,json,io,contextlib
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
src=R/'params/09B7_NeTi_recalib_boundary_checked.json';p=json.loads(src.read_text(encoding='utf-8'))
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(src),'--multi_region_calib','True','--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
ids=list(o.global_point_ids);cfg=o.multi_region_parameters;report={};selected={}
for d in (0,):
 base={r:cfg['regions'][r]['slopes'][d].copy() for r in ('end15cm','end5cm')}
 sizes=[len(v) for v in base.values()];n=sum(sizes)
 def assign(x):
  off=0
  for r,size in zip(base,sizes):
   cfg['regions'][r]['slopes'][d]=base[r].copy();cfg['regions'][r]['slopes'][d][:,0]+=np.asarray(x)[off:off+size];off+=size
 frames=[(rad,np.asarray(f)) for rad,f in o.processed_Data['circ'][d].items() if rad>0]
 angles=[];J=[]
 for rad,f in frames:
  assign(np.zeros(n));dg=o._assemble_multiregion_parameters(f.T,d)[-1];v=np.asarray(dg['final_angle']);pair=np.array([v[15]-v[14],v[17]-v[16]]);cols=[]
  for x in np.eye(n):
   assign(x);w=np.asarray(o._assemble_multiregion_parameters(f.T,d)[-1]['final_angle']);diff=np.array([w[15]-w[14],w[17]-w[16]])-pair;cols.append(np.angle(np.exp(1j*diff)))
  angles.extend(pair);J.extend(np.column_stack(cols))
 angles=np.asarray(angles);J=np.asarray(J)
 def loss(x):
  e=angles+J@x;return np.r_[np.sin(e),1-np.cos(e),.001*x]
 fits=[least_squares(loss,z,bounds=(-120,120),max_nfev=150) for z in (np.zeros(n),)];fit=min(fits,key=lambda f:np.linalg.norm(f.fun))
 trials=[]
 for factor in (0,.25,.5,.75,1):
  x=fit.x*factor;assign(x);errs=[];ends=[];jumps=[]
  for rad,f in frames:
   s,c,t,dg=_reconstruct_frame(o,f,d);ideal,_=straight_prefix_circular_tail(s,0,rad/1000);err=np.linalg.norm(c-ideal,axis=1)/(s[-1]-s[0]);errs.append(float(err.mean()));ends.append(float(err[-1]));v=np.asarray(dg['final_angle']);jumps.append(np.rad2deg(abs(np.angle(np.exp(1j*np.array([v[15]-v[14],v[17]-v[16]]))))).tolist())
  trials.append({'factor':factor,'offsets_rad_per_m':x.tolist(),'full_replay_point_ratio':float(np.mean(errs)),'full_replay_end_ratio':float(np.mean(ends)),'boundary_max_deg':np.max(jumps,axis=0).tolist()})
 best=min(trials,key=lambda v:max(v['boundary_max_deg'])+100*max(v['full_replay_end_ratio']-trials[0]['full_replay_end_ratio'],0));selected[str(d)]=best;assign(best['offsets_rad_per_m'])
 for r in base:p['regions'][r]['slopes'][str(d)]=cfg['regions'][r]['slopes'][d].tolist()
 report[str(d)]={'trials':trials,'selected':best};print(d,json.dumps(report[str(d)]),flush=True)
p['multi_region']['deployment_ready']=False;p['provenance']['boundary_offset_trial']={'source':str(src),'report':'docs/09B7_boundary_offset_level_report.json','only_local_first_segment_slopes_changed':True,'validation_pending':True}
(R/'params/09B7_NeTi_recalib_boundary_level_trial.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');(R/'docs/09B7_boundary_offset_level_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
