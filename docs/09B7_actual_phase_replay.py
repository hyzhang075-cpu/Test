import argparse, contextlib, io, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from optimiser import Optimiser
from calibration_batch import optimizer_parameters
from tools.calibration_validation import _reconstruct_frame, build_phase_transport_evidence
cli=argparse.ArgumentParser()
cli.add_argument('--sensor-params',required=True)
cli.add_argument('--output',required=True)
args=cli.parse_args()
path=str(Path(args.sensor_params).resolve())
p=json.loads(Path(path).read_text(encoding='utf-8'))
with contextlib.redirect_stdout(io.StringIO()):
    def make(region,merged):
        a=main.parse_main_args(['--task','recon','--sensor_params',path,'--multi_region_calib',str(merged),'--optimization_region',region,'--use_full_transported_phase','False','--direct','0','--exp_directs','[0,120,240]'])
        a.use_stored_zero=False
        main.configure_calibration_args(a)
        return Optimiser(**optimizer_parameters(a))
    full=make('full',True)
    local={r:make(r,False) for r in ['end15cm','end5cm']}
ids=list(full.global_point_ids)
dist=np.asarray(p['regions']['full']['global_sample_dist_m'])
starts={r:ids.index(p['regions'][r]['support_point_ids'][0]) for r in local}
rows=[]
for d in [0,120,240]:
    phases={r:p['provenance']['local_global_phases_set'][r][str(d)] for r in local}
    for region,source in local.items():
        samples=[]
        for radius in source.radii[d]['circ']:
            if radius<=0: continue
            frame=np.array(full.processed_Data['circ'][d][0]).copy()
            indices=[ids.index(i) for i in source.global_point_ids]
            frame[indices]=np.asarray(source.processed_Data['circ'][d][radius])
            _,_,_,diag=_reconstruct_frame(full,frame,d)
            e=build_phase_transport_evidence(full.global_phases_set,dist,np.asarray(diag['slope_map']),phases,starts,tolerance_deg=30.)[region]
            samples.append({'radius_mm':radius,**e})
        if not samples: raise ValueError('No nonzero samples for '+region)
        worst=max(samples,key=lambda x:x['phase_error_deg'])
        row={'direct':d,'region':region,'first_point':p['regions'][region]['support_point_ids'][0],'max_phase_error_deg':worst['phase_error_deg'],'worst_radius_mm':worst['radius_mm'],'pass_30deg':worst['phase_error_deg']<=30.,'samples':samples}
        rows.append(row)
        print(json.dumps({k:v for k,v in row.items() if k!='samples'}))
report={'package':path,'basis':'Actual assembled candidate slope_map. Local measured nonzero-radius samples inserted into full straight-state frame. Circular phase difference at region first support point against stored local reference.','rot_ang':full.rot_ang,'use_full_transported_phase':False,'rows':rows}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
