"""Local V4 evaluation harness (Layer 11).

Usage:
  python backend/scripts/run_local_evaluation.py --manifest backend/.local_evaluation/manifest.csv

Manifest CSV columns: sample_id,relative_path,label,source_category
  label: BONAFIDE | SYNTHETIC | OUT_OF_DOMAIN

Runs real V4 inference on each file and writes:
  backend/.local_evaluation/reports/evaluation_report.json
  backend/.local_evaluation/reports/per_sample.csv
  backend/.local_evaluation/reports/summary.txt
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
import sys  # noqa: E402

sys.path.insert(0, str(BACKEND))

from app.services.inference_service import run_inference_core  # noqa: E402
from app.services.model_loader import load_v4_model  # noqa: E402

EVAL_DIR = BACKEND / ".local_evaluation"
REPORT_DIR = EVAL_DIR / "reports"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(EVAL_DIR / "manifest.csv"))
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print("Manifest not found:", manifest_path)
        return 2

    handle = load_v4_model()
    if not handle.ready:
        print("Model failed to load:", handle.error)
        return 2
    from app.services.model_loader import set_model_handle

    set_model_handle(handle)

    rows = list(csv.DictReader(manifest_path.open(encoding="utf-8")))
    if not rows:
        print("Empty manifest")
        return 2

    results = []
    for row in rows:
        sample_id = row["sample_id"]
        rel = row["relative_path"]
        label = row["label"].strip().upper()
        source = row.get("source_category", "")
        path = EVAL_DIR / rel
        if not path.is_file():
            results.append({"sample_id": sample_id, "error": "file_not_found", "label": label})
            continue
        try:
            info = sf.info(str(path))
            duration = float(info.duration)
            sr = int(info.samplerate)
            channels = int(info.channels)
        except Exception as exc:  # noqa: BLE001
            results.append(
                {"sample_id": sample_id, "error": f"audio_info_failed: {exc}", "label": label}
            )
            continue

        # hash
        import hashlib

        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        sha = h.hexdigest()

        t0 = time.perf_counter()
        res = run_inference_core(str(path))
        elapsed = time.perf_counter() - t0

        results.append(
            {
                "sample_id": sample_id,
                "relative_path": rel,
                "label": label,
                "source_category": source,
                "duration_seconds": duration,
                "sample_rate": sr,
                "channels": channels,
                "sha256": sha,
                "status": res.message,
                "ready": res.ready,
                "inference_ready": res.inference_ready,
                "logit": res.logit,
                "spoof_probability": res.spoof_probability,
                "threshold": res.threshold,
                "predicted_class": res.predicted_class,
                "predicted_label": "SYNTHETIC"
                if res.predicted_class == 1
                else "GENUINE"
                if res.predicted_class == 0
                else None,
                "latency_seconds": round(elapsed, 4),
            }
        )

    # Metrics (only BONAFIDE/SYNTHETIC, excluding OUT_OF_DOMAIN)
    bin_rows = [
        r
        for r in results
        if r.get("label") in ("BONAFIDE", "SYNTHETIC") and r.get("predicted_class") is not None
    ]
    tp = sum(1 for r in bin_rows if r["label"] == "SYNTHETIC" and r["predicted_class"] == 1)
    tn = sum(1 for r in bin_rows if r["label"] == "BONAFIDE" and r["predicted_class"] == 0)
    fp = sum(1 for r in bin_rows if r["label"] == "BONAFIDE" and r["predicted_class"] == 1)
    fn = sum(1 for r in bin_rows if r["label"] == "SYNTHETIC" and r["predicted_class"] == 0)
    total = len(bin_rows)
    acc = (tp + tn) / total if total else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    far = fp / (fp + tn) if (fp + tn) else 0.0
    frr = fn / (fn + tp) if (fn + tp) else 0.0

    # distributions
    gen_probs = [
        r["spoof_probability"]
        for r in bin_rows
        if r["label"] == "BONAFIDE" and r["spoof_probability"] is not None
    ]
    syn_probs = [
        r["spoof_probability"]
        for r in bin_rows
        if r["label"] == "SYNTHETIC" and r["spoof_probability"] is not None
    ]

    report = {
        "total_samples": len(results),
        "binary_samples": total,
        "genuine_count": sum(1 for r in bin_rows if r["label"] == "BONAFIDE"),
        "synthetic_count": sum(1 for r in bin_rows if r["label"] == "SYNTHETIC"),
        "out_of_domain_count": sum(1 for r in results if r.get("label") == "OUT_OF_DOMAIN"),
        "correct_genuine": tn,
        "incorrect_genuine": fp,
        "correct_synthetic": tp,
        "incorrect_synthetic": fn,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "false_acceptance_rate": far,
        "false_rejection_rate": frr,
        "confusion_matrix": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "genuine_prob_min": min(gen_probs) if gen_probs else None,
        "genuine_prob_max": max(gen_probs) if gen_probs else None,
        "genuine_prob_mean": (sum(gen_probs) / len(gen_probs)) if gen_probs else None,
        "synthetic_prob_min": min(syn_probs) if syn_probs else None,
        "synthetic_prob_max": max(syn_probs) if syn_probs else None,
        "synthetic_prob_mean": (sum(syn_probs) / len(syn_probs)) if syn_probs else None,
        "avg_latency_seconds": (sum(r.get("latency_seconds", 0) for r in results) / len(results))
        if results
        else 0,
        "threshold": 0.39499999999999996,
        "temperature": 1.0,
        "model_version": "V4",
        "checkpoint_sha256": "40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda",
        "per_sample": results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "evaluation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # per-sample csv
    csv_path = REPORT_DIR / "per_sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    # summary txt
    summary = f"""SpeechShield V4 Local Evaluation Report
=====================================
Total samples: {report["total_samples"]}
Binary samples: {report["binary_samples"]}
Genuine: {report["genuine_count"]}  Synthetic: {report["synthetic_count"]}  Out-of-domain: {report["out_of_domain_count"]}

Confusion matrix (positive=SYNTHETIC):
  TP={tp}  TN={tn}  FP={fp}  FN={fn}

Accuracy:  {acc:.4f}
Precision: {prec:.4f}
Recall:    {rec:.4f}
F1:        {f1:.4f}
FAR:       {far:.4f}
FRR:       {frr:.4f}

Genuine prob:   min={report["genuine_prob_min"]} max={report["genuine_prob_max"]} mean={report["genuine_prob_mean"]}
Synthetic prob: min={report["synthetic_prob_min"]} max={report["synthetic_prob_max"]} mean={report["synthetic_prob_mean"]}

Threshold: {report["threshold"]}  Temperature: {report["temperature"]}
Avg latency: {report["avg_latency_seconds"]}s

NOTE: Small exploratory dataset. Not a statistically representative benchmark.
NOTE: V4 evaluates a 4-second segment (center crop / right pad). Long recordings are not fully analyzed.
"""
    (REPORT_DIR / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
