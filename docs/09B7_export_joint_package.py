"""Export explicitly selected parameter trials; no automatic claim of deployment."""
import argparse,json,math
from copy import deepcopy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
cli=argparse.ArgumentParser()
for d in (0,120,240):cli.add_argument(f'--direct{d}',required=True)
cli.add_argument('--output',required=True);args=cli.parse_args()
source=ROOT/'params/09B7_20261102_coupled_phase_candidate.json'
p=json.loads(source.read_text(encoding='utf-8'));fragments={}
for d in (0,120,240):
 path=Path(getattr(args,f'direct{d}'));path=path if path.is_absolute() else ROOT/path
 r=json.loads(path.read_text(encoding='utf-8'));assert r['direct']==d
 assert Path(r['source']).resolve()==source.resolve()
 for region,w in r['weights'].items():p['regions'][region]['weights'][str(d)]=w
 if 'full_slopes' in r:p['regions']['full']['slopes'][str(d)]=r['full_slopes']
 for region,slopes in r.get('local_slopes',{}).items():p['regions'][region]['slopes'][str(d)]=slopes
 fragments[str(d)]={'report':str(path.relative_to(ROOT)),'metrics_nonzero_replay':r['metrics_nonzero_replay'],'aligned_phase_max_deg':r['aligned_phase_after_deg'],'local_replay_rot_ang':r['local_replay_rot_ang']}
max_slope=max(float(np.max(abs(np.asarray(b['slopes'][str(d)])))) for b in p['regions'].values() for d in (0,120,240))
p['shared_parameters']['optimization_hyperparameters']['weight_bounds']=[.1,8.]
p['shared_parameters']['optimization_hyperparameters']['slope_upper_bound']=max(250.,50.*math.ceil(max_slope/50.))
p['provenance'].setdefault('historical_evidence',{})
for key in ('full_parameter_refine','full9_seed_trial','full_geometry_validation'):
 if key in p['provenance']:p['provenance']['historical_evidence'][key]=p['provenance'].pop(key)
p['provenance']['joint_parameter_refinement']={'source':str(source.relative_to(ROOT)),'fragments':fragments,'production_optimizer_modified':False,'phase_frame_alignment':'aligned local reference = raw local phase + radians(local replay rot_ang - full rot_ang); original raw phase references retained','raw_source_results_are_historical':True}
p['provenance']['local_replay_rot_ang']={r:{d:fragments[d]['local_replay_rot_ang'][r] for d in fragments} for r in ('end15cm','end5cm')}
p['provenance']['user_acceptance']={'verified':False,'full_point_ratio_max':.01,'full_end_ratio_max':.01,'local_point_ratio_max':.1,'local_end_ratio_max':.1,'aligned_phase_max_deg':30.,'basis':'calibration replay; standalone locals require their recorded replay rotations; merged replay uses full rotation'}
p['multi_region']['deployment_ready']=False;p['multi_region']['available_deployment_directions']=[]
for state in p['multi_region']['direction_deployment'].values():
 state['deployment_ready']=False;state['full_geometry']={};state['phase_transport']={}
 for k in state.get('quality_gates',{}):state['quality_gates'][k]=False
 state['failures']=['Joint parameter candidate; formal replay acceptance is recorded separately from legacy deployment gates']
for b in p['regions'].values():
 b['errors']={};b['optimization']={}
 for d in (0,120,240):
  s=np.asarray(b['slopes'][str(d)]);w=np.asarray(b['weights'][str(d)])
  assert s.shape==(len(b['thresholds'])+1,len(b['local_segmentation']))
  assert np.all(np.isfinite(s)) and np.all(np.isfinite(w)) and np.all(w>0)
out=Path(args.output);out=out if out.is_absolute() else ROOT/out
assert out.resolve()!=source.resolve()
out.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
print(str(out))
