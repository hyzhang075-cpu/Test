"""Standalone refinement using unchanged production reconstruction; explicit per-local replay rotation."""
import sys,json,io,contextlib
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares,minimize_scalar
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from tools.end5_weight_coverage import expand_groupwise_weights
D=int(sys.argv[1]);source=R/'params/09B7_dynamic_smooth_score_trial.json';p=json.loads(source.read_text(encoding='utf-8'));report={}
for region in ('full','end15cm','end5cm'):
 with contextlib.redirect_stdout(io.StringIO()):
  a=main.parse_main_args(['--task','recon','--sensor_params',str(source),'--multi_region_calib','False','--optimization_region',region,'--use_full_transported_phase','False','--exp_directs','[0,120,240]','--direct',str(D)]);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
 base_s=o.slopes[D].copy();base_w=o.weights[D].copy();segments=base_s.shape[1];levels=base_s.shape[0];rot0=float(o.rot_ang);support=p['regions'][region].get('coverage_aware_weights',{}).get('directions',{}).get(str(D),{}).get('support_map') if region=='end5cm' else None
 entries=[(int(g),int(l)) for g,v in support['groups'].items() for l in v['free_levels']] if support else [(0,i) for i in range(len(base_w))]
 def assign(x):
  o.slopes[D]=base_s+np.asarray(x[:segments])[None,:];factors=np.exp(x[segments:segments+len(entries)])
  if support:
   free={g:{} for g in support['groups']}
   for (g,l),factor in zip(entries,factors):free[str(g)][l]=float(base_w[g*levels+l]*factor)
   o.weights[D]=expand_groupwise_weights(free,support).reshape(-1)
  else:o.weights[D]=base_w*factors
  o.rot_ang=rot0+(float(x[-1]) if region!='full' else 0.)
 best=[float('inf'),None,None];calls=0;cap=.01 if region=='full' else .1
 class Done(Exception):pass
 def evaluate(x,stop=True):
  global calls
  assign(x);rs,s=o.reconstruct_shapes(calib_shape='circ',direct=D,verbose=False);o._compute_error(interp_dist=s,rs={'circ':rs});m={'point':float(o.avg_point_err['calib']),'end':float(o.avg_end_err['calib'])};score=max(m.values());calls+=1
  if score<best[0]:best[:]=[score,np.asarray(x).copy(),m]
  if calls%25==0:print(D,region,calls,m,flush=True)
  if stop and score<cap*.97:raise Done()
  ideals=o._construct_ideals(calib_shape='circ',interp_dist=s-s[0],val_len=float(s[-1]-s[0]));parts=[]
  for rad,c in rs.items():
   err=(np.asarray(c)-ideals[rad])/(s[-1]-s[0]);idx=np.linspace(0,len(s)-1,30).astype(int);parts.extend([err[idx].reshape(-1)/(cap*np.sqrt(len(rs)*len(idx))),2*err[-1]/(cap*np.sqrt(len(rs)))])
  return np.r_[np.concatenate(parts),20*np.maximum(np.array(list(m.values()))/cap-.96,0),.0001*x]
 n=segments+len(entries)+(region!='full');x=np.zeros(n);evaluate(x,False);before=best[2].copy()
 if region!='full' and best[0]>=cap*.97:
  for angle in range(-180,180,30):
   t=x.copy();t[-1]=angle;evaluate(t,False)
  x=best[1].copy();center=x[-1]
  def rotation_loss(v):
   t=x.copy();t[-1]=v;evaluate(t,False);return max(float(o.avg_point_err['calib']),float(o.avg_end_err['calib']))
  minimize_scalar(rotation_loss,bounds=(max(-180,center-30),min(180,center+30)),method='bounded',options={'xatol':.1});x=best[1].copy()
 if best[0]>=cap*.97:
  low=np.r_[np.full(segments,-80.),np.full(len(entries),np.log(.3)),[-180.] if region!='full' else []];high=np.r_[np.full(segments,80.),np.full(len(entries),np.log(3.)),[180.] if region!='full' else []]
  try:least_squares(evaluate,x,bounds=(low,high),max_nfev=50,ftol=1e-6,xtol=1e-6,gtol=1e-6,diff_step=1e-4)
  except Done:pass
 assign(best[1]);b=p['regions'][region];b['slopes'][str(D)]=o.slopes[D].tolist();b['weights'][str(D)]=o.weights[D].tolist();report[region]={'before':before,'after':best[2],'passed':best[0]<cap,'rot_ang':o.rot_ang,'evaluations':calls}
 Path(f'docs/09B7_standalone_20261106_direct{D}_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');Path(f'params/09B7_standalone_20261106_direct{D}_trial.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');print('REGION_DONE',D,region,report[region],flush=True)
print('DIRECTION_DONE',D,flush=True)
