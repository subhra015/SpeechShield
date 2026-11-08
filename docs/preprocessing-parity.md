# Preprocessing Parity Report (Layer 2 Revision)

## Result

**BLOCKED** — preprocessing stages match the golden references within justified tolerances, but the **local checkpoint hash does not match the golden-reference manifest checkpoint hash**, and the model logits do not match. Inference remains disabled.

- Local checkpoint SHA-256: `40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda`
- Golden manifest checkpoint SHA-256: `6f4f37e46e9fb22fcfd13334f6fb0d929c8170d125628c3d6e968b6f3272719f`
- Mismatch: YES

## Authoritative source

- Notebook: `D:\Projects\SpeechShield-Backups\SpeechShield_v4_high_throughput.ipynb`, Layer 2 "HIGH-THROUGHPUT AUDIO PREPROCESSOR".
- Configs: local `backend/artifacts/v4/v4_config.json` and `preprocessing_config.json`.
- Golden archive: `D:\Projects\SpeechShield-Backups\speechshield_v4_preprocessing_reference.zip`, extracted to `D:\Projects\SpeechShield-Backups\v4_reference_extracted`.

## Preprocessing sequence (verified, implemented in `backend/app/ml/preprocessor.py`)

1. Decode WAV/FLAC with soundfile (`always_2d=True`, float32).
2. Mono: arithmetic mean along axis 1 (float32) if 2D.
3. Reject empty / non-finite / invalid sr.
4. Resample with `scipy.signal.resample_poly`, gcd-reduced up/down factors, default filter, only if sr != 16000.
5. If longer than 64000: `start=(len-64000)//2`, slice `[start:start+64000]`.
6. If shorter: right-pad zeros to 64000.
7. Contiguous float32.
8. Mel: `torchaudio.transforms.MelSpectrogram` (sr=16000, n_fft=512, win_length=512, hop=160, f_min=0, f_max=8000, n_mels=64, hann window periodic, power=2.0, normalized=False, center=True, pad_mode=reflect, norm=None, mel_scale=htk).
9. `log_mel = log(mel + 1e-6)`.
10. mean over dims (1,2) keepdim; std population (unbiased=False) clamp_min(1e-5).
11. `features = ((log_mel - mean)/std).unsqueeze(1)` → (1,1,64,401) float32.
12. FP16 cache round trip: float32 → float16 → float32, then model input (1,1,64,401).

## Per-stage parity (all 5 fixtures)

| Fixture | waveform | mel | log_mel | mean | std | normalized | fp16 | model_input | logit | prob |
|---|---|---|---|---|---|---|---|---|---|---|
| genuine_normal | PASS 0 | PASS 9.16e-5 | PASS 1.82e-4 | PASS 0 | PASS 0 | PASS 6.56e-5 | PASS 9.77e-4 | PASS 9.77e-4 | FAIL 9.66e-3 | PASS 6.07e-9 |
| synthetic_normal | PASS 0 | PASS 1.83e-4 | PASS 1.24e-3 | PASS 1.43e-6 | PASS 1.91e-6 | PASS 2.75e-4 | PASS 1.95e-3 | PASS 1.95e-3 | FAIL 1.73e-2 | FAIL 3.96e-3 |
| genuine_short_2s | PASS 0 | PASS 4.58e-5 | PASS 1.24e-4 | PASS 2.86e-6 | PASS 0 | PASS 2.23e-5 | PASS 9.77e-4 | PASS 9.77e-4 | FAIL 6.10e-3 | FAIL 9.38e-4 |
| genuine_long_6s | PASS 0 | PASS 6.10e-5 | PASS 2.17e-4 | PASS 4.77e-7 | PASS 0 | PASS 6.57e-5 | PASS 9.77e-4 | PASS 9.77e-4 | FAIL 3.78e-3 | PASS 1.23e-7 |
| genuine_non16k_22050 | PASS 0 | PASS 9.16e-5 | PASS 3.16e-4 | PASS 0 | PASS 2.38e-7 | PASS 9.48e-5 | PASS 9.77e-4 | PASS 9.77e-4 | FAIL 6.60e-3 | FAIL 1.19e-3 |

Numbers are max absolute error. Tolerances justified by CPU (torchaudio 2.11.0+cpu) vs GPU (2.11.0+cu128) floating point; fp16 tolerance covers one ulp. Standardized waveform is bit-exact.

## Checkpoint mismatch (blocker)

The local checkpoint (`40c96ffa…`) differs from the golden manifest's checkpoint (`6f4f37e4…`). Feeding the golden's exact `model_input_fp32` to our model still yields a different logit (diff ~0.004–0.017), confirming weights differ, not just preprocessing. No file with hash `6f4f37e4…` exists on disk.

Therefore inference cannot be declared parity-verified for our checkpoint. Inference remains disabled. The preprocessing pipeline itself is verified and implemented.

## Tolerances

- waveform: 0 (exact)
- mel: 2e-4
- log_mel: 2e-3
- mean/std: 1e-5
- normalized: 5e-4
- fp16/model_input: 2e-3
- logit: 1e-4 (strict; fails due to checkpoint)
- prob: 1e-5 (strict; fails for some due to checkpoint)

## Validation command

```
backend\.venv\Scripts\python.exe backend\scripts\validate_v4_parity.py --reference-dir D:\Projects\SpeechShield-Backups\v4_reference_extracted
```

Report: `backend/.validation_reports/v4_parity_report.json` (gitignored).

## Status

BLOCKED due to checkpoint hash mismatch. Preprocessing implementation verified and tested. Public prediction API remains disabled.
