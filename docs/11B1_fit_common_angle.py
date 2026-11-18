import json,sys,os,subprocess,concurrent.futures
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
src=Path('params/11B1_NeTi_seven_assembled.json')
args=main.parse_main_args(['--task','recon','--sensor_params',str(src),'--multi_region_calib','True'])
ctx=main.configure_calibration_args(args);o=Optimiser(**optimizer_parameters(args));o.calibration_context=ctx
terms=[]
for d in (0,120,240):
 rs,s=o.reconstruct_shapes('circ',d);s=np.asarray(s)-s[0];L=s[-1]
 curves=np.stack(list(rs.values()));ideal=np.stack([o._construct_ideal_shape('circ',s,L,r/1000,None) for r in rs])
 x,y,z=curves.transpose(2,0,1);u,v,_=ideal.transpose(2,0,1)
 terms.append(np.stack(((x-u)**2+y*y+z*z+v*v,-2*v*y,2*v*z))/L**2)
A,B,C=np.stack(terms,axis=1)
def metrics(deg):
 t=np.deg2rad(deg);e=np.sqrt(np.maximum(0,A+B*np.cos(t)+C*np.sin(t)))
 return np.column_stack((e.mean(axis=(1,2)),e[:,:,-1].mean(axis=1)))
grid=np.arange(-180.,180.,.1)
def solve(fn):
 vals=np.array([fn(t) for t in grid]);i=vals.argmin();x=grid[i]
 return float(minimize_scalar(fn,bounds=(x-.1,x+.1),method='bounded',options={'xatol':1e-10}).x)
angle=solve(lambda t:metrics(t).max())
solo=[solve(lambda t:metrics(t)[i].max()) for i in range(3)]
report=dict(angle=angle,solo=solo,zero=metrics(0).tolist(),selected=metrics(angle).tolist(),objective='minimum worst of six full-length assembled calibration mean errors')
pkg=json.loads(src.read_text(encoding='utf8'));pkg['multi_region']['rot_ang']=angle;pkg['provenance']['common_angle_fit']=report
out=Path('params/11B1_NeTi_seven_common_angle.json');out.write_text(json.dumps(pkg,ensure_ascii=False,indent=2),encoding='utf8')
print(report,flush=True)
def run(d):
 with open(f'docs/11B1_common_fit_recon_{d}.log','w',encoding='utf8') as f:subprocess.run([sys.executable,'main.py','--task','recon','--sensor_params',str(out),'--multi_region_calib','True','--direct',str(d)],stdout=f,stderr=subprocess.STDOUT,check=True)
with concurrent.futures.ThreadPoolExecutor(3) as pool:list(pool.map(run,(0,120,240)))

