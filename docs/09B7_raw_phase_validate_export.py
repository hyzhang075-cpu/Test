"""Replay the requested acceptance criteria and publish only a passing package.

This does not replace or claim to pass the repository's different legacy gates.
"""
import argparse,contextlib,hashlib,io,json,sys
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
cli=argparse.ArgumentParser();cli.add_argument('--sensor-params',default='params/09B7_20261102_raw_phase_candidate.json');cli.add_argument('--output',default='params/09B7_20261102_original_phase_pass.json');args=cli.parse_args()
source=Path(args.sensor_params).resolve();p=json.loads(source.read_text(encoding='utf-8'))
rot=p['provenance']['local_replay_rot_ang']
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(source),'--multi_region_calib',str(m),'--optimization_region',r,'--use_full_transported_phase','False','--exp_directs','[0,120,240]'])
 a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 merged=make('full',True);single={r:make(r,False) for r in ('full','end15cm','end5cm')}
ids=list(merged.global_point_ids)
owned=[pt for r in merged.multi_region_parameters['region_order'] for pt in merged.multi_region_parameters['regions'][r]['owned_point_ids']]
assert sorted(owned)==ids and len(set(owned))==len(ids)
report={'source':str(source),'basis':'means over available calibration radii, including straight state; each error normalized by its evaluated region length; not independent held-out or live data',
 'phase_basis':'actual assembled theta_dynamic and original offline validator, using independently initialized local phase references without rotation conversion; standard original local radius plan',
 'full_merged_1pct_is_required':False,'raw_local_phase_references_changed':True,'phase_reference_source':'docs/09B7-raw-phase-source-audit.json',
 'production_optimizer_modified':False,'directions':{},'standalone_full_rot_ang':float(merged.rot_ang),
 'local_replay_rot_ang':rot,'region_ownership':{r:merged.multi_region_parameters['regions'][r]['owned_point_ids'] for r in merged.multi_region_parameters['region_order']}}
all_pass=True
for d in (0,120,240):
 row={'standalone':{},'merged':{},'phase':{}}
 for r,o in single.items():
  o.rot_ang=float(p['multi_region']['rot_ang']) if r=='full' else float(rot[r][str(d)])
  rs={}
  for shape in o.calib_shapes:rs[shape],s=o.reconstruct_shapes(calib_shape=shape,direct=d,verbose=False)
  o._compute_error(interp_dist=s,rs=rs)
  m={'point_ratio':float(o.avg_point_err['calib']),'end_ratio':float(o.avg_end_err['calib']),
     'rot_ang':o.rot_ang,'radii_mm':list(o.radii[d]['circ']),
     'per_radius_point':o.point_errors_avg['circ'],'per_radius_end':o.end_errors['circ']}
  limit=.01 if r=='full' else .1;m['passed']=bool(m['point_ratio']<limit and m['end_ratio']<limit);all_pass &= m['passed'];row['standalone'][r]=m
  pe=[];ee=[];samples=[];raw_phase=[];aligned_phase=[]
  for radius in o.radii[d]['circ']:
   if r=='full':frame=np.asarray(merged.processed_Data['circ'][d][radius]);crop=0.
   else:
    frame=np.asarray(merged.processed_Data['circ'][d][0]).copy();idx=[ids.index(v) for v in o.global_point_ids];frame[idx]=np.asarray(o.processed_Data['circ'][d][radius]);crop=float(o.calibration_context['crop_origin_m'])
   s,curve,_,diag=_reconstruct_frame(merged,frame,d);ideal,_=straight_prefix_circular_tail(s,crop,radius/1000.)
   L=float(s[-1]-crop);errors=np.linalg.norm(curve-ideal,axis=1)/L
   point=float(errors[s>=crop-1e-12].mean());end=float(errors[-1]);pe.append(point);ee.append(end)
   samples.append({'radius_mm':radius,'point_ratio':point,'end_ratio':end})
   if r!='full' and radius in {'end15cm':[100,75,50,30],'end5cm':[30,20,15]}[r]:
    j=ids.index(o.global_point_ids[0]);actual=float(np.asarray(diag['final_theta_dynamic'])[0,j])
    raw=float(p['provenance']['local_global_phases_set'][r][str(d)]);aligned=raw
    raw_phase.append(float(np.rad2deg(abs(np.angle(np.exp(1j*(actual-raw)))))))
    aligned_phase.append(float(np.rad2deg(abs(np.angle(np.exp(1j*(actual-aligned)))))))
  row['merged'][r]={'point_ratio':float(np.mean(pe)),'end_ratio':float(np.mean(ee)),'samples':samples}
  if r!='full':
   row['merged'][r]['local_10pct_passed']=bool(max(np.mean(pe),np.mean(ee))<.1)
   row['phase'][r]={'raw_reference_max_deg':max(raw_phase),'actual_raw_reference_max_deg':max(aligned_phase),'passed':bool(max(aligned_phase)<=30.),'first_point':int(o.global_point_ids[0])};all_pass &= row['phase'][r]['passed']
 report['directions'][str(d)]=row
 print(json.dumps({'direct':d,'standalone':{r:{k:m[k] for k in ('point_ratio','end_ratio','passed')} for r,m in row['standalone'].items()},'merged':{r:{k:m[k] for k in ('point_ratio','end_ratio')} for r,m in row['merged'].items()},'phase':row['phase']}),flush=True)
legacy=json.loads((ROOT/'docs/09B7-20261102-raw-phase-validation.json').read_text(encoding='utf-8'))
report['original_phase_validation']={d:{r:v['phase_transport'][r] for r in ('end15cm','end5cm')} for d,v in legacy['directions'].items()}
all_pass &= all(v['within_30_deg'] for row in report['original_phase_validation'].values() for v in row.values())
report['all_requested_criteria_passed']=bool(all_pass)
def native(x):
 if isinstance(x,np.generic):return x.item()
 if isinstance(x,np.ndarray):return x.tolist()
 raise TypeError(type(x).__name__)
rp=ROOT/'docs/09B7-20261102-raw-final-acceptance.json';rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=native),encoding='utf-8')
if not all_pass:
 print('NOT PUBLISHED: at least one requested criterion failed. See '+str(rp),flush=True);sys.exit(2)
# Avoid carrying another sensor's stored zero into an untested dynamic session.
dynamic=p['shared_parameters'].get('dynamic_display_parameters',{})
old_zero={'use_stored_zero':dynamic.get('use_stored_zero'),'zero_reference_path':dynamic.get('zero_reference_path')}
dynamic['use_stored_zero']=False;dynamic['zero_reference_path']='./params/09B7_zero_reference.json'
p['provenance']['dynamic_zero_status']={'previous':old_zero,'stored_09B7_zero_available':False,'use_stored_zero':False,'note':'Offline calibration replay validated. Live demo uses first-frame zero; start straight. Capture a sensor-specific zero before enabling stored zero. No live demodulator validation was performed.'}
p['provenance']['user_acceptance'].update({'verified':True,'report':str(rp.relative_to(ROOT)),'full_merged_1pct_is_required':False,'local_merged_10pct_verified':all(v['local_10pct_passed'] for row in report['directions'].values() for k,v in row['merged'].items() if k!='full'),'phase_basis':report['phase_basis']})
payload={'shared':p['shared_parameters'],'globals':{k:p['multi_region'].get(k) for k in ('global_phases_set','rot_ang','use_full_transported_phase','region_order','directions')},'regions':p['regions'],'local_replay_rot_ang':rot}
digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
p['provenance']['user_acceptance']['parameter_sha256']=digest;report['published_parameter_sha256']=digest
output=Path(args.output);output=output if output.is_absolute() else ROOT/output
assert output.resolve()!=source
output.write_text(json.dumps(p,ensure_ascii=False,indent=2,default=native),encoding='utf-8');report['published_package']=str(output)
rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=native),encoding='utf-8')
lines=['# 09B7 calibration replay acceptance','','Means across available calibration radii; not worst-case per-radius or independent/live accuracy.','','## Standalone replay','','| Region | Direction | Point (%) | End (%) | rot_ang |','|---|---|---:|---:|---:|']
for d,row in report['directions'].items():
 for r,m in row['standalone'].items():lines.append(f"| {r} | {d} | {100*m['point_ratio']:.4f} | {100*m['end_ratio']:.4f} | {m['rot_ang']:.8f} |")
lines+=['','## Assembled replay','','Full assembled errors are listed separately and are not subject to the standalone full 1% gate. Local cases substitute local measurements into the full straight frame.','','| Region | Direction | Point (%) | End (%) |','|---|---|---:|---:|']
for d,row in report['directions'].items():
 for r,m in row['merged'].items():lines.append(f"| {r} | {d} | {100*m['point_ratio']:.4f} | {100*m['end_ratio']:.4f} |")
lines+=['','## Raw phase verification','','Actual assembled theta_dynamic is compared directly to independently measured local initial phases, without any rot_ang conversion. Original validator phase gates are reported separately; overall deployment gates may remain false.','','| Region | Direction | Raw actual max (deg) | Raw actual repeated (deg) |','|---|---|---:|---:|']
for d,row in report['directions'].items():
 for r,m in row['phase'].items():lines.append(f"| {r} | {d} | {m['raw_reference_max_deg']:.4f} | {m['actual_raw_reference_max_deg']:.4f} |")
lines+=['','## Reconstruct','','Standalone local commands must supply their recorded rot_ang; the current application does not automatically select per-region replay angles. Full assembled reconstruction uses rot_ang=-31.4.','', 'The old foreign-sensor stored-zero path was disabled. Live inference is not validated; first-frame zero requires a straight initial sensor state.','', '```powershell']
for d,row in report['directions'].items():
 for r,m in row['standalone'].items():lines.append(f"python main.py --task recon --sensor_params params/{output.name} --multi_region_calib False --optimization_region {r} --use_full_transported_phase False --direct {d} --exp_directs \"[0,120,240]\" --rot_ang {m['rot_ang']:.15g}")
 lines.append(f"python main.py --task recon --sensor_params params/{output.name} --multi_region_calib True --use_full_transported_phase False --direct {d} --exp_directs \"[0,120,240]\" --rot_ang -31.4")
lines+=['```','',f'Parameter SHA256: `{digest}`.']
(ROOT/'docs/09B7-20261102-raw-final-acceptance.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('PUBLISHED '+str(output),flush=True)
