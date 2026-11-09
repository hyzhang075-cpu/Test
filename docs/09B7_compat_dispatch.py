import sys,runpy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import calibration_batch
calibration_batch.CONTROL_KEYS.update({'end15cm_assembly_loss','end15cm_assembly_loss_weight'})
target=sys.argv[1];args=sys.argv[2:]
if target=='tools/sensor_parameter_package.py':
 import main
 from tools import sensor_parameter_package as m
 keys={a.dest for a in main.build_argument_parser()._actions}
 m.TRANSIENT_DESTINATIONS=tuple(k for k in m.TRANSIENT_DESTINATIONS if k in keys)
 m.main(args)
else:
 sys.argv=[target]+args;runpy.run_path(target,run_name='__main__')
