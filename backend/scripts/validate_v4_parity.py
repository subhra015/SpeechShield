"""V4 preprocessing parity validation against the approved golden references.

Usage:
  python backend/scripts/validate_v4_parity.py --reference-dir <dir>

The reference directory must contain:
  golden_manifest.json, checkpoint_provenance.json, preprocessing_config.json,
  fixtures/*.wav, references/*.npz

Exits nonzero if any required check fails.
Saves a unique timestamped JSON report under backend/.validation_reports/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.preprocessor import extract_features  # noqa: E402
from app.services.model_loader import load_v4_model  # noqa: E402

ARCHITECTURE = "CompactCNN"
PARAMETER_COUNT = 97761
STATE_DICT_ENTRIES = 30

EXPECTED_FIXTURES = {
    "genuine_normal",
    "synthetic_normal",
    "genuine_short_2s",
    "genuine_long_6s",
    "genuine_non16k_22050",
}

CONFIG_KEYS = [
    "target_sample_rate",
    "target_length_seconds",
    "n_mels",
    "n_fft",
    "hop_length",
    "mel_power",
    "mel_center",
    "mel_pad_mode",
    "mel_norm",
    "mel_scale",
    "mel_window",
    "log_epsilon",
    "normalization",
    "normalization_std_floor",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def model_state_fingerprint(state_dict: dict[str, torch.Tensor]) -> str:
    """Canonical V4 model-state fingerprint (matches golden generation)."""
    h = hashlib.sha256()
    for key in sorted(state_dict.keys()):
        tensor_cpu = state_dict[key].detach().cpu().contiguous()
        h.update(key.encode("utf-8"))
        h.update(str(tensor_cpu.dtype).encode("utf-8"))
        h.update(repr(tuple(tensor_cpu.shape)).encode("utf-8"))
        h.update(tensor_cpu.reshape(-1).view(torch.uint8).numpy().tobytes())
    return h.hexdigest()


def state_dict_equal(a: dict[str, torch.Tensor], b: dict[str, torch.Tensor]) -> dict[str, Any]:
    if set(a.keys()) != set(b.keys()):
        return {
            "equal": False,
            "reason": "key_set_mismatch",
            "keys_a": sorted(a.keys()),
            "keys_b": sorted(b.keys()),
        }
    for key in sorted(a.keys()):
        ta = a[key].detach().cpu()
        tb = b[key].detach().cpu()
        if ta.shape != tb.shape:
            return {
                "equal": False,
                "reason": "shape_mismatch",
                "key": key,
                "shape_a": list(ta.shape),
                "shape_b": list(tb.shape),
            }
        if str(ta.dtype) != str(tb.dtype):
            return {
                "equal": False,
                "reason": "dtype_mismatch",
                "key": key,
                "dtype_a": str(ta.dtype),
                "dtype_b": str(tb.dtype),
            }
        if not torch.equal(ta, tb):
            maxdiff = float((ta.float() - tb.float()).abs().max().item()) if ta.numel() else 0.0
            return {"equal": False, "reason": "value_mismatch", "key": key, "max_abs_diff": maxdiff}
    return {"equal": True, "reason": "ok", "entry_count": len(a)}


def compare_tensors(name: str, local: np.ndarray, ref: np.ndarray, atol: float) -> dict[str, Any]:
    local = np.asarray(local)
    ref = np.asarray(ref)
    shape_ok = local.shape == ref.shape
    dtype_ok = str(local.dtype) == str(ref.dtype)
    if shape_ok and local.size:
        max_abs = float(np.max(np.abs(local.astype(np.float64) - ref.astype(np.float64))))
        denom = np.maximum(np.abs(ref.astype(np.float64)), 1e-12)
        max_rel = float(np.max(np.abs(local.astype(np.float64) - ref.astype(np.float64)) / denom))
    else:
        max_abs = float("nan")
        max_rel = float("nan")
    if local.size and ref.size:
        finite_ok = bool(np.all(np.isfinite(local)) and np.all(np.isfinite(ref)))
    else:
        finite_ok = True
    passed = bool(shape_ok and dtype_ok and finite_ok and (max_abs <= atol))
    return {
        "name": name,
        "shape_local": list(local.shape),
        "shape_ref": list(ref.shape),
        "dtype_local": str(local.dtype),
        "dtype_ref": str(ref.dtype),
        "shape_ok": bool(shape_ok),
        "dtype_ok": bool(dtype_ok),
        "finite_ok": bool(finite_ok),
        "max_abs_error": max_abs,
        "max_rel_error": max_rel,
        "atol": atol,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", required=True)
    args = parser.parse_args()
    ref_dir = Path(args.reference_dir)

    try:
        manifest = json.loads((ref_dir / "golden_manifest.json").read_text(encoding="utf-8"))
        provenance = json.loads(
            (ref_dir / "checkpoint_provenance.json").read_text(encoding="utf-8")
        )
        preproc_cfg = json.loads(
            (ref_dir / "preprocessing_config.json").read_text(encoding="utf-8")
        )

        local_v4_cfg = json.loads(
            (BACKEND / "artifacts" / "v4" / "v4_config.json").read_text(encoding="utf-8")
        )
        local_preproc_cfg = json.loads(
            (BACKEND / "artifacts" / "v4" / "preprocessing_config.json").read_text(encoding="utf-8")
        )

        approved = manifest["approved_checkpoint"]
        ref_exec = manifest["reference_execution"]
        fixtures = manifest["fixture_records"]

        handle = load_v4_model()
        if not handle.ready:
            raise RuntimeError(f"Model failed to load: {handle.error}")

        # --- Provenance checks ---
        provenance_checks: dict[str, Any] = {}

        checkpoint_hash_ok = handle.checkpoint_sha256.lower() == approved["sha256"].lower()
        provenance_checks["checkpoint_sha256"] = {
            "local": handle.checkpoint_sha256,
            "approved": approved["sha256"],
            "passed": checkpoint_hash_ok,
        }

        arch_ok = (
            handle.config.get("model_architecture") == ARCHITECTURE
            and approved.get("architecture") == ARCHITECTURE
        )
        provenance_checks["architecture"] = {
            "local": handle.config.get("model_architecture"),
            "approved": approved.get("architecture"),
            "passed": arch_ok,
        }

        param_ok = (
            handle.parameter_count == PARAMETER_COUNT
            and approved.get("parameter_count") == PARAMETER_COUNT
        )
        provenance_checks["parameter_count"] = {
            "local": handle.parameter_count,
            "approved": approved.get("parameter_count"),
            "expected": PARAMETER_COUNT,
            "passed": param_ok,
        }

        # state dict from raw checkpoint
        raw_state = torch.load(handle.checkpoint_path, map_location="cpu", weights_only=True)
        raw_fp = model_state_fingerprint(raw_state)
        loaded_fp = model_state_fingerprint(handle.model.state_dict())
        fp_raw_ok = raw_fp.lower() == approved["model_state_sha256"].lower()
        fp_loaded_ok = loaded_fp.lower() == approved["model_state_sha256"].lower()
        provenance_checks["model_state_fingerprint_raw"] = {
            "local": raw_fp,
            "approved": approved["model_state_sha256"],
            "passed": fp_raw_ok,
        }
        provenance_checks["model_state_fingerprint_loaded"] = {
            "local": loaded_fp,
            "approved": approved["model_state_sha256"],
            "passed": fp_loaded_ok,
        }

        state_eq = state_dict_equal(raw_state, handle.model.state_dict())
        state_eq_ok = (
            state_eq.get("equal", False) and state_eq.get("entry_count") == STATE_DICT_ENTRIES
        )
        provenance_checks["state_dict_equality"] = {
            "equal": state_eq.get("equal", False),
            "entry_count": state_eq.get("entry_count"),
            "expected_entries": STATE_DICT_ENTRIES,
            "reason": state_eq.get("reason"),
            "passed": state_eq_ok,
        }

        # approved manifest entry count
        manifest_entries_ok = approved.get("state_dictionary_entries") == STATE_DICT_ENTRIES
        provenance_checks["manifest_entry_count"] = {
            "manifest": approved.get("state_dictionary_entries"),
            "expected": STATE_DICT_ENTRIES,
            "passed": manifest_entries_ok,
        }

        # threshold / temperature
        local_threshold = float(local_v4_cfg["classification_threshold"])
        golden_threshold = float(ref_exec["threshold"])
        threshold_ok = local_threshold == golden_threshold
        provenance_checks["threshold"] = {
            "local": local_threshold,
            "golden": golden_threshold,
            "passed": threshold_ok,
        }

        local_temp = float(local_v4_cfg.get("temperature", 1.0))
        golden_temp = float(ref_exec["temperature"])
        temp_ok = local_temp == golden_temp
        provenance_checks["temperature"] = {
            "local": local_temp,
            "golden": golden_temp,
            "passed": temp_ok,
        }

        # checkpoint provenance file
        prov_ckpt_ok = provenance.get("checkpoint_sha256", "").lower() == approved["sha256"].lower()
        prov_state_ok = (
            provenance.get("checkpoint_state_sha256", "").lower()
            == approved["model_state_sha256"].lower()
        )
        prov_active_ok = (
            provenance.get("active_model_state_sha256", "").lower()
            == approved["model_state_sha256"].lower()
        )
        prov_cpu_ok = (
            provenance.get("cpu_reference_model_state_sha256", "").lower()
            == approved["model_state_sha256"].lower()
        )
        prov_arch_ok = provenance.get("architecture") == ARCHITECTURE
        prov_params_ok = provenance.get("parameter_count") == PARAMETER_COUNT
        prov_thresh_ok = provenance.get("threshold") == golden_threshold
        prov_temp_ok = provenance.get("temperature") == golden_temp
        provenance_checks["checkpoint_provenance_file"] = {
            "checkpoint_sha256_ok": prov_ckpt_ok,
            "state_sha256_ok": prov_state_ok,
            "active_state_ok": prov_active_ok,
            "cpu_reference_state_ok": prov_cpu_ok,
            "architecture_ok": prov_arch_ok,
            "parameter_count_ok": prov_params_ok,
            "threshold_ok": prov_thresh_ok,
            "temperature_ok": prov_temp_ok,
            "passed": bool(
                prov_ckpt_ok
                and prov_state_ok
                and prov_active_ok
                and prov_cpu_ok
                and prov_arch_ok
                and prov_params_ok
                and prov_thresh_ok
                and prov_temp_ok
            ),
        }

        # preprocessing config match (key exists in both before comparing)
        preproc_match = True
        preproc_diffs = {}
        preproc_missing = []
        for k in CONFIG_KEYS:
            if k not in local_preproc_cfg or k not in preproc_cfg:
                preproc_match = False
                preproc_missing.append(k)
                continue
            if local_preproc_cfg.get(k) != preproc_cfg.get(k):
                preproc_match = False
                preproc_diffs[k] = {"local": local_preproc_cfg.get(k), "golden": preproc_cfg.get(k)}
        provenance_checks["preprocessing_config"] = {
            "passed": preproc_match and not preproc_missing,
            "missing_keys": preproc_missing,
            "diffs": preproc_diffs,
        }

        # --- Fixture set validation ---
        fixture_set_ok = set(fixtures.keys()) == EXPECTED_FIXTURES
        provenance_checks["fixture_set"] = {
            "expected": sorted(EXPECTED_FIXTURES),
            "actual": sorted(fixtures.keys()),
            "passed": fixture_set_ok,
        }

        # --- Per-fixture checks ---
        fixture_results: dict[str, Any] = {}
        all_fixtures_passed = True

        for name, info in fixtures.items():
            wav_path = ref_dir / info["input_fixture"]
            npz_path = ref_dir / info["reference_fixture"]

            # WAV hash
            wav_hash = sha256_file(wav_path)
            wav_hash_ok = wav_hash.lower() == info["input_sha256"].lower()

            # NPZ hash
            npz_hash = sha256_file(npz_path)
            npz_hash_ok = npz_hash.lower() == info["reference_sha256"].lower()

            # Load NPZ
            npz = np.load(npz_path, allow_pickle=False)
            try:
                sw = np.asarray(npz["standardized_waveform"])
                mel = np.asarray(npz["mel"])
                logmel = np.asarray(npz["log_mel"])
                mean = np.asarray(npz["normalization_mean"])
                std = np.asarray(npz["normalization_std"])
                norm = np.asarray(npz["normalized_feature_fp32"])
                fp16 = np.asarray(npz["feature_cache_fp16"])
                model_input_ref = np.asarray(npz["model_input_fp32"])
                golden_logit = float(npz["model_logit"])
                golden_prob = float(npz["spoof_probability"])
                golden_threshold = float(npz["decision_threshold"])
                golden_temp = float(npz["temperature"])
                golden_pred = int(npz["predicted_class"])
            finally:
                npz.close()

            # finite checks on scalars and arrays
            arrays = [sw, mel, logmel, mean, std, norm, fp16, model_input_ref]
            nonfinite = any(not np.all(np.isfinite(a)) for a in arrays if a.size)
            scalar_nonfinite = not (
                np.isfinite(golden_logit)
                and np.isfinite(golden_prob)
                and np.isfinite(golden_threshold)
                and np.isfinite(golden_temp)
            )
            nonfinite = nonfinite or scalar_nonfinite

            # shape checks
            shape_ok = (
                sw.shape == (64000,)
                and mel.shape == (64, 401)
                and logmel.shape == (64, 401)
                and mean.shape == (1, 1)
                and std.shape == (1, 1)
                and norm.shape == (1, 64, 401)
                and fp16.shape == (1, 64, 401)
                and model_input_ref.shape == (1, 64, 401)
            )

            # dtype checks (no conversion)
            dtype_ok = (
                str(sw.dtype) == "float32"
                and str(mel.dtype) == "float32"
                and str(logmel.dtype) == "float32"
                and str(mean.dtype) == "float32"
                and str(std.dtype) == "float32"
                and str(norm.dtype) == "float32"
                and str(fp16.dtype) == "float16"
                and str(model_input_ref.dtype) == "float32"
            )

            # per-fixture configuration checks
            cfg_threshold_ok = golden_threshold == ref_exec["threshold"]
            cfg_temp_ok = golden_temp == ref_exec["temperature"]
            cfg_logit_ok = golden_logit == info["model_logit"]
            cfg_prob_ok = golden_prob == info["spoof_probability"]
            cfg_pred_ok = golden_pred == info["predicted_class"]
            per_fixture_cfg_ok = bool(
                cfg_threshold_ok and cfg_temp_ok and cfg_logit_ok and cfg_prob_ok and cfg_pred_ok
            )

            # Run local preprocessing (no astype conversion before compare)
            feat = extract_features(wav_path)

            comps = []
            comps.append(
                compare_tensors(
                    "standardized_waveform",
                    feat["standardized_waveform"],
                    sw,
                    atol=0.0,
                )
            )
            comps.append(compare_tensors("mel", feat["mel"], mel, atol=2e-4))
            comps.append(compare_tensors("log_mel", feat["log_mel"], logmel, atol=2e-3))
            comps.append(
                compare_tensors("normalization_mean", feat["normalization_mean"], mean, atol=1e-5)
            )
            comps.append(
                compare_tensors("normalization_std", feat["normalization_std"], std, atol=1e-5)
            )
            comps.append(
                compare_tensors(
                    "normalized_feature_fp32", feat["normalized_feature_fp32"], norm, atol=5e-4
                )
            )
            comps.append(
                compare_tensors("feature_cache_fp16", feat["feature_cache_fp16"], fp16, atol=2e-3)
            )
            comps.append(
                compare_tensors(
                    "model_input_fp32", feat["model_input_fp32"], model_input_ref, atol=2e-3
                )
            )

            # Model outputs using local model + locally generated model input
            model_input = feat["model_input"]
            with torch.inference_mode():
                logit = handle.model(model_input).reshape(-1)
                prob = torch.sigmoid(logit / local_temp)
            local_logit = float(logit.item())
            local_prob = float(prob.item())
            local_pred = int(local_prob >= local_threshold)

            logit_err = abs(local_logit - golden_logit)
            prob_err = abs(local_prob - golden_prob)
            logit_ok = logit_err <= 1e-4
            prob_ok = prob_err <= 1e-5

            # classification consistency across 4 sources
            golden_pred_from_prob = int(golden_prob >= golden_threshold)
            class_sources = {
                "local_prob_vs_local_threshold": local_pred,
                "golden_prob_vs_golden_threshold": golden_pred_from_prob,
                "npz_predicted_class": golden_pred,
                "manifest_predicted_class": info["predicted_class"],
            }
            class_ok = local_pred == golden_pred_from_prob == golden_pred == info["predicted_class"]

            comps.append(
                {
                    "name": "model_logit",
                    "local": local_logit,
                    "golden": golden_logit,
                    "abs_error": logit_err,
                    "tolerance": 1e-4,
                    "passed": bool(logit_ok),
                }
            )
            comps.append(
                {
                    "name": "spoof_probability",
                    "local": local_prob,
                    "golden": golden_prob,
                    "abs_error": prob_err,
                    "tolerance": 1e-5,
                    "passed": bool(prob_ok),
                }
            )
            comps.append(
                {
                    "name": "predicted_class",
                    "local": local_pred,
                    "golden": golden_pred,
                    "threshold": local_threshold,
                    "class_sources": class_sources,
                    "passed": bool(class_ok),
                }
            )

            tensor_ok = all(c["passed"] for c in comps if "max_abs_error" in c)
            fixture_passed = bool(
                wav_hash_ok
                and npz_hash_ok
                and shape_ok
                and dtype_ok
                and not nonfinite
                and per_fixture_cfg_ok
                and tensor_ok
                and logit_ok
                and prob_ok
                and class_ok
            )
            all_fixtures_passed = all_fixtures_passed and fixture_passed

            fixture_results[name] = {
                "passed": fixture_passed,
                "wav_hash_ok": wav_hash_ok,
                "wav_hash_local": wav_hash,
                "wav_hash_expected": info["input_sha256"],
                "npz_hash_ok": npz_hash_ok,
                "npz_hash_local": npz_hash,
                "npz_hash_expected": info["reference_sha256"],
                "shape_ok": shape_ok,
                "dtype_ok": dtype_ok,
                "nonfinite": nonfinite,
                "per_fixture_config_ok": per_fixture_cfg_ok,
                "per_fixture_config": {
                    "threshold_ok": cfg_threshold_ok,
                    "temperature_ok": cfg_temp_ok,
                    "logit_ok": cfg_logit_ok,
                    "probability_ok": cfg_prob_ok,
                    "predicted_class_ok": cfg_pred_ok,
                },
                "comparisons": comps,
                "local_logit": local_logit,
                "golden_logit": golden_logit,
                "local_prob": local_prob,
                "golden_prob": golden_prob,
                "local_pred": local_pred,
                "golden_pred": golden_pred,
                "class_sources": class_sources,
            }

            status = "PASS" if fixture_passed else "FAIL"
            print(f"{name}: {status}")
            print(
                f"  wav_hash_ok={wav_hash_ok} npz_hash_ok={npz_hash_ok} shape_ok={shape_ok} dtype_ok={dtype_ok} nonfinite={nonfinite}"
            )
            for c in comps:
                if "max_abs_error" in c:
                    print(
                        f"  {c['name']}: {'PASS' if c['passed'] else 'FAIL'} max_abs={c['max_abs_error']:.3e}"
                    )
                else:
                    print(f"  {c['name']}: {'PASS' if c['passed'] else 'FAIL'}")

        # --- Overall acceptance ---
        prov_all_ok = all(
            v.get("passed", False)
            for v in provenance_checks.values()
            if isinstance(v, dict) and "passed" in v
        )
        prov_file_ok = provenance_checks["checkpoint_provenance_file"]["passed"]
        preproc_ok = provenance_checks["preprocessing_config"]["passed"]
        fixture_set_ok_flag = provenance_checks["fixture_set"]["passed"]

        overall_passed = bool(
            checkpoint_hash_ok
            and arch_ok
            and param_ok
            and fp_raw_ok
            and fp_loaded_ok
            and state_eq_ok
            and manifest_entries_ok
            and threshold_ok
            and temp_ok
            and prov_file_ok
            and preproc_ok
            and fixture_set_ok_flag
            and prov_all_ok
            and all_fixtures_passed
        )

        report = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "overall_passed": overall_passed,
            "checkpoint_provenance": provenance_checks,
            "preprocessing_config_match": preproc_ok,
            "fixtures": fixture_results,
            "aggregate": {
                "all_fixtures_passed": all_fixtures_passed,
                "provenance_passed": prov_all_ok,
                "fixture_set_ok": fixture_set_ok_flag,
            },
        }

        report_dir = BACKEND / ".validation_reports"
        report_dir.mkdir(exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        report_path = report_dir / f"v4_parity_report_{ts}.json"
        i = 1
        while report_path.exists():
            report_path = report_dir / f"v4_parity_report_{ts}_{i}.json"
            i += 1
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print("\nProvenance checks:")
        for k, v in provenance_checks.items():
            if isinstance(v, dict) and "passed" in v:
                print(f"  {k}: {'PASS' if v['passed'] else 'FAIL'}")
        print("\nOverall:", "PASS" if overall_passed else "FAIL")
        print("Report saved:", report_path)
        return 0 if overall_passed else 1

    except Exception as exc:  # noqa: BLE001
        # Capture failure evidence in a report instead of exiting silently.
        try:
            report_dir = BACKEND / ".validation_reports"
            report_dir.mkdir(exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            report_path = report_dir / f"v4_parity_report_{ts}_error.json"
            i = 1
            while report_path.exists():
                report_path = report_dir / f"v4_parity_report_{ts}_error_{i}.json"
                i += 1
            report_path.write_text(
                json.dumps(
                    {
                        "timestamp_utc": datetime.now(UTC).isoformat(),
                        "overall_passed": False,
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print("Error report saved:", report_path)
        except Exception:  # noqa: BLE001
            pass
        print("VALIDATION ERROR:", repr(exc))
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
