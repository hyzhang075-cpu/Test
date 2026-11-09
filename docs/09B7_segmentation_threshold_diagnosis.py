import contextlib,io,json,copy,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import integrate_phase_to_point,circular_angle_error_deg
path='params/09B7_20261029_all_regions_candidate.json';p=json.loads(Path(path).read_text(encoding='utf-8'))
with contextlib.redirect_stdout(io.StringIO()):
 def make(region,merged):
  a=main.parse_main_args(['--task','recon','--sensor_params',path,'--multi_region_calib',str(merged),'--optimization_region',region,'--use_full_transported_phase','False','--direct','0','--exp_directs','[0,120,240]']);a.use_stored_zero=False
  main.configure_calibration_args(a);return Optimiser(**optimizer_parameters(a))
 full=make('full',True);local={r:make(r,False) for r in ['end15cm','end5cm']}
ids=list(full.global_point_ids);dist=np.asarray(p['regions']['full']['global_sample_dist_m']);original=copy.deepcopy(full.multi_region_parameters)
# Measure directions with one common channel reference, without candidate slope correction.
theta=full._calculate_dynamic_angles(mode='init',segments=None,seg_slopes=None)-full.global_phases_set
raw={};fit_rows=[]
for name,o in [('full',full),*local.items()]:
 raw[name]={}
 positions=np.asarray(o.samp_dist)
 for d in [0,120,240]:
  curves=[];slope_arrays=[]
  for r in [1000,800,600,400,300,200]:
   frame=np.asarray(o.processed_Data['circ'][d][r]).T
   mag,angle=o._calculate_curvature_and_angle(frame,theta[:,:o.total_points])
   angle=np.unwrap(angle);curves.append((r,np.asarray(angle)))
   slope_arrays.append(-np.diff(angle)/np.diff(positions))
  med=np.median(slope_arrays,axis=0)
  raw[name][str(d)]={'point_ids':list(map(int,o.global_point_ids)),'median_adjacent_slope_rad_per_m':med.tolist(),'common_radii':[r for r,_ in curves]}
  if name!='full':
   start=list(o.global_point_ids).index(18);x=positions[start:]
   for partition in [[5],[3,2],[2,3]]:
    residual=[]
    for r,y in curves:
     y=y[start:];offset=0;res=[]
     for count in partition:
      xs=x[offset:offset+count];ys=y[offset:offset+count];coef=np.polyfit(xs,ys,1);res.extend((ys-np.polyval(coef,xs)).tolist());offset+=count
     residual.extend(res)
    fit_rows.append({'dataset':name,'direct':d,'tail_partition':partition,'angle_fit_rmse_deg':float(np.degrees(np.sqrt(np.mean(np.square(residual)))))})
variants=[]
for variant in ['original','local_nearest','local_window1','all_nearest']:
 config=copy.deepcopy(original)
 for name,block in config['regions'].items():
  if variant=='all_nearest' or (variant=='local_nearest' and name!='full'):block['score_boundary_mode']='nearest'
  if variant=='local_window1' and name!='full':block['score_window']=1
 full.multi_region_parameters=config
 for d in [0,120,240]:
  for region,source in local.items():
   first=p['regions'][region]['support_point_ids'][0];i=ids.index(first);reference=p['provenance']['local_global_phases_set'][region][str(d)];values=[]
   for r in source.radii[d]['circ']:
    if r<=0:continue
    frame=np.asarray(full.processed_Data['circ'][d][0]).copy();indices=[ids.index(k) for k in source.global_point_ids];frame[indices]=np.asarray(source.processed_Data['circ'][d][r])
    out=full._assemble_multiregion_parameters(frame.T,d);s=out[3]
    phase=integrate_phase_to_point(full.global_phases_set,dist,s,i)
    values.append(circular_angle_error_deg(phase,reference))
   variants.append({'variant':variant,'direct':d,'region':region,'max_phase_error_deg':max(values)})
result={'source':path,'raw':raw,'tail_fits':fit_rows,'scoring_counterfactuals':variants,'note':'All are diagnostics with fixed existing calibration parameters. Extra segments lower training fit residual by construction; not proof of improved reconstruction.'}
Path('docs/09B7-20261029-segmentation-threshold-diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
