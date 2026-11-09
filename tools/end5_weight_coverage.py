"""Pure coverage diagnostics for independent end5cm weight groups."""

from collections import defaultdict

import numpy as np


def _group_level_masses(sample, groups, num_levels):
    masses = np.asarray(sample.get('weight_masses'), dtype=float)
    if (masses.ndim != 2 or masses.shape != (num_levels, groups.size)
            or not np.all(np.isfinite(masses))):
        raise ValueError('sample weight_masses shape must match thresholds and group_ids')
    return {
        int(group): masses[:, np.flatnonzero(groups == group)].mean(axis=1)
        for group in sorted(set(groups.tolist()))
    }


def build_groupwise_support_map(
    samples, *, thresholds, group_ids=(0, 0, 1, 2),
    min_effective_samples=1.0, min_max_mass=0.05,
):
    """Build a fixed reliable/free/derived level map from group-mean masses."""
    groups = np.asarray(group_ids, dtype=int)
    thresholds = [float(value) for value in thresholds]
    num_levels = len(thresholds) + 1
    if groups.ndim != 1 or groups.size == 0:
        raise ValueError('group_ids must be a non-empty one-dimensional sequence')
    if (not thresholds or not np.all(np.isfinite(thresholds))
            or np.any(np.asarray(thresholds) <= 0)
            or np.any(np.diff(np.asarray(thresholds)) <= 0)):
        raise ValueError('thresholds must be finite, positive, and strictly increasing')
    if (not np.isfinite(min_effective_samples) or not np.isfinite(min_max_mass)
            or min_effective_samples < 0 or min_max_mass < 0):
        raise ValueError('coverage thresholds must be non-negative')
    totals = {int(group): np.zeros(num_levels, dtype=float)
              for group in sorted(set(groups.tolist()))}
    maxima = {int(group): np.zeros(num_levels, dtype=float)
              for group in sorted(set(groups.tolist()))}
    point_ids = {}
    used_samples = 0
    excluded_radius_zero = 0
    for sample in samples:
        keys = sample.get('keys', [])
        radius = keys[0] if keys else None
        theory = sample.get('theoretical_curvature_m_inv')
        is_zero_radius = radius is not None and float(radius) == 0.0
        is_zero_theory = theory is not None and float(theory) == 0.0
        if is_zero_radius or is_zero_theory:
            excluded_radius_zero += 1
            continue
        level_masses = _group_level_masses(sample, groups, num_levels)
        used_samples += 1
        ids = np.asarray(sample.get('global_point_ids', np.arange(groups.size)), dtype=int)
        if ids.shape != groups.shape:
            raise ValueError('sample global_point_ids must match group_ids')
        for group, values in level_masses.items():
            # Effective sample count is the accumulated score mass. Tiny
            # sigmoid tails therefore cannot masquerade as full samples.
            totals[group] += values
            maxima[group] = np.maximum(maxima[group], values)
            point_ids.setdefault(str(group), ids[np.flatnonzero(groups == group)].tolist())

    result = {
        'thresholds': thresholds,
        'num_levels': num_levels,
        'definition': {
            'min_effective_samples': float(min_effective_samples),
            'min_max_mass': float(min_max_mass),
            'effective_sample_count_definition': 'sum of group score-mass samples',
            'reliable_rule': 'effective_sample_count >= min_effective_samples and max_mass >= min_max_mass',
            'excluded_radius_zero_samples': excluded_radius_zero,
            'used_nonzero_radius_samples': used_samples,
        },
        'groups': {},
    }
    for group in sorted(totals):
        reliable = [
            level for level in range(num_levels)
            if totals[group][level] >= min_effective_samples
            and maxima[group][level] >= min_max_mass
        ]
        derived = [level for level in range(num_levels) if level not in reliable]
        result['groups'][str(group)] = {
            'point_ids': point_ids.get(str(group), []),
            'levels': [
                {
                    'level': level,
                    'effective_sample_count': float(totals[group][level]),
                    'max_mass': float(maxima[group][level]),
                    'reliable': level in reliable,
                }
                for level in range(num_levels)
            ],
            'reliable_levels': reliable,
            'free_levels': reliable,
            'derived_levels': derived,
        }
    return result


def expand_groupwise_weights(free_weights, support_map, *, neutral=1.0):
    """Expand free group anchors to a complete vector using log interpolation."""
    neutral = float(neutral)
    if not np.isfinite(neutral) or neutral <= 0:
        raise ValueError('neutral weight must be positive and finite')
    thresholds = np.asarray(support_map['thresholds'], dtype=float)
    num_levels = int(support_map['num_levels'])
    if (thresholds.ndim != 1 or thresholds.size + 1 != num_levels
            or not thresholds.size or not np.all(np.isfinite(thresholds))
            or np.any(thresholds <= 0) or np.any(np.diff(thresholds) <= 0)):
        raise ValueError('support map thresholds must be finite, positive, and strictly increasing')
    # Level 0 is the below-first-threshold interval; subsequent levels are
    # located at the actual threshold coordinates.
    coordinates = np.concatenate(([0.0], thresholds))
    expanded = []
    for group_name in sorted(support_map['groups'], key=int):
        group = support_map['groups'][group_name]
        free_levels = [int(level) for level in group.get('free_levels', ())]
        values = free_weights.get(group_name, free_weights.get(int(group_name), {}))
        values = {int(level): float(value) for level, value in values.items()}
        missing = [level for level in free_levels if level not in values]
        if missing:
            raise ValueError(f'group {group_name} missing free levels: {missing}')
        for level in free_levels:
            value = values[level]
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f'group {group_name} level {level} anchor must be positive and finite')
        row = np.full(num_levels, neutral, dtype=float)
        for level in free_levels:
            row[level] = values[level]
        for level in group.get('derived_levels', ()):
            lower = [anchor for anchor in free_levels if anchor < level]
            upper = [anchor for anchor in free_levels if anchor > level]
            if not lower or not upper:
                row[level] = neutral
                continue
            left, right = max(lower), min(upper)
            left_coord, right_coord = coordinates[left], coordinates[right]
            if right_coord <= left_coord:
                raise ValueError(f'group {group_name} threshold coordinates are not increasing')
            fraction = (coordinates[level] - left_coord) / (right_coord - left_coord)
            row[level] = np.exp(
                np.log(row[left]) + fraction * (np.log(row[right]) - np.log(row[left]))
            )
        expanded.append(row)
    return np.asarray(expanded, dtype=float)


def _finite_or_none(value):
    value = float(value)
    return value if np.isfinite(value) else None


def compute_groupwise_weight_coverage(
    samples, *, thresholds, weights, weight_bounds, group_ids=(0, 0, 1, 2),
    mass_threshold=0.05, magnitude_epsilon=1e-12,
):
    """Summarize theory-vs-measurement coverage for shared group scores.

    ``samples`` is the score report's sample list.  A sample contains the
    measured pointwise ``score_magnitude``, ``global_point_ids``, its
    theoretical curvature, and groupwise ``weight_masses``.  The function is
    deliberately independent of ``Optimiser`` so reports can be tested or
    regenerated without loading calibration data.
    """
    groups = np.asarray(group_ids, dtype=int)
    weights = np.asarray(weights, dtype=float).reshape(-1, len(thresholds) + 1)
    if groups.ndim != 1 or groups.size == 0:
        raise ValueError('group_ids must be a non-empty one-dimensional sequence')
    if weights.shape[0] != int(groups.max()) + 1:
        raise ValueError('weights group count does not match group_ids')
    lower, upper = (float(value) for value in weight_bounds)
    group_values = {}
    for group in sorted(set(groups.tolist())):
        indices = np.flatnonzero(groups == group)
        point_ids = []
        rows = []
        for sample in samples:
            magnitudes = np.asarray(sample['score_magnitude'], dtype=float)
            ids = np.asarray(sample.get('global_point_ids', np.arange(groups.size)), dtype=int)
            if magnitudes.shape != groups.shape or ids.shape != groups.shape:
                raise ValueError('sample point arrays must match group_ids')
            selected = magnitudes[indices]
            base = float(np.mean(selected))
            theory = sample.get('theoretical_curvature_m_inv')
            theory = None if theory is None else float(theory)
            gain = None
            if (theory is not None and np.isfinite(theory)
                    and abs(theory) > magnitude_epsilon
                    and abs(base) > magnitude_epsilon):
                gain = theory / base
            masses = np.asarray(sample.get('weight_masses'), dtype=float)
            if masses.shape[1] != groups.size:
                raise ValueError('sample weight_masses point count must match group_ids')
            group_mass = masses[:, indices].mean(axis=1)
            rows.append({
                'keys': list(sample.get('keys', [])),
                'radius_mm': sample.get('keys', [None])[0] if sample.get('keys') else None,
                'point_ids': ids[indices].tolist(),
                'base_magnitude': base,
                'theoretical_curvature_m_inv': _finite_or_none(theory) if theory is not None else None,
                'required_gain': _finite_or_none(gain) if gain is not None else None,
                'level_mass': group_mass.tolist(),
            })
            if not point_ids:
                point_ids = ids[indices].tolist()
        level_rows = []
        for level, weight in enumerate(weights[group]):
            masses = np.asarray([row['level_mass'][level] for row in rows], dtype=float)
            dominant = np.asarray([
                int(np.argmax(row['level_mass'])) == level for row in rows
            ], dtype=bool)
            level_rows.append({
                'level': level,
                'weight': float(weight),
                'dominant_level_count': int(dominant.sum()),
                'mass_threshold_count': int((masses > mass_threshold).sum()),
                'effective_sample_count': float(masses.sum()),
                'max_mass': float(masses.max()) if masses.size else 0.0,
            })
        over = []
        for row in rows:
            gain = row['required_gain']
            if gain is not None and (gain < lower or gain > upper):
                over.append({
                    'keys': row['keys'], 'required_gain': gain,
                    'side': 'below_lower' if gain < lower else 'above_upper',
                })
        group_values[str(group)] = {
            'point_ids': point_ids,
            'samples': rows,
            'levels': level_rows,
            'uncovered_levels': [
                row['level'] for row in level_rows
                if row['dominant_level_count'] == 0 and row['mass_threshold_count'] == 0
            ],
            'theory_gain_over_bounds': over,
        }
    return {
        'definition': {
            'group_ids': groups.tolist(),
            'mass_threshold': float(mass_threshold),
            'coverage_rule': 'level is covered when dominant_level_count > 0 or mass_threshold_count > 0',
            'required_gain': 'theoretical_curvature_m_inv / group base magnitude',
        },
        'groups': group_values,
        'opt_bound_hits': {
            'lower': int(np.isclose(weights, lower, rtol=0, atol=1e-6).sum()),
            'upper': int(np.isclose(weights, upper, rtol=0, atol=1e-6).sum()),
            'total': int(weights.size),
        },
    }
