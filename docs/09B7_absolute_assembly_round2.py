"""Recalibrate regional parameters using the live assembly and absolute bend direction."""
import contextlib,io,json,sys,csv
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
from tools.end5_weight_coverage import expand_groupwise_weights
source=R/'params/09B7_absolute_assembly_reoptim_candidate.json';p=json.loads(source.read_text(encoding='utf-8'))
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(source),'--multi_region_calib',str(m),'--optimization_region',r,'--use_full_transported_phase',str(m),'--exp_directs','[0,120,240]']);a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 merged=make('full',True);locals={r:make(r,False) for r in ('end15cm','end5cm')}
cfg=merged.multi_region_parameters;ids=list(merged.global_point_ids);report={};phase_rows=[]
for d in (0,120,240):
 samples=[]
 for region,o in [('full',merged),*locals.items()]:
  for radius,f in o.processed_Data['circ'][d].items():
   if radius<=0:continue
   if region=='full':frame=np.asarray(f);crop=0.
   else:
    frame=np.asarray(merged.processed_Data['circ'][d][0]).copy();frame[[ids.index(i) for i in o.global_point_ids]]=np.asarray(f);crop=o.calibration_context['crop_origin_m']
   samples.append((region,radius,frame,crop))
 def metrics():
  vals={r:[[],[]] for r in ('full','end15cm','end5cm')}
  for r,radius,f,crop in samples:
   s,c,_,dg=_reconstruct_frame(merged,f,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000);e=np.linalg.norm(c-ideal,axis=1)/(s[-1]-crop);vals[r][0].append(float(e[s>=crop-1e-12].mean()));vals[r][1].append(float(e[-1]))
  return {r:{'point_ratio':float(np.mean(v[0])),'end_ratio':float(np.mean(v[1]))} for r,v in vals.items()}
 before=metrics();sigma=np.deg2rad(d*merged.rot_dir[0]+merged.rot_ang)
 for region in ('end15cm','end5cm'):
  block=cfg['regions'][region];base=block['slopes'][d].copy();shape=base.shape;n=base.size;cache=[]
  def assign(delta):block['slopes'][d]=base+np.asarray(delta).reshape(shape)
  for r,radius,f,crop in samples:
   if r not in (region,'full'):continue
   assign(np.zeros(n));dg=merged._assemble_multiregion_parameters(f.T,d)[-1];indices=np.array([ids.index(i) for i in block['support_point_ids']]);angle=np.asarray(dg['final_angle'])[indices];J=[]
   for delta in np.eye(n):
    assign(delta);a=np.asarray(merged._assemble_multiregion_parameters(f.T,d)[-1]['final_angle'])[indices];J.append(np.angle(np.exp(1j*(a-angle))))
   cache.append((angle+sigma,np.asarray(J).T,1. if r==region else .5))
  def loss(x):
   out=[]
   for a,J,w in cache:
    e=a+J@x;out.extend([w*np.sin(e)/np.sqrt(len(e)),w*(1-np.cos(e))/np.sqrt(len(e))])
   return np.r_[np.concatenate(out),.0005*x]
  fit=least_squares(loss,np.zeros(n),bounds=(-150,150),max_nfev=250,ftol=1e-9,gtol=1e-9,xtol=1e-9);assign(fit.x)
  # Known-radius amplitude stage; retain coverage-aware interpolation of unmeasured levels.
  levels=len(block['thresholds'])+1;original=block['weights'][d].copy();support=p['regions'][region].get('coverage_aware_weights',{}).get('directions',{}).get(str(d),{}).get('support_map') if region=='end5cm' else None
  entries=[(int(g),int(l)) for g,v in support['groups'].items() for l in v['free_levels']] if support else [(0,i) for i in range(len(original))]
  def expand(x):
   if support:
    free={g:{} for g in support['groups']}
    for (g,l),v in zip(entries,np.exp(x)):free[str(g)][l]=float(v)
    return expand_groupwise_weights(free,support).reshape(-1)
   return np.exp(x)
  amp=[]
  for r,radius,f,crop in samples:
   if r!=region:continue
   dg=merged._assemble_multiregion_parameters(f.T,d)[-1];mass=np.asarray(dg[region]['weight_masses']);inds=[ids.index(i) for i in block['support_point_ids']];amp.append((mass,np.asarray(dg['base_magnitude'])[inds],1000/radius))
  x0=np.log([original[g*levels+l] if support else original[l] for g,l in entries])
  def amplitude_loss(x):
   w=expand(x);out=[]
   for mass,base_mag,target in amp:
    vectors=w.reshape(-1,levels)[np.asarray(block['weight_group_ids'])].T if block['weight_group_ids'] is not None else np.broadcast_to(w[:levels,None],mass.shape)
    out.append((base_mag*np.sum(mass*vectors,axis=0)/target-1)/np.sqrt(len(base_mag)))
   return np.r_[np.concatenate(out),.0001*(x-x0)]
  wf=least_squares(amplitude_loss,np.clip(x0,np.log(.05),np.log(10)),bounds=(np.log(.05),np.log(10)),max_nfev=100);block['weights'][d]=expand(wf.x)
  print('STAGE',d,region,'direction loss',float(np.linalg.norm(fit.fun)),flush=True)
 after=metrics();report[str(d)]={'before':before,'after':after};print('METRICS',d,json.dumps(report[str(d)]),flush=True)
 for region in locals:
  p['regions'][region]['slopes'][str(d)]=cfg['regions'][region]['slopes'][d].tolist();p['regions'][region]['weights'][str(d)]=cfg['regions'][region]['weights'][d].tolist()
 for r,radius,f,crop in samples:
  dg=merged._assemble_multiregion_parameters(f.T,d)[-1]
  for j,pt in enumerate(ids):phase_rows.append([d,r,radius,int(pt),float(merged.samp_dist[j]),float(np.asarray(dg['final_theta_dynamic'])[0,j]),float(np.degrees(np.asarray(dg['final_theta_dynamic'])[0,j])),float(np.degrees(dg['final_angle'][j])),dg['slope_map'][j],dg['final_magnitude'][j]])
 p['provenance']['assembled_absolute_recalibration']={'source':str(source),'report':'docs/09B7_absolute_assembly_reoptim_round2_report.json','full_coefficients_frozen':True,'direction_target':'known planar calibration direction using recorded direct/rot_dir/rot_ang','phase_mode':'full mixed end15 anchor, end15 mixed bridge to end5','live_validation':'pending'}
 p['multi_region']['use_full_transported_phase']=True;p['multi_region']['deployment_ready']=False;p['shared_parameters']['runtime_control_parameters']['use_full_transported_phase']=True;p['shared_parameters']['runtime_control_parameters']['multi_region_calib']=True;p['shared_parameters']['dynamic_display_parameters']['use_stored_zero']=False
 Path('params/09B7_absolute_assembly_reoptim_round2.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');Path('docs/09B7_absolute_assembly_reoptim_round2_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
with Path('docs/09B7_absolute_assembly_round2_point_phases.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['direct','replay_region','radius_mm','global_point','distance_m','phase_rad','phase_deg_unwrapped','bend_direction_deg','mixed_slope_rad_per_m','curvature_m_inv']);w.writerows(phase_rows)
print('EXPORTED candidate and per-sample phases; acceptance requires report review',flush=True)
