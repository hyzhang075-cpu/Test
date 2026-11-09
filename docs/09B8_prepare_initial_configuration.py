import json,sys,subprocess,os
from pathlib import Path
R=Path.cwd();sys.path.insert(0,str(R));import main
regions={
 'full':{'length_m':None,'folder_path':'全段测试','radii':{'circ':[0,2000,1500,1000,800,600,400,300,200]},'thresholds':[.8,1.2,2.,3.,4.],'end_weights':False,'end_start':-5,'segmentation':[3,4,2,4,2,3,2,2],'weights':None,'slopes':None},
 'end15cm':{'length_m':.15,'folder_path':'末端测试/15cm','radii':{'circ':[0,2000,1500,1000,800,600,400,300,200,100,75,50,30]},'thresholds':[.8,1.2,2.,3.,4.,10.,20.],'end_weights':False,'end_start':-5,'segmentation':[3,2,2],'weights':None,'slopes':None},
 'end5cm':{'length_m':.05,'folder_path':'末端测试/5cm','radii':{'circ':[0,2000,1500,1000,800,600,400,300,200,100,75,50,30,20,15]},'thresholds':[.8,1.2,2.,3.,4.,10.,20.,35.,45.,70.],'end_weights':True,'end_start':-1,'segmentation':[2,2],'weights':None,'slopes':None}}
argv=['--sensor_id','09B8','--calibration_data_root','./09B8数据','--start_value','-32','--end_value','9','--full_segmentation',repr([3,4,2,4,2,3,2,2]),'--calibration_regions',repr(regions),'--weights','None','--slopes','None','--global_phases_set','0','--rot_ang','0','--use_stored_zero','False','--use_full_transported_phase','False','--multi_region_calib','True','--exp_directs','[0,120,240]']
contexts={}
for r in regions:
 a=main.parse_main_args(['--task','init','--optimization_region',r,*argv]);contexts[r]=main.configure_calibration_args(a)
config={'sensor_id':'09B8','hardware_note':'CH1 center, CH2/3/4 peripheral; physical first grating excluded by negative start','argv':argv,'regions':regions,'geometry':{r:{k:c[k] for k in ('global_point_ids','sample_dist_m','segmentation')} for r,c in contexts.items()}}
Path('docs/09B8_20261106_initial_configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
