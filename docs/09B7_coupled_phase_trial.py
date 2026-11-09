"""Fit assembly/reference consistency with original reconstruction untouched."""
import contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
SOURCE=ROOT/'params/09B7_20261102_local_restart_candidate.json'
p=json.loads(SOURCE.read_text(encoding='utf-8'))
rot=json.loads((ROOT/'docs/09B7-20261102-local-rotation-audit.json').read_text(encoding='utf-8'))
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(SOURCE),'--multi_region_calib',str(m),'--optimization_region',r,'--exp_directs','[0,120,240]']);a.use_stored_zero=False
 c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 full=make('full',True);single={r:make(r,False) for r in ('full','end15cm','end5cm')}
ids=list(full.global_point_ids);dist=np.asarray(full.samp_dist);cfg=full.multi_region_parameters;report={}
for d in (0,120,240):
 cols=[];x0=[]
 for r,b in cfg['regions'].items():
  segs=list(range(5,9)) if r=='full' else list(range(len(b['local_segmentation'])))
  for l in range(len(b['thresholds'])+1):
   for seg in segs:cols.append((r,l,seg));x0.append(b['slopes'][d][l,seg])
 x0=np.asarray(x0)
 def design(blocks,masses,support,positions,j):
  row=[]
  for r,l,seg in cols:
   value=0.
   if r in blocks:
    b=blocks[r];labels=np.repeat(np.arange(len(b['local_segmentation'])),b['local_segmentation'])
    for k,pt in enumerate(b['support_point_ids']):
     i=support.index(pt)
     if pt in b['owned_point_ids'] and 0<i<=j and labels[k]==seg:value+=masses[r][l,k]*(positions[i]-positions[i-1])
   row.append(value)
  return row
 B=[];err=[];weight=[];PB=[];perr=[];samples=[]
 standalone={}
 for r,o in single.items():
  standalone[r]={}
  b=cfg['regions'][r].copy();b['owned_point_ids']=list(b['support_point_ids'])
  for radius in o.radii[d]['circ']:
   if radius<=0:continue
   frame=np.asarray(o.processed_Data['circ'][d][radius])
   _,mag,_,_=o._get_base(keys=None,calib_Data=frame,base_slopes=o.slopes[d][0],verbose=False)
   mass=o._alloc_mass(o._get_scores(np.asarray(mag)))
   _,angle=o._Strain_2_Cur(keys=None,calib_shape='circ',calib_Data=frame,weight=o.weights[d],slope=o.slopes[d],direct=d)
   standalone[r][radius]=np.asarray(angle)
   sigma=np.deg2rad(d*o.rot_dir[0]+(o.rot_ang if r=='full' else rot[r][str(d)]['rot_ang']))
   for j in range(len(o.global_point_ids)):
    if r=='full' and j<13:continue
    B.append(design({r:b},{r:mass},list(o.global_point_ids),np.asarray(o.samp_dist),j))
    err.append(0. if r=='full' else angle[j]+sigma)
    weight.append(4.*min(1.,(1000/radius)/5.) if r=='full' else .7)
 for r,o in single.items():
  for radius in o.radii[d]['circ']:
   if radius<=0:continue
   if r=='full':frame=np.asarray(o.processed_Data['circ'][d][radius]);crop=0.
   else:
    frame=np.asarray(full.processed_Data['circ'][d][0]).copy();idx=[ids.index(v) for v in o.global_point_ids];frame[idx]=np.asarray(o.processed_Data['circ'][d][radius]);crop=o.calibration_context['crop_origin_m']
   diag=full._assemble_multiregion_parameters(frame.T,d)[-1]
   masses={k:np.asarray(diag[k]['slope_masses']) for k in cfg['regions']}
   sigma=np.deg2rad(d*full.rot_dir[0]+full.rot_ang)
   points=range(15,len(ids)) if r in ('full','end15cm') else range(17,len(ids))
   for j in points:
    B.append(design(cfg['regions'],masses,ids,dist,j))
    err.append(diag['final_angle'][j]-(standalone['full'][radius][j] if r=='full' else -sigma))
    weight.append(2.*min(1.,(1000/radius)/5.) if r=='full' else 1.)
   if r!='full':
    j=ids.index(o.global_point_ids[0]);pred=full.global_phases_set+np.dot(np.asarray(diag['slope_map'])[1:j+1],np.diff(dist[:j+1]))
    ref=p['provenance']['local_global_phases_set'][r][str(d)]+np.deg2rad(rot[r][str(d)]['rot_ang']-full.rot_ang)
    PB.append(design(cfg['regions'],masses,ids,dist,j));perr.append(pred-ref)
   samples.append((r,radius,frame,crop))
 B=np.asarray(B);err=np.asarray(err);weight=np.sqrt(weight);PB=np.asarray(PB);perr=np.asarray(perr)
 def residual(x):
  e=err+B@(x-x0);pe=np.angle(np.exp(1j*(perr+PB@(x-x0))))
  return np.r_[weight*np.sin(e),weight*(1-np.cos(e)),30*np.maximum(abs(pe)-np.deg2rad(25),0),.0001*(x-x0)]
 def jac(x):
  e=err+B@(x-x0);pe=np.angle(np.exp(1j*(perr+PB@(x-x0))))
  return np.vstack([weight[:,None]*np.cos(e)[:,None]*B,weight[:,None]*np.sin(e)[:,None]*B,30*((abs(pe)>np.deg2rad(25))*np.sign(pe))[:,None]*PB,.0001*np.eye(len(x0))])
 fit=least_squares(residual,np.clip(x0,-249.99,249.99),jac=jac,bounds=(-250.,250.),max_nfev=400,ftol=1e-8,xtol=1e-8,gtol=1e-8)
 for (r,l,s),v in zip(cols,fit.x):cfg['regions'][r]['slopes'][d][l,s]=v
 for r,b in cfg['regions'].items():
  p['regions'][r]['slopes'][str(d)]=b['slopes'][d].tolist();single[r].slopes[d]=b['slopes'][d].copy()
 metrics={};phase={r:[] for r in ('end15cm','end5cm')}
 for r in ('full','end15cm','end5cm'):
  pe=[];ee=[]
  for name,radius,frame,crop in samples:
   if name!=r:continue
   s,curve,_,diag=_reconstruct_frame(full,frame,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000.)
   e=np.linalg.norm(curve-ideal,axis=1)/(s[-1]-crop);pe.append(float(e[s>=crop-1e-12].mean()));ee.append(float(e[-1]))
   if r!='full':
    j=ids.index(single[r].global_point_ids[0]);pred=full.global_phases_set+np.dot(np.asarray(diag['slope_map'])[1:j+1],np.diff(dist[:j+1]))
    ref=p['provenance']['local_global_phases_set'][r][str(d)]+np.deg2rad(rot[r][str(d)]['rot_ang']-full.rot_ang)
    phase[r].append(float(np.rad2deg(abs(np.angle(np.exp(1j*(pred-ref)))))))
  metrics[r]={'point':float(np.mean(pe)),'end':float(np.mean(ee))}
 report[str(d)]={'merged':metrics,'aligned_phase_max_deg':{r:max(v) for r,v in phase.items()}}
 print(d,report[str(d)],flush=True)
 p['provenance']['coupled_phase_trial']={'source':str(SOURCE),'report':'docs/09B7-20261102-coupled-phase-trial.json','validation_complete':False,'phase_reference_basis':'independently fitted local replay rotations aligned to full rotation; raw references retained'}
 p['shared_parameters']['optimization_hyperparameters']['slope_upper_bound']=250.
 (ROOT/'params/09B7_20261102_coupled_phase_candidate.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'docs/09B7-20261102-coupled-phase-trial.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

