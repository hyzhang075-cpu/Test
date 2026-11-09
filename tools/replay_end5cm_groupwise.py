"""Stream recorded dynamic frames through end5cm groupwise score variants."""

import argparse
from copy import deepcopy
import csv
import json
import pickle
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.sensor_parameter_package import load_sensor_package
from reconstructor import Reconstructor


VARIANTS = (
    'original_weights_slopes',
    'weights_one',
    'slopes_zero',
    'virtual_tip_zero',
)


def curvature_tail_metrics(x, magnitude, angle, *, tail_length_m=0.05):
    """Return scalar and planar-vector curvature integrals over the final tail."""
    x = np.asarray(x, dtype=float)
    magnitude = np.asarray(magnitude, dtype=float)
    angle = np.asarray(angle, dtype=float)
    if x.ndim != 1 or magnitude.shape != x.shape or angle.shape != x.shape:
        raise ValueError('x, magnitude, angle must be one-dimensional and equal length')
    if x.size < 2 or not np.all(np.isfinite(np.r_[x, magnitude, angle])) or np.any(np.diff(x) <= 0):
        raise ValueError('x, magnitude, angle must be finite with strictly increasing x')
    hi = float(x[-1])
    lo = max(float(x[0]), hi - float(tail_length_m))
    inside = (x > lo) & (x < hi)
    xx = np.r_[lo, x[inside], hi]
    mm = np.interp(xx, x, magnitude)
    aa = np.interp(xx, x, np.unwrap(angle))
    scalar_rad = float(np.trapezoid(mm, xx))
    vector_x = float(np.trapezoid(mm * np.cos(aa), xx))
    vector_y = float(np.trapezoid(mm * np.sin(aa), xx))
    return {
        'scalar_integral_deg': scalar_rad * 180.0 / np.pi,
        'vector_integral_deg': float(np.hypot(vector_x, vector_y) * 180.0 / np.pi),
        'max_curvature_m_inv': float(np.max(mm)),
    }


def summarize_variant_timeline(rows, *, over_threshold_deg=180.0):
    """Summarize a list of frame metrics, defining residual after the scalar peak."""
    if not rows:
        raise ValueError('cannot summarize an empty timeline')
    peak_frame = int(np.argmax([row['scalar_integral_deg'] for row in rows]))
    post_peak = rows[peak_frame + 1:] or rows[-1:]
    return {
        'frames': len(rows),
        'duration_s': float(rows[-1]['elapsed_s']),
        'peak_frame': peak_frame,
        'peak_elapsed_s': float(rows[peak_frame]['elapsed_s']),
        'max_scalar_integral_deg': float(max(row['scalar_integral_deg'] for row in rows)),
        'max_vector_integral_deg': float(max(row['vector_integral_deg'] for row in rows)),
        'max_curvature_m_inv': float(max(row['max_curvature_m_inv'] for row in rows)),
        'over_180_fraction': float(np.mean([
            row['scalar_integral_deg'] > over_threshold_deg for row in rows
        ])),
        'post_peak_residual': {
            'definition': 'mean of frames after the maximum scalar tail integral',
            'scalar_integral_deg': float(np.mean([row['scalar_integral_deg'] for row in post_peak])),
            'vector_integral_deg': float(np.mean([row['vector_integral_deg'] for row in post_peak])),
        },
    }


def _make_reconstructor(package, variant):
    config = deepcopy(package)
    end5 = config['regions']['end5cm']
    end5['weight_score_mode'] = 'group_mean'
    if variant == 'weights_one':
        for direct, values in end5['weights'].items():
            end5['weights'][direct] = [1.0] * len(values)
    elif variant == 'slopes_zero':
        for direct, values in end5['slopes'].items():
            end5['slopes'][direct] = [[0.0] * len(row) for row in values]

    hardware = package['shared_parameters']['hardware_parameters']
    reconstruction = package['shared_parameters']['reconstruction_parameters']
    rec = Reconstructor.__new__(Reconstructor)
    rec.samp_dist = np.asarray(package['regions']['full']['global_sample_dist_m'], dtype=float)
    rec.ad_samp_dist = np.r_[0.0, rec.samp_dist,
                              rec.samp_dist[-1] + float(hardware['end_value']) * 0.001]
    rec.total_points = rec.samp_dist.size
    rec.global_point_ids = np.arange(1, rec.total_points + 1)
    rec.num_channels_recon = 3
    rec.R = float(hardware['R'])
    rec.active_angles = None
    rec.interlaced_grating = False
    rec.global_phases_set = package['multi_region']['global_phases_set']
    rec.sharpness = float(reconstruction['sharpness'])
    rec.min_consecutive = int(reconstruction['min_consecutive'])
    rec.soft = True
    rec.discont = np.pi
    rec.move_filter = int(reconstruction['move_filter'])
    rec.move_filter_for_vector = bool(reconstruction.get('move_filter_for_vector', False))
    rec.interp_num = int(reconstruction['interp_num'])
    rec.multi_region_parameters = rec._normalise_multiregion_parameters(config)
    return rec


def _frame_metrics(rec, strain, direct, variant, x):
    magnitude, angle, weights, slope_map, diagnostics = (
        rec._assemble_multiregion_parameters(strain, direct)
    )
    node_magnitude = np.r_[magnitude[0], magnitude, magnitude[-1]]
    node_angle = np.r_[angle[0], angle, angle[-1]]
    if variant == 'virtual_tip_zero':
        node_magnitude[-1] = 0.0
    interp_magnitude, interp_angle, interp_x = rec._interpolate_curvature_vector(
        node_magnitude, np.unwrap(node_angle), method='pchip',
    )
    metrics = curvature_tail_metrics(interp_x, interp_magnitude, interp_angle)
    metrics.update({
        'weights_tail_mean': float(np.mean(weights[-4:])),
        'slope_tail_mean': float(np.mean(slope_map[-4:])),
        'group_base_magnitude': diagnostics['end5cm'].get('group_base_magnitude'),
    })
    return metrics


def replay_recording(recording, package, *, direct=0):
    """Read one pickle stream once and calculate all variants frame by frame."""
    reconstructors = {variant: _make_reconstructor(package, variant) for variant in VARIANTS}
    x = reconstructors[VARIANTS[0]].ad_samp_dist
    timelines = {variant: [] for variant in VARIANTS}
    first_timestamp = None
    previous_strain = None
    bad_frames = 0
    with Path(recording).open('rb') as stream:
        while True:
            try:
                frame = pickle.load(stream)
            except EOFError:
                break
            timestamp = float(frame['timestamp'])
            first_timestamp = timestamp if first_timestamp is None else first_timestamp
            raw = np.asarray(frame['raw_data'], dtype=float)
            processed = raw[:, 1:] - raw[:, :1]
            bad = ~np.isfinite(processed).all(axis=1)
            if np.any(bad):
                bad_frames += 1
                if previous_strain is not None:
                    processed[bad] = previous_strain[bad]
                else:
                    processed[bad] = 0.0
            previous_strain = processed.copy()
            strain = processed.T
            elapsed = timestamp - first_timestamp
            for variant, rec in reconstructors.items():
                row = _frame_metrics(rec, strain, direct, variant, x)
                row['elapsed_s'] = float(elapsed)
                timelines[variant].append(row)
    return {
        'recording': str(recording),
        'records': sum(len(rows) for rows in timelines.values()) // len(VARIANTS),
        'nonfinite_raw_frames': bad_frames,
        'variants': {
            variant: {
                'summary': summarize_variant_timeline(timelines[variant]),
                'timeline': timelines[variant],
            }
            for variant in VARIANTS
        },
    }


def _write_outputs(results, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    reference = {
        'score_mode': 'spatial_window',
        'description': 'Existing behavior: one spatial-window score/mass field drives both slope and weight selection; legacy packages without weight_score_mode stay on this path.',
    }
    report = {
        'reference_legacy_logic': reference,
        'groupwise_logic': {
            'score_mode': 'group_mean',
            'groups': [0, 0, 1, 2],
            'description': 'Point 19/20 share the arithmetic mean of their pre-weight base magnitude; points 21 and 22 score independently; slope scoring remains spatial_window.',
        },
        'no_ground_truth_note': 'Integrated curvature is accumulated turning from the reconstructed curvature field, not a ground-truth mechanical angle error.',
        'recordings': results,
    }
    (output_dir / 'replay.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8',
    )

    with (output_dir / 'replay.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        fieldnames = ['recording', 'variant', 'elapsed_s', 'scalar_integral_deg',
                      'vector_integral_deg', 'max_curvature_m_inv']
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for recording in results:
            for variant, data in recording['variants'].items():
                for row in data['timeline']:
                    writer.writerow({key: row.get(key) for key in fieldnames})

    lines = [
        '# end5cm groupwise-weight offline replay', '',
        '## Reference: existing scoring logic', '',
        reference['description'], '',
        '## Groupwise replay definition', '',
        report['groupwise_logic']['description'], '',
        report['no_ground_truth_note'], '',
        '## Summary', '',
        '| recording | variant | max scalar tail integral (deg) | max vector tail integral (deg) | max curvature (1/m) | >180° frames | post-peak scalar residual (deg) | post-peak vector residual (deg) |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for recording in results:
        for variant, data in recording['variants'].items():
            summary = data['summary']
            residual = summary['post_peak_residual']
            lines.append(
                f"| {Path(recording['recording']).name} | {variant} | "
                f"{summary['max_scalar_integral_deg']:.3f} | {summary['max_vector_integral_deg']:.3f} | "
                f"{summary['max_curvature_m_inv']:.3f} | {summary['over_180_fraction']:.3%} | "
                f"{residual['scalar_integral_deg']:.3f} | {residual['vector_integral_deg']:.3f} |"
            )
    (output_dir / 'replay.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=True)
    for recording in results:
        label = Path(recording['recording']).name
        for variant, data in recording['variants'].items():
            timeline = data['timeline']
            t = [row['elapsed_s'] for row in timeline]
            axes[0].plot(t, [row['scalar_integral_deg'] for row in timeline], label=f'{label}: {variant}')
            axes[1].plot(t, [row['vector_integral_deg'] for row in timeline], label=f'{label}: {variant}')
    for ax, ylabel in zip(axes, ('Scalar tail integral (deg)', 'Vector tail integral (deg)')):
        ax.axhline(180., color='black', linestyle='--', linewidth=.8)
        ax.set(xlabel='Elapsed seconds', ylabel=ylabel)
        ax.legend(fontsize='x-small', ncol=2)
    fig.savefig(output_dir / 'replay-timeline.png', dpi=150)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parameters', type=Path)
    parser.add_argument('recordings', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--direct', type=int, choices=(0, 120, 240), default=0)
    args = parser.parse_args(argv)
    package = load_sensor_package(args.parameters)
    results = [replay_recording(recording, package, direct=args.direct)
               for recording in args.recordings]
    _write_outputs(results, args.output)
    print(json.dumps({
        'output': str(args.output),
        'recordings': [result['recording'] for result in results],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
