import json,os,subprocess,sys,concurrent.futures
from pathlib import Path
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
p=read('params/11B1_NeTi_five_segment_candidate.json')
row=read('docs/11B1_NeTi_240_least_squares/status.json')['rows'][0]
seg=row['segmentation'];h=p['shared_parameters'];h['hardware_parameters'].update(start_value=114,end_value=8,samp_dist_preset=[510,521,532,543,554,565,576,587,607,627,647,667,687,707,807,907,1107,1307])
h['runtime_control_parameters'].update(full_segmentation=seg,calibration_data_root=next(Path('.').glob('1113-11B1*')).as_posix(),use_full_transported_phase=False,multi_region_calib=True)
h['dynamic_display_parameters']['use_stored_zero']=False
p['multi_region'].update(use_full_transported_phase=False,phase_reference_directions=[])
f=p['regions']['full'];f.update(local_segmentation=seg,global_segment_ids=list(range(7)))
prov=p['provenance'];prov['source_results']=['docs/11B1_NeTi_240_least_squares/status.json']
for d,b in row['refined'].items():
 for key in ('weights','slopes'):f[key][d]=b[key]
 f['errors'][d]=b['metrics'];f['optimization'][d]={'source':'seven segment geometry refinement'};prov['local_rot_ang']['full'][d]=b['rot_ang']
for path in Path('docs/11B1_seven_local_replay').glob('*/results.json'):
 q=read(path);d=str(q['direct']);prov['source_results'].append(str(path))
 for name,v in q['regions'].items():
  b=p['regions'][name];c=v['context'];a=v['parameters'];b.update(local_segmentation=c['segmentation'],global_segment_ids=c['global_segment_ids'])
  for key in ('weights','slopes'):b[key][d]=a[key][d]
  b['phase_reference'][d]=a.get('phase_reference');b['errors'][d]=v['errors'];b['optimization'][d]=v['optimization']
  prov['local_global_phases_set'][name][d]=a['global_phases_set'];prov['local_rot_ang'][name][d]=a['rot_ang']
out=Path('params/11B1_NeTi_seven_assembled.json');out.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
def run(d):
 with open(f'docs/11B1_seven_assembled_recon_{d}.log','w',encoding='utf8') as log:
  subprocess.run([sys.executable,'main.py','--task','recon','--sensor_params',str(out),'--multi_region_calib','True','--direct',d,'--rot_ang',str(row['refined'][d]['rot_ang'])],stdout=log,stderr=subprocess.STDOUT,check=True,env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1'))
with concurrent.futures.ThreadPoolExecutor(3) as pool:list(pool.map(run,['0','120','240']))
