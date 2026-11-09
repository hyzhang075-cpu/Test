"""Re-estimate phase directly from calibration data without package inheritance."""
import contextlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
out={}
for r in ('full','end15cm','end5cm'):
 log=io.StringIO()
 with contextlib.redirect_stdout(log):
  a=main.parse_main_args(['--task','init','--sensor_params','params/09B7_20261102_multi_region_10pct.json','--multi_region_calib','False','--optimization_region',r,'--exp_directs','[0,120,240]'])
  a.use_stored_zero=False;main.configure_calibration_args(a);a.global_phases_set=None;o=Optimiser(**optimizer_parameters(a))
 out[r]={'measured_phase_rad':float(o.global_phases_set),'inherited_phase_disabled':True}
 (ROOT/f'docs/09B7-raw-phase-source-{r}.log').write_text(log.getvalue(),encoding='utf-8')
 print(r,out[r],flush=True)
(ROOT/'docs/09B7-raw-phase-source-audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
