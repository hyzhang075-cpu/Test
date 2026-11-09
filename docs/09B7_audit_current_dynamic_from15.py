import sys,json,contextlib,io
from pathlib import Path
import numpy as np
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
from calibration_phase_reference import _mixed_slopes
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_NeTi_new.json','--multi_region_calib','True','--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
rows=[]
for d in (0,120,240):
 for radius,f in o.processed_Data['circ'][d].items():
  if radius<=0:continue
  f=np.asarray(f);dg=o._assemble_multiregion_parameters(f.T,d)[-1];full=_mixed_slopes(o,f,d);sg,sl=o._generate_dynamic_segments(full);alpha=o._calculate_dynamic_angles(mode='recon',segments=sg,seg_slopes=sl);km,ka=o._calculate_curvature_and_angle(epsilon=f.T,alpha_dynamic=alpha);delta=np.rad2deg(np.angle(np.exp(1j*(np.asarray(dg['final_angle'])-ka))));jumps=np.rad2deg(abs(np.angle(np.exp(1j*np.diff(dg['final_angle'])))))
  rows.append({'direct':d,'radius':radius,'angle_minus_full_deg':delta.tolist(),'adjacent_angle_jump_deg':jumps.tolist(),'slope':dg['slope_map'],'full_slope':full.tolist()})
Path('docs/09B7_dynamic_splice_from15_audit.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
for d in (0,120,240):
 print('DIRECTION',d)
 rr=[r for r in rows if r['direct']==d]
 for pt in range(15,23):
  v=[r['angle_minus_full_deg'][pt-1] for r in rr];j=[r['adjacent_angle_jump_deg'][pt-2] for r in rr];print(pt,round(min(v),2),round(max(v),2),'jump',round(max(j),2))

