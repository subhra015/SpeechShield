# Preprocessing Parity Report (Layer 2)

## Result

**BLOCKED_PREPROCESSING_PARITY** — training preprocessing source and golden reference fixtures are unavailable. No guessed pipeline implemented. Inference disabled.

## Evidence audit

| Parameter | Saved value | Training implementation evidence | Verification status |
|---|---|---|---|
| Sample rate | 16000 Hz | Config only | Unverified source |
| Channels | Mono (assumed) | Not specified | **Unknown** (mono conversion method) |
| Target duration | 4.0 s | Config only | Inspected |
| Crop policy | center_crop_or_right_pad | Name only | **Unknown** (index rounding, alignment) |
| n_mels | 64 | Config only | Inspected |
| n_fft | 512 | Config only | Inspected |
| hop_length | 160 | Config only | Inspected |
| mel_power | 2.0 | Config only | Inspected |
| mel_center | true | Config only | Inspected |
| pad_mode | reflect | Config only | Inspected |
| mel_scale | htk | Config only | Inspected |
| mel_norm | null | Config only | Inspected (null) |
| Window | hann | Config only | **Unknown** (periodic vs symmetric) |
| f_min / f_max | Not in config | None | **Unknown** (defaults assumed by librosa: 0..sr/2; unverified) |
| Log transformation | epsilon only | None | **Unknown** (ln vs log10 vs log1p) |
| Log epsilon | 1e-6 | Config only | Inspected |
| Normalization | per_recording_mean_std | Name only | **Unknown** (order vs log, population vs sample std, dims) |
| Std floor | 1e-5 | Config only | Inspected |
| Resampling method | Not specified | None | **Unknown** |
| Crop alignment | Not specified | None | **Unknown** |

## Unknowns (must not be guessed)

1. Natural log vs base-10 log vs log1p.
2. Mel f_min / f_max.
3. Hann window periodicity (librosa default periodic=True; training may differ).
4. Resampling filter (librosa default kaiser-best; training may differ).
5. Stereo-to-mono downmix method.
6. Center-crop index rounding and right-pad fill.
7. Normalization order relative to log.
8. Population vs sample standard deviation.
9. Normalization axes (per-recording vs per-feature).

## Missing evidence required from original Kaggle runtime

To unblock, export a small golden reference package containing, per example:

- Input WAV (or deterministic source waveform) + metadata.
- Expected cropped/padded waveform.
- Expected log-Mel tensor (shape, dtype, values).
- Expected normalized feature tensor.
- Expected model logit and sigmoid spoof probability.

Representative examples needed:
1. Normal-length genuine recording.
2. Synthetic (spoof) recording.
3. Shorter-than-4s recording.
4. Longer-than-4s recording.
5. Non-16-kHz input.

Also needed: the original training preprocessing source (Python cell) or notebook.

## How to generate (Kaggle)

Run the original training preprocessing on the above examples and save arrays with `numpy.save` / `torch.save`, plus input WAVs, into a zip. Provide SHA-256s. Do not fabricate.

## Parity comparison metrics (to apply once fixtures exist)

- Max absolute error, mean absolute error, relative error.
- Tensor shape, dtype, NaN/Inf count.
- Logit and probability tolerance.

## Current decision

Inference stays disabled. No prediction endpoint. `inference_ready = false`. Do not treat this as a pass.
