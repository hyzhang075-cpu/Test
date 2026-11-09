"""Joint replay parameter trial, original production code unchanged."""
import argparse,contextlib,io,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
from tools.end5_weight_coverage import expand_groupwise_weights
cli=argparse.ArgumentParser();cli.add_argument('--direct',type=int,required=True,choices=[0,120,240]);cli.add_argument('--refine-first-slope',action='store_true');cli.add_argument('--refine-unused-tail',action='store_true');cli.add_argument('--phase-neutral-boundary',action='store_true');cli.add_argument('--nullspace');cli.add_argument('--phase-feasible',action='store_true');cli.add_argument('--initial-weights');args=cli.parse_args();d=args.direct
SOURCE=ROOT/'params/09B7_20261102_raw_phase_candidate.json'
p=json.loads(SOURCE.read_text(encoding='utf-8'));rot={r:{d:{'rot_ang':v} for d,v in vals.items()} for r,vals in p['provenance']['local_replay_rot_ang'].items()}
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(SOURCE),'--multi_region_calib',str(m),'--optimization_region',r,'--exp_directs','[0,120,240]','--direct',str(d)])
 a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 merged=make('full',True);single={r:make(r,False) for r in ('full','end15cm','end5cm')}
for r in ('end15cm','end5cm'):single[r].rot_ang=rot[r][str(d)]['rot_ang']
cfg=merged.multi_region_parameters;ids=list(merged.global_point_ids);dist=np.asarray(merged.samp_dist)
initial={}
if args.initial_weights:
 initial=json.loads(Path(args.initial_weights).read_text(encoding='utf-8'))
 for r,v in initial['weights'].items():cfg['regions'][r]['weights'][d]=np.asarray(v);single[r].weights[d]=np.asarray(v).copy()
base_full_slopes=cfg['regions']['full']['slopes'][d].copy()
base_local_slopes={r:cfg['regions'][r]['slopes'][d].copy() for r in ('end15cm','end5cm')}
support=p['regions']['end5cm']['coverage_aware_weights']['directions'][str(d)]['support_map']
entries=[];x0=[];low=[];high=[]
for r in ('full','end15cm','end5cm'):
 w=np.asarray(cfg['regions'][r]['weights'][d]);levels=len(cfg['regions'][r]['thresholds'])+1
 free=range(len(w)) if r!='end5cm' else [int(g)*levels+int(l) for g,v in sorted(support['groups'].items(),key=lambda x:int(x[0])) for l in v['free_levels']]
 for i in free:entries.append((r,int(i)));x0.append(np.log(w[i]));low.append(np.log(.6 if r=='full' else .1));high.append(np.log(5. if r=='full' else 8.))
weight_count=len(entries)
if args.refine_first_slope:x0.append(initial.get('full_first_segment_slope_offset_rad_per_m',0.));low.append(-1. if args.nullspace else -1.3);high.append(1. if args.nullspace else 1.3)
if args.refine_unused_tail:
 assert args.refine_first_slope
 x0.extend(initial.get('tail_offsets',[0.]*6)[:6]);low.extend([-15.]*5+[-20.]);high.extend([15.]*5+[20.])
if args.phase_neutral_boundary:
 assert args.refine_unused_tail
 assert cfg['regions']['full']['local_segmentation'].tolist()==[2,2,3,2,4,2,2,3,2]
 x0.append(initial.get('phase_neutral_boundary_offset',0.));low.append(-3.);high.append(3.)
 neutral15=-(dist[14]-dist[12])/(dist[15]-dist[14])
 neutral5=-((dist[14]-dist[12])+neutral15*(dist[16]-dist[14]))/(dist[17]-dist[16])
if args.nullspace:
 assert args.phase_neutral_boundary
 ns=json.loads(Path(args.nullspace).read_text(encoding='utf-8'))[str(d)];P=np.asarray(ns['P']);u,sv,vt=np.linalg.svd(P,full_matrices=True);N=vt[int(np.sum(sv>5e-4)):].T
 uniform=np.r_[np.ones(6),neutral15*np.ones(9),neutral5*np.ones(11)];uniform/=np.linalg.norm(uniform)
 projected=(np.eye(len(uniform))-np.outer(uniform,uniform)) if args.phase_feasible else (N-uniform[:,None]*(uniform@N)[None,:]);u,sv,_=np.linalg.svd(projected,full_matrices=False);N=u[:,:int(np.sum(sv>1e-8))]
 N=N/np.max(abs(N),axis=0)
 error_per_unit=float(np.max(np.sum(abs(P@N),axis=1)));ns_limit=20. if args.phase_feasible else min(10.,np.deg2rad(.8)/max(error_per_unit,1e-15))
 ns_start=len(x0);ns_size=N.shape[1];x0.extend(initial.get('nullspace_coordinates',[0.]*ns_size));low.extend([-ns_limit]*ns_size);high.extend([ns_limit]*ns_size)
x0=np.asarray(x0);original={r:np.asarray(cfg['regions'][r]['weights'][d]).copy() for r in single}
def assign(x):
 w={r:v.copy() for r,v in original.items()}
 for (r,i),v in zip(entries,np.exp(x)):w[r][i]=v
 levels=len(cfg['regions']['end5cm']['thresholds'])+1
 free={g:{int(l):float(w['end5cm'][int(g)*levels+int(l)]) for l in v['free_levels']} for g,v in support['groups'].items()}
 w['end5cm']=expand_groupwise_weights(free,support).reshape(-1)
 for r,v in w.items():cfg['regions'][r]['weights'][d]=v;single[r].weights[d]=v.copy()
 if args.refine_first_slope:
  s=base_full_slopes.copy();s[:,0]+=x[weight_count]
  if args.refine_unused_tail:
   tail=x[weight_count+1:weight_count+7];s[:,6:9]+=tail[:3]
   s15=base_local_slopes['end15cm'].copy();s15[:,1:3]+=tail[3:5]
   s5=base_local_slopes['end5cm'].copy();s5[:,1]+=tail[5]
   if args.phase_neutral_boundary:
    delta=x[weight_count+7];s[:,5]+=delta;s15[:,0]+=neutral15*delta;s5[:,0]+=neutral5*delta
   if args.nullspace:
    changes=N@x[ns_start:ns_start+ns_size]
    for (r,l,seg),change in zip(ns['columns'],changes):
     if r=='full':s[l,seg]+=change
     elif r=='end15cm':s15[l,seg]+=change
     else:s5[l,seg]+=change
   for r,ss in [('end15cm',s15),('end5cm',s5)]:cfg['regions'][r]['slopes'][d]=ss;single[r].slopes[d]=ss.copy()
  cfg['regions']['full']['slopes'][d]=s;single['full'].slopes[d]=s.copy()
 return w
samples=[];phase={r:[] for r in ('end15cm','end5cm')};signed_phase=[]
for r,o in single.items():
 for radius in o.radii[d]['circ']:
  if radius<=0:continue
  frame=np.asarray(o.processed_Data['circ'][d][radius])
  samples.append(('standalone/'+r,radius,frame,0.,o))
  if r=='full':frame2=np.asarray(merged.processed_Data['circ'][d][radius]);crop=0.
  else:
   frame2=np.asarray(merged.processed_Data['circ'][d][0]).copy();idx=[ids.index(v) for v in o.global_point_ids];frame2[idx]=frame;crop=o.calibration_context['crop_origin_m']
  samples.append(('merged/'+r,radius,frame2,crop,merged))
  if r!='full':
   diag=merged._assemble_multiregion_parameters(frame2.T,d)[-1];j=ids.index(o.global_point_ids[0]);pred=merged.global_phases_set+np.dot(np.asarray(diag['slope_map'])[1:j+1],np.diff(dist[:j+1]))
   ref=p['provenance']['local_global_phases_set'][r][str(d)]
   signed=float(np.angle(np.exp(1j*(pred-ref))));signed_phase.append(signed);phase[r].append(float(np.rad2deg(abs(signed))))
phase_max={r:max(v) for r,v in phase.items()};print(json.dumps({'direct':d,'fixed_aligned_phase_max_deg':phase_max}),flush=True)
counts={label:sum(s[0]==label for s in samples) for label in set(s[0] for s in samples)}
best=[float('inf'),None,None];calls=[0]
class TargetReached(Exception):pass
def residual(x):
 assign(x);parts=[];vals={label:[[],[]] for label in counts}
 for label,radius,frame,crop,o in samples:
  s,curve,_,_=_reconstruct_frame(o,frame,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000.)
  mask=np.flatnonzero(s>=crop-1e-12);L=float(s[-1]-crop);cap=.01 if label.endswith('/full') else .1
  error=(curve-ideal)/L;e=np.linalg.norm(error,axis=1)
  vals[label][0].append(float(e[mask].mean()));vals[label][1].append(float(e[-1]))
  take=mask[np.unique(np.linspace(0,len(mask)-1,20).astype(int))]
  parts.append(error[take].reshape(-1)/(cap*np.sqrt(counts[label]*len(take))))
  parts.append(2*error[-1]/(cap*np.sqrt(counts[label])))
 metrics={label:{'point':float(np.mean(v[0])),'end':float(np.mean(v[1]))} for label,v in vals.items()}
 ratios=[v/(.01 if label.endswith('/full') else .1) for label,m in metrics.items() for v in m.values()]
 phase_valid=True
 if args.phase_feasible:
  current_phase=np.angle(np.exp(1j*(np.asarray(signed_phase)+P@(N@x[ns_start:ns_start+ns_size])+(dist[1]-dist[0])*x[weight_count])))
  phase_valid=bool(np.max(abs(current_phase))<=np.deg2rad(30.))
  parts.append(50*np.maximum(abs(current_phase)-np.deg2rad(29.5),0)/np.deg2rad(30.))
 score=max(ratios)+.02*np.mean(ratios)+(0. if phase_valid else 1000.)
 if score<best[0]:best[:]=[score,np.asarray(x).copy(),metrics]
 parts.append(5*np.maximum(np.asarray(ratios)-.95,0))
 parts.append(.002*(x-x0));calls[0]+=1
 if calls[0]%25==0:print(json.dumps({'direct':d,'calls':calls[0],'max_target_ratio':max(ratios),'metrics':metrics}),flush=True)
 if max(ratios)<.98 and phase_valid:raise TargetReached()
 return np.concatenate(parts)
try:least_squares(residual,np.clip(x0,low,high),bounds=(low,high),max_nfev=30,ftol=1e-5,xtol=1e-5,gtol=1e-5,diff_step=1e-4)
except TargetReached:pass
w=assign(best[1]);out={'source':str(SOURCE),'direct':d,'metrics_nonzero_replay':best[2],'weights':{r:v.tolist() for r,v in w.items()},'base_aligned_phase_max_deg':phase_max,'local_replay_rot_ang':{r:rot[r][str(d)]['rot_ang'] for r in rot},'max_target_ratio':max(v/(.01 if label.endswith('/full') else .1) for label,m in best[2].items() for v in m.values())}
if args.refine_first_slope:
 out['full_first_segment_slope_offset_rad_per_m']=float(best[1][weight_count]);out['full_slopes']=cfg['regions']['full']['slopes'][d].tolist()
if args.refine_unused_tail:
 out['tail_offsets']=best[1][weight_count+1:weight_count+7].tolist();out['local_slopes']={r:cfg['regions'][r]['slopes'][d].tolist() for r in base_local_slopes}
if args.phase_neutral_boundary:out['phase_neutral_boundary_offset']=float(best[1][weight_count+7])
if args.nullspace:
 out['nullspace_coordinates']=best[1][ns_start:ns_start+ns_size].tolist();out['nullspace_coefficient_changes']=(N@best[1][ns_start:ns_start+ns_size]).tolist()
 if args.phase_feasible:out['phase_feasible_search']=True
 else:out['nullspace_phase_extra_bound_deg']=float(np.rad2deg(error_per_unit*ns_limit))
out['aligned_phase_after_deg']={r:[] for r in phase}
for label,radius,frame,crop,o in samples:
 if not label.startswith('merged/') or label=='merged/full':continue
 r=label.split('/')[1];diag=merged._assemble_multiregion_parameters(frame.T,d)[-1];j=ids.index(single[r].global_point_ids[0]);pred=merged.global_phases_set+np.dot(np.asarray(diag['slope_map'])[1:j+1],np.diff(dist[:j+1]))
 ref=p['provenance']['local_global_phases_set'][r][str(d)]
 out['aligned_phase_after_deg'][r].append(float(np.rad2deg(abs(np.angle(np.exp(1j*(pred-ref)))))))
out['aligned_phase_after_deg']={r:max(v) for r,v in out['aligned_phase_after_deg'].items()}
suffix='jointweights-slope' if args.refine_first_slope else 'jointweights'
if args.refine_unused_tail:suffix='jointweights-tail'
if args.phase_neutral_boundary:suffix='jointweights-neutral'
if args.nullspace:suffix='jointweights-null'
if args.phase_feasible:suffix='jointweights-feasible'
(ROOT/f'docs/09B7-raw-phase-{suffix}-direct{d}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out),flush=True)
