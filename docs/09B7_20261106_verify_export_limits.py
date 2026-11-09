import json,csv,sys,contextlib,io
from pathlib import Path
import numpy as np
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from tools.calibration_validation import _reconstruct_frame,straight_prefix_circular_tail
p=json.loads(Path('params/09B7_dynamic_smooth_score_trial.json').read_text(encoding='utf-8'));reports={}
for d in (0,120,240):
 report=json.loads(Path(f'docs/09B7_standalone_20261106_direct{d}_report.json').read_text());assert len(report)==3 and all(v['passed'] for v in report.values());q=json.loads(Path(f'params/09B7_standalone_20261106_direct{d}_trial.json').read_text(encoding='utf-8'));reports[str(d)]=report
 for r in p['regions']:
  for key in ('slopes','weights'):p['regions'][r][key][str(d)]=q['regions'][r][key][str(d)]
rot={r:{d:reports[d][r]['rot_ang'] for d in reports} for r in ('end15cm','end5cm')};p['provenance']['local_replay_rot_ang']=rot;p['provenance']['standalone_limits_recalibration']={'source':'params/09B7_dynamic_smooth_score_trial.json','all_nine_replay_verified':False,'criterion':'mean point and end error / standalone region length, all available radii including straight','local_replay_rot_ang_requires_explicit_cli':True,'merged_acceptance_pending':True};p['multi_region']['deployment_ready']=False;p['multi_region']['available_deployment_directions']=[]
for v in p['multi_region'].get('direction_deployment',{}).values():v['deployment_ready']=False
out=Path('params/09B7_20261106_single_limits_candidate.json');out.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',str(out),'--multi_region_calib',str(m),'--optimization_region',r,'--use_full_transported_phase',str(m),'--exp_directs','[0,120,240]']);a.use_stored_zero=False;c=main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a));o.calibration_context=c;return o
with contextlib.redirect_stdout(io.StringIO()):
 merged=make('full',True);single={r:make(r,False) for r in ('full','end15cm','end5cm')}
ids=list(merged.global_point_ids);verified={};phase_rows=[]
for d in (0,120,240):
 row={'standalone':{},'assembled':{}}
 for r,o in single.items():
  o.rot_ang=reports[str(d)][r]['rot_ang'];rs,s=o.reconstruct_shapes(calib_shape='circ',direct=d,verbose=False);o._compute_error(interp_dist=s,rs={'circ':rs});point=float(o.avg_point_err['calib']);end=float(o.avg_end_err['calib']);cap=.01 if r=='full' else .1;assert max(point,end)<cap;row['standalone'][r]={'point_ratio':point,'end_ratio':end,'rot_ang':o.rot_ang};pe=[];ee=[]
  for radius,f in o.processed_Data['circ'][d].items():
   if r=='full':frame=np.asarray(f);crop=0.
   else:
    frame=np.asarray(merged.processed_Data['circ'][d][0]).copy();frame[[ids.index(i) for i in o.global_point_ids]]=np.asarray(f);crop=o.calibration_context['crop_origin_m']
   dist,c,_,dg=_reconstruct_frame(merged,frame,d);ideal,_=straight_prefix_circular_tail(dist,crop,radius/1000.);e=np.linalg.norm(c-ideal,axis=1)/(dist[-1]-crop);pe.append(float(e[dist>=crop-1e-12].mean()));ee.append(float(e[-1]))
   for j,pt in enumerate(ids):phase_rows.append([d,r,radius,int(pt),float(merged.samp_dist[j]),float(np.asarray(dg['final_theta_dynamic'])[0,j]),float(np.degrees(np.asarray(dg['final_theta_dynamic'])[0,j])),float(np.degrees(dg['final_angle'][j]))])
  row['assembled'][r]={'point_ratio':float(np.mean(pe)),'end_ratio':float(np.mean(ee))}
 verified[str(d)]=row;print(d,json.dumps(row),flush=True)
p['provenance']['standalone_limits_recalibration']['all_nine_replay_verified']=True;p['provenance']['standalone_limits_recalibration']['report']='docs/09B7_20261106_single_limits_verified.json';out.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');Path('docs/09B7_20261106_single_limits_verified.json').write_text(json.dumps(verified,indent=2),encoding='utf-8')
with open('docs/09B7_20261106_single_limits_assembled_phases.csv','w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['direct','data_region','radius_mm','global_point','distance_m','phase_rad','phase_deg','bend_direction_deg']);w.writerows(phase_rows)
lines=['# Single-region limits verified','','Errors are means including straight state. Standalone local rotations require explicit CLI. Merged replay is a separate criterion.','','| Direction | Region | Point % | End % | rot_ang |','|---|---|---:|---:|---:|']
for d,row in verified.items():
 for r,v in row['standalone'].items():lines.append(f"| {d} | {r} | {100*v['point_ratio']:.4f} | {100*v['end_ratio']:.4f} | {v['rot_ang']:.8f} |")
lines+=['','## Assembled replay','','| Direction | Region | Point % | End % |','|---|---|---:|---:|']
for d,row in verified.items():
 for r,v in row['assembled'].items():lines.append(f"| {d} | {r} | {100*v['point_ratio']:.4f} | {100*v['end_ratio']:.4f} |")
lines+=['','```powershell']
for d,row in verified.items():
 for r,v in row['standalone'].items():lines.append(f'python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/{out.name} --multi_region_calib False --optimization_region {r} --use_full_transported_phase False --direct {d} --exp_directs "[0,120,240]" --rot_ang {v["rot_ang"]:.15g}')
lines+=['```'];Path('docs/09B7_20261106_single_limits_verified.md').write_text('\n'.join(lines),encoding='utf-8');print('VERIFIED_ALL_NINE',out,flush=True)
