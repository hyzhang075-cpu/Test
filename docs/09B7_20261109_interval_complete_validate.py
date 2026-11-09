import os,sys,json,subprocess
from pathlib import Path
R=Path.cwd();sys.path.insert(0,str(R));tag='09B7_20261109_interval_complete';pkg='params/'+tag+'_candidate.json'
common=['--full_segmentation','[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]','--start_value','19','--end_value','6','--use_stored_zero','False']
before=set(R.glob('calibration_results/09B7*/results.json'))
subprocess.run([sys.executable,'docs/09B7_compat_dispatch.py','main.py','--task','score','--sensor_params',pkg,'--multi_region_calib','True','--direct','0','--exp_directs','[0,120,240]',*common],check=True,env=dict(os.environ,MPLBACKEND='Agg'))
files=set(R.glob('calibration_results/09B7*/results.json'))-before;assert len(files)==1
import main
original=main.parse_main_args
main.parse_main_args=lambda argv=None:original([*(argv or []),*common])
from tools.calibration_validation import main as validate
validate(['--sensor-params',pkg,'--score-results',str(next(iter(files))),'--json-output','docs/'+tag+'_validation.json','--markdown-output','docs/'+tag+'_validation.md','--package-output','params/'+tag+'_checked.json'])
