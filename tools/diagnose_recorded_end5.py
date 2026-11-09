"""Inspect recorded curvature without running calibration or changing parameters."""
import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconstructor import Reconstructor


def integral(x, y, lo, hi):
    inside = (x > lo) & (x < hi)
    xx = np.r_[lo, x[inside], hi]
    return float(np.trapezoid(np.interp(xx, x, y), xx) * 180 / np.pi)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('parameters', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package = json.loads(args.parameters.read_text(encoding='utf-8'))
    rec = Reconstructor.__new__(Reconstructor)
    rec.samp_dist = np.array(package['regions']['full']['global_sample_dist_m'])
    end_gap = package['shared_parameters']['hardware_parameters']['end_value'] * .001
    rec.ad_samp_dist = np.r_[0., rec.samp_dist, rec.samp_dist[-1] + end_gap]
    rec.total_points = len(rec.samp_dist)
    rec.global_point_ids = np.arange(1, rec.total_points + 1)
    rec.num_channels_recon = 3
    rec.R = package['shared_parameters']['hardware_parameters']['R']
    rec.active_angles = None
    rec.interlaced_grating = False
    rec.global_phases_set = package['multi_region']['global_phases_set']
    recon_config = package['shared_parameters']['reconstruction_parameters']
    rec.move_filter = recon_config['move_filter']
    rec.move_filter_for_vector = recon_config['move_filter_for_vector']
    rec.interp_num = recon_config['interp_num']
    rec.sharpness = recon_config['sharpness']
    rec.min_consecutive = recon_config['min_consecutive']
    rec.multi_region_parameters = rec._normalise_multiregion_parameters(package)
    x = np.linspace(0, rec.ad_samp_dist[-1], rec.interp_num)
    rows = []
    selected = {}
    peak_frame = None
    peak_value = -np.inf
    t0 = None
    previous_strain = None
    bad_frames = 0
    with args.recording.open('rb') as stream:
        while True:
            try:
                frame = pickle.load(stream)
            except EOFError:
                break
            t0 = frame['timestamp'] if t0 is None else t0
            raw = np.asarray(frame['raw_data'])
            processed = raw[:, 1:] - raw[:, :1]
            bad = ~np.isfinite(processed).all(axis=1)
            if np.any(bad):
                bad_frames += 1
                if previous_strain is not None:
                    processed[bad] = previous_strain[bad]
            previous_strain = processed.copy()
            frame['_replay_strain'] = processed.T
            k = np.asarray(frame['cur_interp'])
            angle = np.asarray(frame['angle'])
            mag = np.asarray(frame['magnitude'])
            tail = integral(x, k, x[-1] - .05, x[-1])
            virtual = integral(x, k, rec.samp_dist[-1], x[-1])
            rows.append([frame['timestamp'] - t0, tail, virtual,
                         float(np.ptp(np.unwrap(angle[-4:])) * 180 / np.pi),
                         *mag[-4:]])
            if tail > peak_value:
                peak_value = tail
                peak_frame = frame
            index = len(rows) - 1
            if index % 100 == 0:
                selected[index] = frame
    arr = np.array(rows)
    peak = int(np.argmax(arr[:, 1]))
    selected[peak] = peak_frame
    representative = [min(selected, key=lambda i: abs(arr[i,0]-t)) for t in (130, 194.2)]
    examples = []
    figure_data = None
    for index in sorted(set([0, peak, *representative, *[int(i) for i in np.linspace(0, len(arr)-1, 10) // 100 * 100]])):
        frame = selected[index]
        strain = frame['_replay_strain']
        magnitude, angle, weights, slopes, diag = rec._assemble_multiregion_parameters(strain, 0)
        mag_error = float(np.max(np.abs(magnitude - np.asarray(frame['magnitude']))))
        angle_error = float(np.max(np.abs(np.angle(np.exp(1j*(np.asarray(angle)-frame['angle']))))))
        m = np.r_[magnitude[0], magnitude, magnitude[-1]]
        a = np.r_[angle[0], angle, angle[-1]]
        ki, ai, xi = rec._interpolate_curvature_vector(m, a, 'pchip')
        variants = {}
        for name, last in [('copied_weighted_tip', magnitude[-1]),
                           ('virtual_tip_zero', 0.),
                           ('virtual_tip_unweighted', magnitude[-1] / weights[-1])]:
            mm = m.copy()
            mm[-1] = last
            kk, aa, xx = rec._interpolate_curvature_vector(mm, a, 'pchip')
            variants[name] = {'tail_integrated_curvature_deg': integral(xx, kk, xx[-1]-.05, xx[-1]),
                              'virtual_segment_deg': integral(xx, kk, rec.samp_dist[-1], xx[-1])}
        mm = m.copy()
        mm[-2:] /= weights[-1]
        kk, aa, xx = rec._interpolate_curvature_vector(mm, a, 'pchip')
        variants['true_and_virtual_tip_unweighted'] = {
            'tail_integrated_curvature_deg': integral(xx, kk, xx[-1]-.05, xx[-1]),
            'virtual_segment_deg': integral(xx, kk, rec.samp_dist[-1], xx[-1])}
        examples.append({'frame': index, 'elapsed_s': arr[index, 0],
                         'recorded_tail_deg': arr[index, 1], 'recorded_virtual_deg': arr[index, 2],
                         'magnitude_replay_max_error': mag_error, 'angle_replay_max_error_rad': angle_error,
                         'interpolation_replay_max_error': float(np.max(np.abs(ki-frame['cur_interp']))),
                         'nonfinite_raw_point_ids': (np.flatnonzero(~np.isfinite(np.asarray(frame['raw_data'])).all(axis=1))+1).tolist(),
                         'base_curvature_tail': diag['base_magnitude'][-4:],
                         'weights_tail': weights[-4:].tolist(), 'slopes_tail': slopes[-4:].tolist(),
                         'curvature_tail': magnitude[-4:].tolist(),
                         'angle_tail_deg': np.rad2deg(angle[-4:]).tolist(),
                         'raw_bending_angle_tail_deg': np.rad2deg(np.arctan2(
                             -np.sum(strain*np.sin(np.arange(3)[:,None]*2*np.pi/3),axis=0),
                             -np.sum(strain*np.cos(np.arange(3)[:,None]*2*np.pi/3),axis=0))[-4:]).tolist(),
                         'interpolated_angle_tail_deg': np.rad2deg(np.unwrap(ai[xi >= xi[-1]-.05])).tolist(),
                         'counterfactuals': variants})
        if index == representative[-1]:
            figure_data = (index, frame, magnitude, np.asarray(angle), ki, ai, xi, variants)
    output = {'records': len(rows), 'duration_s': arr[-1, 0], 'sensor_length_m': x[-1],
              'tail_curvature_integral_deg_percentiles': np.percentile(arr[:,1], [0,25,50,75,95,100]).tolist(),
              'maximum_frame': peak, 'maximum_frame_metrics': arr[peak].tolist(), 'examples': examples,
              'frames_over_180_fraction': float(np.mean(arr[:,1]>180)),
              'nonfinite_raw_frames': bad_frames,
              'note': 'Integrated curvature measures accumulated tangent turning, not a signed planar angle. Virtual tip alternatives are diagnostics only.'}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'analysis.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez_compressed(args.output/'timeline.npz', metrics=arr)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), constrained_layout=True)
    axes[0].plot(arr[::10,0], arr[::10,1], lw=.7, label='Last 50 mm integral of curvature')
    axes[0].plot(arr[::10,0], arr[::10,2], lw=.7, label='Last 10 mm virtual segment')
    axes[0].axhline(180, color='r', ls='--', label='180 degree reference')
    axes[0].set(xlabel='Elapsed seconds', ylabel='Accumulated turning (deg)')
    axes[0].legend()
    index, frame, magnitude, angle, ki, ai, xi, variants = figure_data
    mask = xi >= xi[-1]-.065
    axes[1].plot((xi[mask]-xi[-1])*1000,ki[mask],label='Recorded/replayed vector PCHIP')
    axes[1].scatter((rec.samp_dist[-4:]-xi[-1])*1000,magnitude[-4:],label='Weighted real points')
    axes[1].axhline(np.pi/.05, color='r',ls='--',label='Uniform 180 degrees over 50 mm')
    axes[1].axvspan(-10,0,color='grey',alpha=.15,label='Virtual last 10 mm')
    axes[1].set(xlabel='Distance from tip (mm)',ylabel='Curvature (1/m)',title=f'Example at {arr[index,0]:.2f} s')
    axes[1].legend()
    raw_angles = np.array(next(e for e in examples if e['frame']==index)['raw_bending_angle_tail_deg'])
    corrected = np.rad2deg(np.unwrap(angle[-4:]))
    raw_angles = np.rad2deg(np.unwrap(np.deg2rad(raw_angles)))
    axes[2].plot((rec.samp_dist[-4:]-xi[-1])*1000, raw_angles-raw_angles[0], 'o-',label='Raw strain direction (relative)')
    axes[2].plot((rec.samp_dist[-4:]-xi[-1])*1000,corrected-corrected[0],'o-',label='After slope compensation (relative)')
    axes[2].set(xlabel='Distance from tip (mm)',ylabel='Relative bending-plane direction (deg)')
    axes[2].legend()
    fig.savefig(args.output/'diagnostic.png',dpi=160)
    plt.close(fig)
    print(json.dumps({k:v for k,v in output.items() if k!='examples'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
