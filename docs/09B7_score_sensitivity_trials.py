import json,contextlib,io,sys
from pathlib import Path
import numpy as np
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
source='params/09B7_absolute_assembly_dynamic_candidate.json';p=json.loads(Path(source).read_text(encoding='utf-8'))
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',source,'--multi_region_calib',str(m),'--optimization_region',r,'--use_full_transported_phase',str(m),'--exp_directs','[0,120,240]']);a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 o=make('full',True);loc={r:make(r,False) for r in ('end15cm','end5cm')}
ids=list(o.global_point_ids);cfg=o.multi_region_parameters;original={r:{'sharpness':cfg['regions'][r]['sharpness'],'weights':{d:w.copy() for d,w in cfg['regions'][r]['weights'].items()}} for r in loc};samples=[]
for r,src in [('full',o),*loc.items()]:
 for radius,f in src.processed_Data['circ'][0].items():
  if radius<=0:continue
  if r=='full':frame=np.asarray(f);crop=0.
  else:
   frame=np.asarray(o.processed_Data['circ'][0][0]).copy();frame[[ids.index(i) for i in src.global_point_ids]]=np.asarray(f);crop=src.calibration_context['crop_origin_m']
  samples.append((r,radius,frame,crop))
reports=[]
for sharp,smooth in ((4.8,False),(2.4,False),(1.6,False),(1.6,True),(.8,True)):
 for r in loc:
  b=cfg['regions'][r];b['sharpness']=sharp
  for d,w in original[r]['weights'].items():
   w=w.copy()
   if smooth and r=='end15cm':
    z=np.log(w);z=.25*np.r_[z[0],z[:-1]]+.5*z+.25*np.r_[z[1:],z[-1]];w=np.exp(z)
   b['weights'][d]=w
 metrics={r:[[],[]] for r in ('full','end15cm','end5cm')}
 for r,rad,f,crop in samples:
  s,c,_,_= _reconstruct_frame(o,f,0);ideal,_=straight_prefix_circular_tail(s,crop,rad/1000);err=np.linalg.norm(c-ideal,axis=1)/(s[-1]-crop);metrics[r][0].append(float(err[s>=crop-1e-12].mean()));metrics[r][1].append(float(err[-1]))
 sensitivity=[]
 for r,rad,f,crop in samples:
  if (r,rad) not in [('full',200),('end15cm',100),('end5cm',15),('end5cm',30)]:continue
  angles=[];curves=[]
  for scale in np.linspace(.5,1.5,101):
   dg=o._assemble_multiregion_parameters((f*scale).T,0)[-1];angles.append(dg['final_angle']);curves.append(dg['final_magnitude'])
  a=np.asarray(angles);k=np.asarray(curves);sensitivity.append({'region':r,'radius':rad,'angle_step_deg_16_17':float(np.max(abs(np.rad2deg(np.angle(np.exp(1j*np.diff(a[:,15:17],axis=0))))))),'curvature_step_16_17':float(np.max(abs(np.diff(k[:,15:17],axis=0)))),'angle_step_deg_18_22':float(np.max(abs(np.rad2deg(np.angle(np.exp(1j*np.diff(a[:,17:],axis=0)))))))})
 record={'sharpness':sharp,'smooth_end15_weights':smooth,'replay':{r:{'point_ratio':float(np.mean(v[0])),'end_ratio':float(np.mean(v[1]))} for r,v in metrics.items()},'synthetic_sensitivity':sensitivity};reports.append(record);print(json.dumps(record),flush=True)
Path('docs/09B7_score_sensitivity_trials.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
