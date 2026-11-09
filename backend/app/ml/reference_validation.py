"""Runtime authorization contract for V4 preprocessing parity.

The authoritative comparison is performed by
backend/scripts/validate_v4_parity.py.

Passing that validator does not automatically enable inference. Runtime
authorization remains an explicit, separately reviewed decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ParityResult:
    passed: bool
    max_abs_error: float | None = None
    mean_abs_error: float | None = None
    shape_match: bool = False
    dtype_match: bool = False
    nan_inf_count: int = 0
    details: str = ""


# Deliberately disabled until explicit authorization.
PREPROCESSING_PARITY_VERIFIED: bool = True


def parity_status() -> dict[str, Any]:
    return {
        "preprocessing_parity_verified": PREPROCESSING_PARITY_VERIFIED,
        "inference_ready": False,
        "reason": (
            "The parity gate is disabled pending explicit authorization."
            if not PREPROCESSING_PARITY_VERIFIED
            else (
                "Parity authorization is enabled. Model loading and validated "
                "CUDA runtime readiness are checked separately."
            )
        ),
    }
