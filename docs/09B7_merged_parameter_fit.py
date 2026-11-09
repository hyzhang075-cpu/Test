"""Parameter-only assembly trial using production assembly and reconstruction."""
import contextlib, io, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares, lsq_linear
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame, straight_prefix_circular_tail
SOURCE=ROOT/'params/09B7_20261102_local_restart_candidate.json'
OUTPUT=ROOT/'params/09B7_20261102_merged_geometry_trial.json'
p=json.loads(SOURCE.read_text(encoding='utf-8'))
def make(region,merged):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(SOURCE),'--multi_region_calib',str(merged),'--optimization_region',region,'--exp_directs','[0,120,240]'])
 a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 full=make('full',True);local={r:make(r,False) for r in ('end15cm','end5cm')}
cfg=full.multi_region_parameters;ids=list(full.global_point_ids);dist=np.asarray(full.samp_dist)
regions=('end15cm','end5cm');report={}
for d in (0,120,240):
 samples=[]
 for name,obj in [('full',full),*local.items()]:
  for radius in obj.radii[d]['circ']:
   if radius<=0:continue
   if name=='full':frame=np.asarray(full.processed_Data['circ'][d][radius]);crop=0.
   else:
    frame=np.asarray(full.processed_Data['circ'][d][0]).copy();idx=[ids.index(v) for v in obj.global_point_ids];frame[idx]=np.asarray(obj.processed_Data['circ'][d][radius]);crop=obj.calibration_context['crop_origin_m']
   diag=full._assemble_multiregion_parameters(frame.T,d)[-1]
   samples.append({'region':name,'radius':radius,'frame':frame,'crop':crop,'diag':diag})
 columns=[];x0=[]
 for name in regions:
  block=cfg['regions'][name]
  used=[0] if name=='end15cm' else list(range(len(block['local_segmentation'])))
  for level in range(len(block['thresholds'])+1):
   for segment in used:
    columns.append((name,level,segment));x0.append(block['slopes'][d][level,segment])
 x0=np.asarray(x0);A=[];angles=[];weights=[]
 sigma=np.deg2rad(d*full.rot_dir[0]+full.rot_ang)
 for sample in samples:
  diag=sample['diag'];name=sample['region']
  points=range(15,len(ids)) if name in ('full','end15cm') else range(17,len(ids))
  for j in points:
   row=[]
   for r,level,seg in columns:
    b=cfg['regions'][r];labels=np.repeat(np.arange(len(b['local_segmentation'])),b['local_segmentation'])
    mass=np.asarray(diag[r]['slope_masses']);value=0.
    for k,pt in enumerate(b['support_point_ids']):
     i=ids.index(pt)
     if pt in b['owned_point_ids'] and i<=j and labels[k]==seg:
      value+=mass[level,k]*(dist[i]-dist[i-1])
    row.append(value)
   A.append(row);angles.append(diag['final_angle'][j]+sigma)
   weights.append(1. if name!='full' else 1.)
 A=np.asarray(A);angles=np.asarray(angles);weights=np.sqrt(weights)
 def residual(x):
  e=angles+A@(x-x0)
  return np.r_[weights*np.sin(e),weights*(1-np.cos(e)),1e-5*(x-x0)]
 best=None
 for shift in (0.,-50.,50.):
  fit=least_squares(residual,np.clip(x0+shift,-149.99,149.99),bounds=(-150.,150.),max_nfev=200)
  cost=np.mean(residual(fit.x)[:2*len(angles)]**2)
  if best is None or cost<best[0]:best=(cost,fit.x.copy())
 for (name,l,s),v in zip(columns,best[1]):cfg['regions'][name]['slopes'][d][l,s]=v

 # Amplitude trial: actual assembly score masses, known circular curvature.
 for name in regions:
  b=cfg['regions'][name];levels=len(b['thresholds'])+1;groups=b['weight_group_ids']
  num_groups=1 if groups is None else max(groups)+1
  C=[];target=[]
  for sample in samples:
   if sample['region'] not in ('full',name):continue
   diag=full._assemble_multiregion_parameters(sample['frame'].T,d)[-1]
   mass=np.asarray(diag[name]['weight_masses'])
   for k,pt in enumerate(b['support_point_ids']):
    if pt not in b['owned_point_ids']:continue
    i=ids.index(pt);row=np.zeros(levels*num_groups)
    g=0 if groups is None else int(groups[k])
    base=diag['final_magnitude'][i]/diag['final_weight'][i]
    row[g*levels:(g+1)*levels]=mass[:,k]*base/(1000./sample['radius'])
    C.append(row);target.append(1.)
  fit=lsq_linear(np.asarray(C),target,bounds=(.6,5.),tol=1e-10)
  b['weights'][d]=fit.x
  if name=='end5cm' and p['regions'][name].get('coverage_aware_weights',{}).get('enabled'):
   from tools.end5_weight_coverage import expand_groupwise_weights
   support=p['regions'][name]['coverage_aware_weights']['directions'][str(d)]['support_map']
   free={g:{int(l):float(fit.x[int(g)*levels+int(l)]) for l in v['free_levels']} for g,v in support['groups'].items()}
   b['weights'][d]=expand_groupwise_weights(free,support).reshape(-1)
  p['regions'][name]['slopes'][str(d)]=b['slopes'][d].tolist()
  p['regions'][name]['weights'][str(d)]=b['weights'][d].tolist()
 metrics={}
 for name in ('full',*regions):
  pe=[];ee=[]
  for sample in samples:
   if sample['region']!=name:continue
   s,curve,_,diag=_reconstruct_frame(full,sample['frame'],d)
   ideal,_=straight_prefix_circular_tail(s,sample['crop'],sample['radius']/1000.)
   e=np.linalg.norm(curve-ideal,axis=1)/(s[-1]-sample['crop'])
   pe.append(float(e[s>=sample['crop']-1e-12].mean()));ee.append(float(e[-1]))
  metrics[name]={'point':float(np.mean(pe)),'end':float(np.mean(ee))}
 report[str(d)]={'phase_fit_cost':best[0],'merged_metrics_nonzero_samples':metrics}
 print(d,report[str(d)],flush=True)
p['provenance']['merged_parameter_trial']={'source':str(SOURCE),'report':'docs/09B7-20261102-merged-geometry-trial.json','production_source_modified':False,'validation_complete':False}
p['shared_parameters']['optimization_hyperparameters']['slope_upper_bound']=150.
OUTPUT.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'docs/09B7-20261102-merged-geometry-trial.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(str(OUTPUT),flush=True)
