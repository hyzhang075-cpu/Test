"""Fixed local phase references and full level-zero bridge interval ownership."""
import numpy as np


def _mixed_slopes(sensor, frame, direct):
    """Estimate state-specific upstream slopes using the existing production score model."""
    _, magnitude, _, _ = sensor._get_base(keys=None, calib_Data=frame,
                                        base_slopes=sensor.slopes[direct][0], verbose=False)
    masses = sensor._alloc_mass(sensor._get_scores(magnitude=np.asarray(magnitude)))
    labels = np.empty(len(sensor.samp_dist), dtype=int)
    for index, (start, end) in enumerate(sensor.base_segments):
        labels[start:end] = index
    return np.sum(masses * np.asarray(sensor.slopes[direct])[:, labels], axis=0)


def build_fixed_phase_reference(full, upstream, context, direct):
    """Average nonzero circular states to the preceding point, then use full level zero.

    The returned first-real-point phase is fixed for the entire local optimization.
    Crop-origin phase is recorded separately because local integration starts at the
    first real point, not at the physical crop origin. All distances are in m.
    """
    ids = list(full.global_point_ids)
    first = ids.index(context['global_point_ids'][0])
    if first == 0:
        raise ValueError('local phase reference requires a preceding full point')
    left_id = ids[first-1]
    left = list(upstream.global_point_ids).index(left_id)
    labels = np.repeat(np.arange(len(full.base_segments)),
                       [end-start for start,end in full.base_segments])
    bridge = float(full.slopes[direct][0, labels[first]])
    samples = []
    for radius, frame in upstream.processed_Data['circ'][direct].items():
        if not isinstance(radius, (int,float)) or radius <= 0:
            continue
        slopes = _mixed_slopes(upstream, frame, direct)
        phase = float(upstream.global_phases_set + np.sum(
            slopes[1:left+1] * np.diff(upstream.samp_dist[:left+1])))
        if not np.isfinite(phase):
            raise ValueError('nonfinite upstream phase reference')
        samples.append((radius, phase))
    if not samples:
        raise ValueError('phase reference requires nonzero circular calibration states')
    phases = np.asarray([phase for _,phase in samples])
    mean_vector = np.mean(np.exp(1j*phases))
    if abs(mean_vector) < 1e-8:
        raise ValueError('upstream circular phase reference is ambiguous')
    mean = float(np.angle(mean_vector))
    left_position = float(full.samp_dist[first-1])
    crop_phase = mean + bridge*(float(context['crop_origin_m'])-left_position)
    first_phase = mean + bridge*(float(full.samp_dist[first])-left_position)
    return {'mode':'full_level0_fixed_bridge', 'direct':int(direct),
            'upstream_region':'full' if upstream is full else 'end15cm',
            'source_radii_mm':[radius for radius,_ in samples],
            'upstream_sample_phases_rad':[phase for _,phase in samples],
            'upstream_circular_resultant':float(abs(mean_vector)),
            'upstream_mean_phase_rad':mean, 'previous_point_id':int(left_id),
            'first_point_id':int(ids[first]), 'bridge_slope_rad_per_m':bridge,
            'phase_at_crop_origin_rad':float(crop_phase),
            'phase_at_first_point_rad':float(first_phase)}


def apply_full_bridge_slopes(slope_map, config, point_ids, direct):
    """Override only intervals ending at regional first points with full level-zero slopes."""
    full = config['regions']['full']
    labels = np.repeat(np.arange(len(full['local_segmentation'])), full['local_segmentation'])
    indices = {int(point):index for index,point in enumerate(point_ids)}
    for name in config['region_order']:
        if name == 'full':
            continue
        point = config['regions'][name]['support_point_ids'][0]
        local = full['support_point_ids'].index(point)
        slope_map[indices[point]] = full['slopes'][direct][0,labels[local]]


def anchor_full_mixed_phases(slope_map, full_mixed, distances, config, point_ids,
                             region_mixed_slopes=None):
    """Anchor first local region to full; later bridges use upstream local slope."""
    positions = np.asarray(distances, dtype=float)
    reference = np.asarray(full_mixed, dtype=float)
    if reference.shape != positions.shape or not np.all(np.isfinite(reference)):
        raise ValueError('Invalid independent full mixed slopes')
    indices = {int(point): i for i, point in enumerate(point_ids)}
    full = config['regions']['full']
    for point in full['owned_point_ids']:
        slope_map[indices[point]] = reference[indices[point]]
    target = np.r_[0., np.cumsum(reference[1:] * np.diff(positions))]
    evidence = []
    for name in config['region_order']:
        if name == 'full':
            continue
        point = config['regions'][name]['support_point_ids'][0]
        j = indices[point]
        if j == 0 or positions[j] <= positions[j-1]:
            raise ValueError('Phase anchor requires a preceding point and positive gap')
        before = float(np.sum(slope_map[1:j] * np.diff(positions[:j])))
        previous = config['region_order'][config['region_order'].index(name)-1]
        if previous == 'full':
            slope_map[j] = (target[j] - before) / (positions[j] - positions[j-1])
        else:
            upstream = config['regions'][previous]
            local_index = upstream['support_point_ids'].index(point)
            if region_mixed_slopes is None or previous not in region_mixed_slopes:
                raise ValueError('Missing upstream region mixed slopes for local bridge')
            slope_map[j] = region_mixed_slopes[previous][local_index]
        actual_target = before + slope_map[j] * (positions[j] - positions[j-1])
        evidence.append({'region': name, 'first_point_id': int(point),
                         'source_region': previous,
                         'target_twist_rad': float(actual_target),
                         'effective_bridge_slope_rad_per_m': float(slope_map[j])})
    return evidence


def assembled_sample_entry_phase(full, upstream, context, direct, local_frame):
    """Use the same raw-frame support and upstream scoring as runtime assembly.

    Outside the measured local support the experiment is assumed straight,
    matching the existing offline local-replay construction.
    """
    ids = list(full.global_point_ids)
    frame = np.asarray(full.processed_Data['circ'][direct][0], dtype=float).copy()
    indices = [ids.index(int(point)) for point in context['global_point_ids']]
    frame[indices] = local_frame
    mixed = _mixed_slopes(full, frame, direct)
    first = indices[0]
    if upstream is full:
        return float(full.global_phases_set + np.sum(
            mixed[1:first+1] * np.diff(full.samp_dist[:first+1])))
    support = list(upstream.global_point_ids)
    start = ids.index(int(support[0]))
    phase = full.global_phases_set + np.sum(
        mixed[1:start+1] * np.diff(full.samp_dist[:start+1]))
    local = frame[[ids.index(int(point)) for point in support]]
    upstream_mixed = _mixed_slopes(upstream, local, direct)
    end = support.index(int(context['global_point_ids'][0]))
    return float(phase + np.sum(upstream_mixed[1:end+1] * np.diff(upstream.samp_dist[:end+1])))


def build_assembled_phase_references(full, upstream, context, direct):
    """Audit metadata; optimization evaluates a separate phase for each frame."""
    radii = []
    phases = []
    # Constructing the optimizer later supplies the actual local measurements.
    # These upstream reference samples initialize only the display/global seed.
    for radius, frame in upstream.processed_Data['circ'][direct].items():
        if radius <= 0:
            continue
        indices = [list(upstream.global_point_ids).index(int(i)) for i in context['global_point_ids']]
        phases.append(assembled_sample_entry_phase(full, upstream, context, direct,
                                                  np.asarray(frame)[indices]))
        radii.append(radius)
    if not phases:
        raise ValueError('No nonzero circular upstream samples for phase initialization')
    mean = float(np.angle(np.mean(np.exp(1j*np.asarray(phases)))))
    return {'mode': 'assembled_absolute_direction_per_sample',
            'direct': int(direct), 'source_radii_mm': radii,
            'phase_at_first_point_rad': mean,
            'phase_at_crop_origin_rad': mean,
            'crop_phase_is_display_seed_only': True,
            'first_point_id': int(context['global_point_ids'][0]),
            'per_sample_phase_during_optimization': True}
