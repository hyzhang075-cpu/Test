import sys,contextlib,io,json,time,copy,ast
from pathlib import Path
root=Path.cwd();stage=root/'docs/proposed_end15_assembly_loss';sys.path.insert(0,str(root));sys.path.insert(0,str(stage))
import tools
tools.__path__.insert(0,str(stage/'tools'))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
for file in ['main.py','optimiser.py','end15_assembly_loss.py','tools/sensor_parameter_package.py']:
 ast.parse((stage/file).read_text(encoding='utf-8'))
argv=['--task','optim','--sensor_params','params/09B7_corrected_multi_region_candidate.json','--optimization_region','end15cm','--multi_region_calib','False','--use_full_transported_phase','False','--end15cm_point_calib','True','--end15cm_assembly_loss','True','--direct','120','--exp_directs','[120]','--rot_ang','-31.4','--calibration_data_root',str(root/'09B7')]
with contextlib.redirect_stdout(io.StringIO()):
 a=main.parse_main_args(argv);a.use_stored_zero=False
 c=main.configure_calibration_args(a);o=Optimiser(**optimizer_parameters(a));o.calibration_context=c
 before_w=copy.deepcopy(o.weights);before_s=copy.deepcopy(o.slopes)
 start=time.perf_counter();total=o._real_point_loss(direction_only=True);elapsed=time.perf_counter()-start
 components=dict(o.assembly_loss_components)
 assert abs(total-components['real_point_direction_loss']-components['coefficient']*components['assembly_geometry_loss']) < 1e-12
 assert all((o.weights[k]==before_w[k]).all() for k in o.weights)
 assert all((o.slopes[k]==before_s[k]).all() for k in o.slopes)
 o.end15cm_assembly_loss=False
 old=o._real_point_loss(direction_only=True)
 assert abs(old-components['real_point_direction_loss']) < 1e-12
 o.end15cm_assembly_loss=True
 steady=time.perf_counter();again=o._real_point_loss(direction_only=True);steady=time.perf_counter()-steady
 assert abs(again-total)<1e-12
 assert o._assembly_evaluator.replay.multi_region_parameters['region_order']==['full','end15cm']
 assert not o._assembly_evaluator.replay.multi_region_parameters['use_full_transported_phase']
 # A candidate change must affect the geometry term; caller state is restored.
 o.slopes[120]=o.slopes[120].copy();o.slopes[120][:,0] += 0.1
 o._real_point_loss(direction_only=True)
 perturbed=dict(o.assembly_loss_components)
 assert abs(perturbed['assembly_geometry_loss']-components['assembly_geometry_loss'])>1e-12
 o.slopes=before_s
 rejected=0
 for extra in [['--multi_region_calib','True'],['--end15cm_point_calib','False'],['--use_full_transported_phase','True'],['--end15cm_assembly_loss_weight','nan']]:
  b=main.parse_main_args(argv+extra)
  try: main.configure_calibration_args(b)
  except ValueError: rejected+=1
 assert rejected==4
report={'checks':'AST, sum identity, candidate sensitivity, disabled identity, deterministic repeat, no owner mutation, full-only upstream ownership, phase false, four invalid combinations rejected','components':components,'perturbed_components':perturbed,'initialization_and_first_eval_seconds':elapsed,'cached_eval_seconds':steady,'radii':o._assembly_evaluator.radii}
(stage/'draft-check-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
