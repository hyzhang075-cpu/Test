# Coverage-aware end5cm support check

The offline check uses the existing `191514` end5cm score report as the
production source of `weight_masses`, with `group_ids=[0, 0, 1, 2]`,
`min_effective_samples=1.0`, and `min_max_mass=0.05`. The existing `192950`
optimization result remains a complete 30-weight group-mean result; no new
optimization was run.

The support map excludes the single radius-0 sample; 1 sample is excluded and
13 non-zero-radius samples are used. Effective sample count is the sum of
group score masses, and reliability requires both effective count `>= 1.0`
and maximum mass `>= 0.05`. The resulting levels are:

| group | free levels | derived levels |
| --- | --- | --- |
| 0 (points 19–20) | 5, 6, 7, 8 | 0, 1, 2, 3, 4, 9 |
| 1 (point 21) | 5, 6, 9 | 0, 1, 2, 3, 4, 7, 8 |
| 2 (point 22) | 3, 4, 5, 6, 9 | 0, 1, 2, 7, 8 |

The free-parameter counts are 4, 3, and 5 (12 total). Internal derived runs
use log(weight) interpolation over actual threshold coordinates; derived edge
levels remain neutral `1.0`. The serialized runtime/package schema remains 30
weights.
