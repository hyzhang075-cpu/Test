# 09B7 calibration replay acceptance

Means across available calibration radii; not worst-case per-radius or independent/live accuracy.

## Standalone replay

| Region | Direction | Point (%) | End (%) | rot_ang |
|---|---|---:|---:|---:|
| full | 0 | 0.3297 | 0.9447 | -31.40000000 |
| end15cm | 0 | 2.6575 | 5.3638 | 8.86571135 |
| end5cm | 0 | 4.3277 | 9.4632 | -5.14095148 |
| full | 120 | 0.5197 | 0.8549 | -31.40000000 |
| end15cm | 120 | 2.8467 | 7.3492 | 12.90348095 |
| end5cm | 120 | 3.9940 | 8.4591 | -17.61637322 |
| full | 240 | 0.5253 | 0.7382 | -31.40000000 |
| end15cm | 240 | 3.6165 | 7.1353 | 16.22876515 |
| end5cm | 240 | 4.5128 | 9.6559 | -0.20584327 |

## Assembled replay

Full assembled errors are listed separately and are not subject to the standalone full 1% gate. Local cases substitute local measurements into the full straight frame.

| Region | Direction | Point (%) | End (%) |
|---|---|---:|---:|
| full | 0 | 0.3494 | 1.3759 |
| end15cm | 0 | 5.3152 | 10.6616 |
| end5cm | 0 | 6.7862 | 6.4656 |
| full | 120 | 0.5357 | 1.2770 |
| end15cm | 120 | 3.9308 | 8.3466 |
| end5cm | 120 | 8.5589 | 9.6528 |
| full | 240 | 0.5377 | 0.8571 |
| end15cm | 240 | 8.4363 | 17.4934 |
| end5cm | 240 | 5.6497 | 8.9888 |

## Raw phase verification

Actual assembled theta_dynamic is compared directly to independently measured local initial phases, without any rot_ang conversion. Original validator phase gates are reported separately; overall deployment gates may remain false.

| Region | Direction | Raw actual max (deg) | Raw actual repeated (deg) |
|---|---|---:|---:|
| end15cm | 0 | 27.6480 | 27.6480 |
| end5cm | 0 | 7.7952 | 7.7952 |
| end15cm | 120 | 27.3760 | 27.3760 |
| end5cm | 120 | 27.3887 | 27.3887 |
| end15cm | 240 | 28.3327 | 28.3327 |
| end5cm | 240 | 27.1309 | 27.1309 |

## Reconstruct

Standalone local commands must supply their recorded rot_ang; the current application does not automatically select per-region replay angles. Full assembled reconstruction uses rot_ang=-31.4.

The old foreign-sensor stored-zero path was disabled. Live inference is not validated; first-frame zero requires a straight initial sensor state.

```powershell
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang 8.86571134952891
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang -5.14095147905175
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib True --use_full_transported_phase False --direct 0 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang 12.9034809463977
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang -17.6163732208917
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib True --use_full_transported_phase False --direct 120 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region full --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang -31.4
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang 16.2287651520802
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib False --optimization_region end5cm --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang -0.205843266481622
python main.py --task recon --sensor_params params/09B7_20261102_original_phase_pass.json --multi_region_calib True --use_full_transported_phase False --direct 240 --exp_directs "[0,120,240]" --rot_ang -31.4
```

Parameter SHA256: `5508adf2eae2ddd7c146c8fcac81192fad751b2425cdcb8b9503f2659b314a6b`.
