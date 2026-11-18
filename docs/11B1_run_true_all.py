import json,os,sys,subprocess,concurrent.futures
from pathlib import Path
root=Path('docs/11B1_true_all');root.mkdir(exist_ok=True)
src='params/11B1_NeTi_seven_common_angle.json'
env=dict(os.environ,MPLBACKEND='Agg',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
def optim(d):
 with (root/f'optim_{d}.log').open('w',encoding='utf8') as f:
  subprocess.run([sys.executable,'main.py','--task','optim','--sensor_params',src,'--multi_region_calib','True','--use_full_transported_phase','True','--optimization_regions',"['end15cm','end5cm']", '--direct',str(d),'--calibration_output_dir',str(root),'--max_iter','30'],stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
with concurrent.futures.ThreadPoolExecutor(3) as pool:list(pool.map(optim,(0,120,240)))
p=json.loads(Path(src).read_text(encoding='utf8'))
for path in root.glob('*/results.json'):
 q=json.loads(path.read_text(encoding='utf8'));d=str(q['direct'])
 for name,v in q['regions'].items():
  assert v['status']=='complete'
  a=v['parameters'];b=p['regions'][name]
  for key in ('weights','slopes'):b[key][d]=a[key][d]
  b['phase_reference'][d]=a['phase_reference'];b['errors'][d]=v['errors'];b['optimization'][d]=v['optimization']
  p['provenance']['local_global_phases_set'][name][d]=a['global_phases_set']
p['multi_region']['phase_reference_directions']=[0,120,240]
out=Path('params/11B1_NeTi_seven_transported.json');out.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
def recon(job):
 region,d=job
 with (root/f'recon_{region}_{d}.log').open('w',encoding='utf8') as f:
  subprocess.run([sys.executable,'main.py','--task','recon','--sensor_params',str(out),'--multi_region_calib',str(region=='assembled'),'--optimization_region','full' if region=='assembled' else region,'--use_full_transported_phase','True','--direct',str(d)],stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
with concurrent.futures.ThreadPoolExecutor(3) as pool:list(pool.map(recon,[(r,d) for r in ('assembled','full','end15cm','end5cm') for d in (0,120,240)]))
print('ALL 12 RECON PASSED',flush=True)
