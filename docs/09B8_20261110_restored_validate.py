import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main
original=main.parse_main_args
def parse(argv=None):
 a=original([*(argv or []),'--calibration_data_root','./09B8数据','--full_segmentation','[3,4,2,4,2,3,2,2]','--start_value','-32','--end_value','9','--use_stored_zero','False'])
 a.segmentation=None;a.active_channels=[1,2,3,4];a.sensing_ranges={1:(583,1048),3:(678,1146),4:(749,1215)}
 return a
main.parse_main_args=parse
from tools.calibration_validation import main as validate
validate(sys.argv[1:])
