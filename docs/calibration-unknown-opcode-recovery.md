# Calibration `unknown opcode` recovery

## Purpose

This document describes the recovery added for an intermittent CPython
`SystemError: unknown opcode` during a long SciPy calibration run. It is
intended to make the same behavior straightforward to port to other branches.

The recovery is deliberately narrow. It does not treat general optimizer,
data, numerical, or programming errors as recoverable.

## Observed incident

The `08B5` direction-0 full-length slopes optimization completed iterations
0, 1, and 2. Its loss improved as follows:

| iteration | final loss |
|---:|---:|
| 0 | 0.005525586864464374 |
| 1 | 0.004405475879551882 |
| 2 | 0.0037481582139310167 |

Iteration 3 then failed while SciPy Powell was evaluating the objective:

```text
XXX lineno: 32760, opcode: -713767328
SystemError: unknown opcode
```

The traceback ended at `numpy.insert`, called through reconstruction from the
optimizer loss function. The impossible source line and invalid opcode show
that CPython detected invalid interpreter bytecode/state. They do not show
that `numpy.insert` received invalid calibration input. The precise native
component responsible cannot be identified from this traceback alone.

The observed runtime was:

- Python 3.10.19 (Anaconda)
- NumPy 2.0.1
- SciPy 1.15.1

## Recovery policy

Recovery is implemented inside
`Optimiser._optim_one_coeff_until_stop()` so it applies independently to the
slopes and weights stages.

For every optimization iteration:

1. Snapshot the current direction's weights and slopes.
2. Run the iteration normally.
3. If it raises `SystemError` whose message contains `unknown opcode`:
   - restore both snapshots;
   - recreate the iteration call and retry it once.
4. If the retry succeeds, accept its result and continue normally.
5. If the retry raises the same error again:
   - restore both snapshots again;
   - if an earlier iteration completed successfully, return its parameters and
     loss with stage status `runtime_error_fallback`;
   - otherwise re-raise the exception because there is no validated fallback.
6. Any other exception is re-raised without retry.

After a slopes fallback, `Optimiser.optim_coeff()` still runs weights. After
the full region returns successfully and completes its final normal-mode
reconstruction, `run_calibration_jobs()` records it as complete and continues
to `end15cm` and `end5cm`.

The final normal-mode reconstruction remains mandatory. If interpreter or
native-library state is still unusable, that validation raises and prevents
the region from being marked complete.

## Result schema

Recovered events are stored under the affected optimization stage:

```json
{
  "optimization": {
    "stages": {
      "slopes": {
        "status": "runtime_error_fallback",
        "start_loss": 0.01,
        "final_loss": 0.0037481582139310167,
        "recoveries": [
          {
            "iteration": 3,
            "exception_type": "SystemError",
            "message": "unknown opcode",
            "retry_count": 1,
            "occurrences": 2,
            "outcome": "fallback_previous_iteration",
            "fallback_iteration": 2,
            "fallback_loss": 0.0037481582139310167
          }
        ]
      }
    }
  }
}
```

When the one retry succeeds, the stage keeps its normal final status and the
event uses:

```json
{
  "retry_count": 1,
  "occurrences": 1,
  "outcome": "retry_succeeded"
}
```

`runtime_error_fallback` is intentionally distinct from `converge`. Existing
parameter-package quality gates therefore expose the recovered stage as not
fully converged instead of silently certifying it.

## Files to port

The functional change is limited to:

- `optimiser.py`
  - unpack recovery records for slopes and weights;
  - attach non-empty recovery lists to stage results;
  - retry and rollback logic in `_optim_one_coeff_until_stop()`.
- `tests/test_optimiser_status.py`
  - retry succeeds from a clean snapshot;
  - repeated failure falls back to the last successful iteration;
  - repeated failure in iteration 0 still raises;
  - unrelated `SystemError` is not retried;
  - slopes fallback still proceeds to weights;
  - existing nonfinite and no-improvement rollback behavior remains intact.

No changes are required in `calibration_batch.py`: a recovered optimizer
returns normally, so the existing batch loop records the region and advances
to the next region.

## Porting checklist

1. Confirm the target branch still has the two-stage
   `Optimiser.optim_coeff()` flow and `_optim_one_coeff_until_stop()` loop.
2. Port the tests first and verify that the new recovery tests fail for the
   expected missing behavior.
3. Port the optimizer change.
4. Run `tests/test_optimiser_status.py` and the full test suite.
5. Confirm that a synthetic repeated `unknown opcode` after one successful
   iteration produces `runtime_error_fallback` and restored parameter arrays.
6. Confirm that a first-iteration repeated failure and unrelated exceptions
   still abort the run.
7. Preserve the distinct status in downstream quality gates; do not translate
   it to `converge`.

## Operational recommendation

This recovery prevents a catchable intermittent interpreter failure from
discarding hours of valid optimization work. It is not a substitute for
investigating repeated runtime corruption. If `unknown opcode` occurs often,
capture the complete console log, run memory diagnostics, and test a fresh
Python/NumPy/SciPy environment before trusting large calibration batches.
