import contextlib,io,json,sys
from pathlib import Path
import numpy as np
R=Path.cwd();sys.path.insert(0,str(R));import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
p='params/09B7_20261102_original_phase_pass.json'
def make(r,m):
 a=main.parse_main_args(['--task','recon','--sensor_params',p,'--optimization_region',r,'--multi_region_calib',str(m),'--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);return Optimiser(**optimizer_parameters(a))
with contextlib.redirect_stdout(io.StringIO()):
 o=make('full',True);local={r:make(r,False) for r in ('end15cm','end5cm')}
ids=list(o.global_point_ids);rows=[]
for d in (0,120,240):
 for region,src in [('full',o),*local.items()]:
  for radius in src.radii[d]['circ']:
   if radius==0:continue
   f=np.asarray(src.processed_Data['circ'][d][radius])
   if region!='full':
    base=np.asarray(o.processed_Data['circ'][d][0]).copy();base[[ids.index(v) for v in src.global_point_ids]]=f;f=base
   dg=o._assemble_multiregion_parameters(f.T,d)[-1];k=np.asarray(dg['final_magnitude']);a=np.asarray(dg['final_angle']);da=abs(np.rad2deg(np.angle(np.exp(1j*np.diff(a)))));dk=abs(np.diff(k));vec=k[:,None]*np.column_stack([np.cos(a),np.sin(a)]);dv=np.linalg.norm(np.diff(vec,axis=0),axis=1)
   for j in range(len(ids)-1):
    rows.append(dict(direct=d,region=region,radius_mm=radius,left=ids[j],right=ids[j+1],distance_mm=[float(o.samp_dist[j]*1000),float(o.samp_dist[j+1]*1000)],angle_jump_deg=float(da[j]),curvature_jump=float(dk[j]),vector_jump=float(dv[j]),k_left=float(k[j]),k_right=float(k[j+1]),angle_reliable=bool(min(k[j:j+2])>=max(.5,.1*1000/radius))))
Path('docs/09B7-splice-point-jumps.json').write_text(json.dumps(rows,indent=2,default=lambda v:v.item()),encoding='utf-8')
for d in (0,120,240):
 rr=[x for x in rows if x['direct']==d and x['region']=='full'];print(d,'FULL angle',sorted([x for x in rr if x['angle_reliable']],key=lambda x:x['angle_jump_deg'],reverse=True)[:2]);print(d,'FULL curvature',sorted(rr,key=lambda x:x['curvature_jump'],reverse=True)[:2])
 for pair in [(15,16),(17,18),(20,21)]:
  rr=[x for x in rows if x['direct']==d and (x['left'],x['right'])==pair];v=max([x for x in rr if x['angle_reliable']],key=lambda x:x['angle_jump_deg'],default=None);w=max(rr,key=lambda x:x['curvature_jump']);print('BOUNDARY',d,pair,'angle',v,'curvature',w)

