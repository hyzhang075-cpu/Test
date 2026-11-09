"""Parameter-only trial against unchanged raw phase and reconstruction code."""
import argparse,contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame,_full_region_slope_map,straight_prefix_circular_tail,integrate_phase_to_point
cli=argparse.ArgumentParser();cli.add_argument('--direct',type=int,required=True);cli.add_argument('--source',default='params/09B7_20261102_multi_region_10pct.json');cli.add_argument('--tag',default='original');args=cli.parse_args();d=args.direct
source=ROOT/args.source;p=json.loads(source.read_text(encoding='utf-8'))
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(source),'--multi_region_calib',str(m),'--optimization_region',r,'--exp_directs','[0,120,240]','--direct',str(d)])
 a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 merged=make('full',True);single={r:make(r,False) for r in ('full','end15cm','end5cm')}
for r in ('end15cm','end5cm'):single[r].rot_ang=p['provenance']['local_replay_rot_ang'][r][str(d)]
cfg=merged.multi_region_parameters;ids=list(merged.global_point_ids);dist=np.asarray(merged.samp_dist)
cols=[(r,l,s) for r,b in cfg['regions'].items() for l in range(len(b['thresholds'])+1) for s in range(len(b['local_segmentation']))]
x0=np.array([cfg['regions'][r]['slopes'][d][l,s] for r,l,s in cols]);samples=[];PB=[];pe=[];B=[];prior=[];wg=[]
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
for r,o in single.items():
 for radius in o.radii[d]['circ']:
  frame=np.asarray(o.processed_Data['circ'][d][radius]);b=cfg['regions'][r].copy();b['owned_point_ids']=list(b['support_point_ids'])
  _,mag,_,_=o._get_base(keys=None,calib_Data=frame,base_slopes=o.slopes[d][0],verbose=False);mass=o._alloc_mass(o._get_scores(np.asarray(mag)))
  if radius>0:
   for j in range(len(o.global_point_ids)):
    B.append(design({r:b},{r:mass},list(o.global_point_ids),np.asarray(o.samp_dist),j));wg.append(10. if r=='full' else 1.)
  if r=='full':f=frame;crop=0.
  else:
   f=np.asarray(merged.processed_Data['circ'][d][0]).copy();f[[ids.index(v) for v in o.global_point_ids]]=frame;crop=o.calibration_context['crop_origin_m']
  samples.append((r,radius,f,crop))
  if radius<=0:continue
  diag=merged._assemble_multiregion_parameters(f.T,d)[-1];masses={k:np.asarray(diag[k]['slope_masses']) for k in cfg['regions']}
  for j in range(13,len(ids)):
   B.append(design(cfg['regions'],masses,ids,dist,j));wg.append(5. if r=='full' else 1.)
  if r!='full' and radius in ({'end15cm':[100,75,50,30],'end5cm':[30,20,15]}[r]):
   j=ids.index(o.global_point_ids[0]);ref=p['provenance']['local_global_phases_set'][r][str(d)]
   for blocks,ms,theta in [(cfg['regions'],masses,float(np.asarray(diag['final_theta_dynamic'])[0,j])),({'full':dict(cfg['regions']['full'],owned_point_ids=ids)},{'full':None},0.)]:
    if ms['full'] is None:
     fo=single['full'];_,mg,_,_=fo._get_base(keys=None,calib_Data=f,base_slopes=fo.slopes[d][0],verbose=False);ms['full']=fo._alloc_mass(fo._get_scores(np.asarray(mg)))
     theta=integrate_phase_to_point(fo.global_phases_set,dist,_full_region_slope_map(fo,f,d),j)
    PB.append(design(blocks,ms,ids,dist,j));pe.append(theta-ref)
B=np.asarray(B);wg=np.sqrt(wg);PB=np.asarray(PB);pe=np.asarray(pe)
def assign(x):
 for (r,l,s),v in zip(cols,x):cfg['regions'][r]['slopes'][d][l,s]=v
 for r,o in single.items():o.slopes[d]=cfg['regions'][r]['slopes'][d].copy()
trials=[];best=None
for penalty in (5.,20.,100.,500.):
 def residual(x):
  delta=x-x0;e=B@delta;phase=np.angle(np.exp(1j*(pe+PB@delta)))
  return np.r_[wg*np.sin(e),wg*(1-np.cos(e)),penalty*np.maximum(abs(phase)-np.deg2rad(27),0),.0001*delta]
 def jac(x):
  e=B@(x-x0);phase=np.angle(np.exp(1j*(pe+PB@(x-x0))))
  return np.vstack([wg[:,None]*np.cos(e)[:,None]*B,wg[:,None]*np.sin(e)[:,None]*B,penalty*((abs(phase)>np.deg2rad(27))*np.sign(phase))[:,None]*PB,.0001*np.eye(len(x0))])
 fit=least_squares(residual,x0 if best is None else best,bounds=(-600,600),jac=jac,max_nfev=250,ftol=1e-7,xtol=1e-7,gtol=1e-7);best=fit.x;assign(best)
 phases=np.rad2deg(abs(np.angle(np.exp(1j*(pe+PB@(best-x0))))));metrics={}
 for r,o in single.items():
  rs,s=o.reconstruct_shapes(calib_shape='circ',direct=d,verbose=False);o._compute_error(interp_dist=s,rs={'circ':rs});metrics[r]={'point':float(o.avg_point_err['calib']),'end':float(o.avg_end_err['calib'])}
 assembled={r:[[],[]] for r in single}
 for r,radius,f,crop in samples:
  s,c,_,_= _reconstruct_frame(merged,f,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000.);e=np.linalg.norm(c-ideal,axis=1)/(s[-1]-crop);assembled[r][0].append(float(e[s>=crop-1e-12].mean()));assembled[r][1].append(float(e[-1]))
 record={'penalty':penalty,'max_raw_phase_deg':float(max(phases)),'standalone':metrics,'assembled':{r:{'point':float(np.mean(v[0])),'end':float(np.mean(v[1]))} for r,v in assembled.items()},'slopes':{r:cfg['regions'][r]['slopes'][d].tolist() for r in single}}
 trials.append(record);(ROOT/f'docs/09B7-{args.tag}-phase-trial-direct{d}.json').write_text(json.dumps({'source':str(source),'direct':d,'raw_references_unchanged':True,'trials':trials},indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in record.items() if k!='slopes'}),flush=True)
