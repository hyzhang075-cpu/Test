import contextlib,io,json,sys
from pathlib import Path
R=Path.cwd();sys.path.insert(0,str(R));import main,calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
from optimiser import Optimiser
report={}
for r in ('full','end15cm','end5cm'):
 with contextlib.redirect_stdout(io.StringIO()):
  a=main.parse_main_args(['--task','recon','--sensor_params','params/09B7_dynamic_smooth_score_trial.json','--multi_region_calib','False','--optimization_region',r,'--use_full_transported_phase','False','--exp_directs','[0,120,240]']);a.use_stored_zero=False;main.configure_calibration_args(a);o=Optimiser(**calibration_batch.optimizer_parameters(a))
 for d in (0,120,240):
  rs,s=o.reconstruct_shapes(calib_shape='circ',direct=d,verbose=False);o._compute_error(interp_dist=s,rs={'circ':rs});report[f'{r}/{d}']={'point':float(o.avg_point_err['calib']),'end':float(o.avg_end_err['calib'])};print(r,d,report[f'{r}/{d}'],flush=True)
Path('docs/09B7_20261106_standalone_baseline.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
