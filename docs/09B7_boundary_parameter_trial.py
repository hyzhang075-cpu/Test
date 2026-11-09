"""Offline parameter-only trial. Does not change production optimization code."""
import contextlib
import io
import json
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from calibration_batch import optimizer_parameters
from optimiser import Optimiser
from tools.calibration_validation import _reconstruct_frame, straight_prefix_circular_tail

SOURCE = ROOT / 'params/09B7_20261102_boundary_review_candidate.json'
OUTPUT = ROOT / 'params/09B7_20261102_slope_phase_trial.json'
REPORT = ROOT / 'docs/09B7-20261102-slope-phase-trial.json'
p = json.loads(SOURCE.read_text(encoding='utf-8'))
original = deepcopy(p)

def make(region, merged):
    args = main.parse_main_args(['--task', 'recon', '--sensor_params', str(SOURCE),
        '--multi_region_calib', str(merged), '--optimization_region', region,
        '--use_full_transported_phase', 'False', '--exp_directs', '[0,120,240]'])
    args.use_stored_zero = False
    context = main.configure_calibration_args(args)
    obj = Optimiser(**optimizer_parameters(args))
    obj.calibration_context = context
    return obj

with contextlib.redirect_stdout(io.StringIO()):
    full = make('full', True)
    locals_ = {name: make(name, False) for name in ('end15cm', 'end5cm')}

# Duplicating old columns leaves the original pointwise coefficients unchanged.
maps = {'full': ([2,5,2,4,2,2,2,3], list(range(8)), list(range(8))),
        'end15cm': ([2,2,3], list(range(3)), list(range(5,8))),
        'end5cm': ([2,3], list(range(2)), list(range(6,8)))}
cfg = full.multi_region_parameters
for region, (segments, columns, global_ids) in maps.items():
    block = cfg['regions'][region]
    block['local_segmentation'] = np.asarray(segments)
    block['global_segment_ids'] = global_ids
    for direct in (0,120,240):
        block['slopes'][direct] = np.asarray(block['slopes'][direct])[:,columns].copy()
    saved = p['regions'][region]
    saved['local_segmentation'] = segments
    saved['global_segment_ids'] = global_ids
    for direct in ('0','120','240'):
        saved['slopes'][direct] = np.asarray(saved['slopes'][direct])[:,columns].tolist()
p['shared_parameters']['runtime_control_parameters']['full_segmentation'] = maps['full'][0]
p['shared_parameters']['optimization_hyperparameters']['slope_upper_bound'] = 100.
dist = np.asarray(full.samp_dist)
ids = list(full.global_point_ids)
starts = {r: ids.index(locals_[r].global_point_ids[0]) for r in locals_}

def phase(diag, first):
    return full.global_phases_set + np.dot(np.asarray(diag['slope_map'])[1:first+1], np.diff(dist[:first+1]))

def wrapped(x):
    return np.arctan2(np.sin(x), np.cos(x))

report = {'source': str(SOURCE), 'phase_basis': 'assembled phase at first support point versus unchanged stored local reference; diagnostic, not independent physical phase ground truth',
          'use_full_transported_phase': False, 'bridge_bound_rad_per_m': 100., 'directions': {}}
for direct in (0,120,240):
    samples = []
    for region, local in locals_.items():
        for radius in local.radii[direct]['circ']:
            if radius <= 0:
                continue
            frame = np.asarray(full.processed_Data['circ'][direct][0]).copy()
            idx = [ids.index(i) for i in local.global_point_ids]
            frame[idx] = np.asarray(local.processed_Data['circ'][direct][radius])
            samples.append((region, radius, frame))
    refs = {r: original['provenance']['local_global_phases_set'][r][str(direct)] for r in locals_}
    blocks = [cfg['regions'][r] for r in locals_]
    sizes = [b['slopes'][direct].shape[0] for b in blocks]
    x0 = np.concatenate([b['slopes'][direct][:,0] for b in blocks])

    def assign(x):
        offset = 0
        for block, size in zip(blocks, sizes):
            block['slopes'][direct][:,0] = x[offset:offset+size]
            offset += size

    def errors(x):
        assign(x)
        return np.asarray([wrapped(phase(full._assemble_multiregion_parameters(frame.T, direct)[-1], starts[r])-refs[r])
                           for r, radius, frame in samples])

    before = errors(x0)
    best = None
    # Different circular branches are physically distinct bridge coefficients.
    for shift in (0., -80., 80.):
        seed = np.clip(x0 + shift, -99.999, 99.999)
        def residual(x):
            e = errors(x)
            return np.r_[np.sin(e), 1-np.cos(e), 0.00005*(x-x0)]
        fit = least_squares(residual, seed, bounds=(-100.,100.), max_nfev=100,
                            ftol=1e-7, xtol=1e-7, gtol=1e-7)
        e = errors(fit.x)
        rank = (float(np.max(np.abs(e))), float(np.mean(e**2)))
        if best is None or rank < best[0]:
            best = (rank, fit.x.copy())
        if rank[0] < np.deg2rad(20.):
            break
    after = errors(best[1])
    direction = {'samples': [], 'bridge_coefficients': {}}
    for r, block in zip(locals_, blocks):
        p['regions'][r]['slopes'][str(direct)] = block['slopes'][direct].tolist()
        direction['bridge_coefficients'][r] = block['slopes'][direct][:,0].tolist()
    for i,(region,radius,frame) in enumerate(samples):
        direction['samples'].append({'region':region, 'radius_mm':radius,
            'before_deg':float(np.rad2deg(abs(before[i]))), 'after_deg':float(np.rad2deg(abs(after[i])))})
    direction['max_after_deg'] = {r:max(s['after_deg'] for s in direction['samples'] if s['region']==r) for r in locals_}

    def geometry():
        result = {}
        for region, local in [('full',full), *locals_.items()]:
            points, ends = [], []
            for radius in local.radii[direct]['circ']:
                if region == 'full':
                    frame = np.asarray(full.processed_Data['circ'][direct][radius])
                    crop = 0.
                else:
                    frame = np.asarray(full.processed_Data['circ'][direct][0]).copy()
                    idx = [ids.index(i) for i in local.global_point_ids]
                    frame[idx] = np.asarray(local.processed_Data['circ'][direct][radius])
                    crop = float(local.calibration_context['crop_origin_m'])
                s, curve, _, _ = _reconstruct_frame(full, frame, direct)
                ideal,_ = straight_prefix_circular_tail(s, crop, radius/1000.)
                mask = s >= crop - 1e-12
                length = float(s[-1]-crop)
                err = np.linalg.norm(curve-ideal,axis=1)/length
                points.append(float(np.mean(err[mask])))
                ends.append(float(err[-1]))
            result[region] = {'point_ratio':float(np.mean(points)), 'end_ratio':float(np.mean(ends)),
                              'basis':'absolute assembled curve error within physical region, divided by region length'}
        return result
    assign(x0)
    direction['geometry_before'] = geometry()
    assign(best[1])
    direction['geometry_after'] = geometry()
    report['directions'][str(direct)] = direction
    print(json.dumps({'direct':direct,'max_phase_after':direction['max_after_deg'],
                      'geometry_after':direction['geometry_after']}),flush=True)

p['multi_region']['deployment_ready'] = False
p['multi_region']['available_deployment_directions'] = []
for state in p['multi_region']['direction_deployment'].values():
    state['deployment_ready'] = False
    for key in state.get('quality_gates', {}):
        state['quality_gates'][key] = False
    state['failures'] = ['Manual slope parameter trial; requires new replay validation']
for block in p['regions'].values():
    block['errors'] = {}
    block['optimization'] = {}
p['provenance']['boundary_parameter_trial'] = {'source':str(SOURCE),'report':str(REPORT),
    'unchanged_local_phase_references':True,'production_optimizer_modified':False,
    'description':'Retain original segmentation; adjust only the first local segment slope columns'}
OUTPUT.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote trial package and report',flush=True)
