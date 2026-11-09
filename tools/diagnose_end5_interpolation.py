"""Replay direct=0 tail calibration and plot production interpolation inputs/outputs."""

import argparse
from copy import copy
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from calibration_batch import _native, optimizer_parameters
from tools.calibration_validation import _full_region_slope_map, integrate_phase_to_point
from optimiser import Optimiser


def build(package_path, region, merged=False, local_phase=False):
    """Build an offline reader; optional local phase recreates its optimization reference."""
    args = main.parse_main_args([
        '--task', 'recon', '--sensor_params', str(package_path),
        '--multi_region_calib', str(merged), '--optimization_region', region,
    ])
    args.use_stored_zero = False
    args.exp_directs = [0]
    if local_phase:
        args.global_phases_set = args._sensor_package['provenance'][
            'local_global_phases_set'][region]['0']
    context = main.configure_calibration_args(args)
    result = Optimiser(**optimizer_parameters(args))
    result.calibration_context = context
    return result


def replay(sensor, frame):
    """Return the production frame intermediates without theoretical-curvature substitution."""
    result = sensor._reconstruct_frame(
        keys=None, calib_shape='circ', calib_Data=frame,
        weight=sensor.weights[0], slope=sensor.slopes[0], direct=0,
        magnitude_ratio=1.0, init_T=[1., 0., 0.], verbose=False,
    )
    return result, result[-1]


def run(package_path, output):
    """Save all direct=0 traces and compare four small-radius samples in two plot sheets."""
    output.mkdir(parents=True, exist_ok=True)
    package = json.loads(package_path.read_text(encoding='utf-8'))
    local = build(package_path, 'end5cm', local_phase=True)
    full = build(package_path, 'full')
    merged = copy(full)
    merged.multi_region_parameters = merged._normalise_multiregion_parameters(package)
    indices = [list(full.global_point_ids).index(p) for p in local.global_point_ids]
    start15 = list(full.global_point_ids).index(package['regions']['end15cm']['support_point_ids'][0])
    phase_rows = []
    for radius in (0, 2000, 1500, 1000, 800, 600, 400, 300, 200):
        frame = np.asarray(full.processed_Data['circ'][0][radius])
        slopes = _full_region_slope_map(full, frame, 0)
        predicted = integrate_phase_to_point(full.global_phases_set, full.samp_dist, slopes, start15)
        local_phase = float(package['provenance']['local_global_phases_set']['end15cm']['0'])
        difference = np.degrees(np.arctan2(np.sin(predicted-local_phase), np.cos(predicted-local_phase)))
        phase_rows.append(dict(radius_mm=radius, predicted_phase_rad=predicted,
                               local_phase_rad=local_phase, signed_difference_deg=float(difference)))
    traces = {'metadata': {'sensor_id': package['sensor_id'], 'direct': 0,
                          'curvature_interp': local.curvature_interp,
                          'local_phase_rad': local.global_phases_set,
                          'global_phase_rad': full.global_phases_set,
                          'zero_init': local.zero_init, 'end_point': local.end_point,
                          'move_filter_for_vector': local.move_filter_for_vector},
              'end15_phase_from_full': phase_rows, 'samples': {}}
    plotted = (50, 30, 20, 15)
    figures = {name: plt.subplots(4, 2, figsize=(13, 14), constrained_layout=True)
               for name in ('local_optimization_reference', 'merged_full_replay')}
    for radius, source in local.processed_Data['circ'][0].items():
        if not isinstance(radius, (int, float)):
            continue
        local_frame = np.asarray(source)
        full_frame = np.asarray(full.processed_Data['circ'][0][0]).copy()
        full_frame[indices] = local_frame
        rows = {}
        for name, sensor, frame in (
                ('local_optimization_reference', local, local_frame),
                ('merged_full_replay', merged, full_frame)):
            result, data = replay(sensor, frame)
            x = np.asarray(sensor.samp_dist)
            knots = np.asarray(sensor.ad_samp_dist)
            grid = np.asarray(result[3])
            origin = 0 if sensor is local else full.ideal_len-.05
            magnitude = np.asarray(data['magnitude'])
            angle = np.asarray(data['angle'])
            padded = magnitude.copy()
            if sensor.zero_init: padded = np.insert(padded, 0, padded[0])
            if sensor.end_point: padded = np.append(padded, padded[-1])
            last_interp = float(data['cur_interp'][-1])
            rows[name] = {
                'real_dist_m': x.tolist(), 'knot_dist_m': knots.tolist(),
                'interp_dist_m': grid.tolist(),
                **{k: np.asarray(v).tolist() for k,v in data.items()},
                'padded_magnitude': padded.tolist(),
                'last_real_curvature_m_inv': float(magnitude[-1]),
                'tip_interpolated_curvature_m_inv': last_interp,
                'tip_vs_last_real_percent': float((last_interp/magnitude[-1]-1)*100) if magnitude[-1] else None,
                'theoretical_curvature_m_inv': 1000/radius if radius else 0,
                'finite': bool(all(np.all(np.isfinite(v)) for v in data.values())),
            }
            if radius in plotted:
                axes = figures[name][1][plotted.index(radius)]
                axes[0].plot((grid-origin)*1000, data['cur_interp'], label='cur_interp')
                axes[0].scatter((x-origin)*1000, magnitude, label='magnitude (real)', zorder=4)
                axes[0].scatter((knots-origin)*1000, padded, marker='x', label='padded knots')
                axes[0].axhline(1000/radius, color='gray', ls='--', label='theory')
                sample_angle = np.unwrap(angle)
                interp_angle = np.unwrap(data['ang_interp'])
                interp_angle += 2*np.pi*np.round((sample_angle[-1]-interp_angle[-1])/(2*np.pi))
                axes[1].plot((grid-origin)*1000, np.degrees(interp_angle), label='ang_interp')
                axes[1].scatter((x-origin)*1000, np.degrees(sample_angle), label='angle (real)', zorder=4)
                for ax in axes:
                    ax.set_xlim(0, 50)
                    ax.set_title(f'R={radius} mm; {name}')
                    ax.set_xlabel('Position in last 5 cm (mm)')
                    ax.grid(alpha=.25)
                    ax.legend(fontsize=8)
                axes[0].set_ylabel('Curvature (1/m)')
                axes[1].set_ylabel('Unwrapped angle (deg)')
        traces['samples'][str(radius)] = rows
    for name, (fig, _) in figures.items():
        fig.savefig(output / f'{name}.png', dpi=160)
        plt.close(fig)
    (output/'traces.json').write_text(json.dumps(_native(traces), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    summarize(traces, output)
    return traces


def summarize(traces, output):
    """Verify exact PCHIP knots/endpoints and overlay a dense grid for tail inspection."""
    if traces['metadata']['curvature_interp'] != 'vector_pchip' or traces['metadata']['move_filter_for_vector']:
        raise ValueError('Cached dense comparison requires unfiltered vector_pchip')
    lines = ['# End5 direct=0 interpolation diagnosis', '',
             'Coordinates: m in traces, mm in figures; curvature: 1/m; angles displayed in deg.', '',
             'Local uses the saved end5 optimization phase; merged grafts local mean strain onto full straight replay.', '',
             '| radius mm | theoretical 1/m | last real 1/m | interpolated tip 1/m | last/theory % | full grid points in last 5 cm | PCHIP knot error 1/m |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    for name in ('local_optimization_reference', 'merged_full_replay'):
        fig, axes = plt.subplots(4, 2, figsize=(13, 14), constrained_layout=True)
        for row, radius in enumerate((50, 30, 20, 15)):
            values = traces['samples'][str(radius)][name]
            knots = np.asarray(values['knot_dist_m'])
            x = np.asarray(values['real_dist_m'])
            grid = np.asarray(values['interp_dist_m'])
            magnitude = np.asarray(values['magnitude'])
            angles = np.asarray(values['angle'])
            padded_angle = angles.copy()
            if traces['metadata']['zero_init']: padded_angle = np.insert(padded_angle, 0, padded_angle[0])
            if traces['metadata']['end_point']: padded_angle = np.append(padded_angle, padded_angle[-1])
            padded = np.asarray(values['padded_magnitude'])
            components = padded[:, None] * np.column_stack((np.cos(padded_angle), np.sin(padded_angle)))
            interpolator = PchipInterpolator(knots, components, axis=0)
            dense = np.linspace(knots[0], knots[-1], 2001)
            dense_components = interpolator(dense)
            dense_magnitude = np.linalg.norm(dense_components, axis=1)
            origin = knots[-1]-.05
            gm, xm, km, dm = grid >= origin, x >= origin, knots >= origin, dense >= origin
            ax, bx = axes[row]
            ax.plot((dense[dm]-origin)*1000, dense_magnitude[dm], ls='--', label='same PCHIP, dense grid')
            ax.plot((grid[gm]-origin)*1000, np.asarray(values['cur_interp'])[gm], 'o-', ms=3, label='production cur_interp')
            ax.scatter((x[xm]-origin)*1000, magnitude[xm], label='magnitude (real)', zorder=4)
            ax.scatter((knots[km]-origin)*1000, padded[km], marker='x', label='padded knots')
            ax.axhline(1000/radius, color='gray', ls=':', label='theory')
            sample_angle = np.unwrap(angles[xm])
            interp_angle = np.unwrap(np.asarray(values['ang_interp'])[gm])
            dense_angle = np.unwrap(np.arctan2(dense_components[dm, 1], dense_components[dm, 0]))
            for a in (sample_angle, interp_angle, dense_angle):
                a -= 2*np.pi*np.round((a[-1]-angles[-1])/(2*np.pi))
            bx.plot((dense[dm]-origin)*1000, np.degrees(dense_angle), ls='--', label='same PCHIP, dense grid')
            bx.plot((grid[gm]-origin)*1000, np.degrees(interp_angle), 'o-', ms=3, label='production ang_interp')
            bx.scatter((x[xm]-origin)*1000, np.degrees(sample_angle), label='angle (real)', zorder=4)
            for a in (ax, bx):
                a.set(xlim=(0, 50), xlabel='Position in last 5 cm (mm)', title=f'R={radius} mm; {name}')
                a.grid(alpha=.25)
                a.legend(fontsize=8)
            ax.set_ylabel('Curvature (1/m)')
            bx.set_ylabel('Angle (deg)')
            if name == 'merged_full_replay':
                error = float(np.max(np.abs(np.linalg.norm(interpolator(knots),axis=1)-padded)))
                lines.append(f'| {radius} | {1000/radius:.3f} | {magnitude[-1]:.3f} | {values["tip_interpolated_curvature_m_inv"]:.3f} | {100*magnitude[-1]/(1000/radius):.2f} | {gm.sum()} | {error:.3g} |')
        fig.savefig(output/f'{name}.png', dpi=160)
        plt.close(fig)
    lines.extend(['', '## Full-to-end15 start phase, direct=0', '',
                  '| full calibration radius mm | predicted phase rad | local phase rad | signed difference deg |',
                  '|---:|---:|---:|---:|'])
    for row in traces['end15_phase_from_full']:
        lines.append(f'| {row["radius_mm"]} | {row["predicted_phase_rad"]:.6f} | {row["local_phase_rad"]:.6f} | {row["signed_difference_deg"]:.3f} |')
    (output/'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--sensor-params', default='params/06B6_NeTi_v2_ftube_multi_region_validated.json')
    cli.add_argument('--output', default='docs/end5-interpolation-direct0-20260916')
    cli.add_argument('--cached', action='store_true', help='Regenerate figures from existing traces.json')
    args = cli.parse_args()
    output = ROOT/args.output
    output.mkdir(parents=True, exist_ok=True)
    if args.cached:
        summarize(json.loads((output/'traces.json').read_text(encoding='utf-8')), output)
    else:
        with (output/'replay.log').open('w', encoding='utf-8') as log, redirect_stdout(log):
            run(ROOT/args.sensor_params, output)
    print(output)
