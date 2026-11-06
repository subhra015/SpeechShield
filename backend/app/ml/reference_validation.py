"""Reference parity validation contract (Layer 2).

Preprocessing parity is currently BLOCKED. This module defines the comparison
contract that must be satisfied once golden reference fixtures are available.
No fake or synthetic reference data is produced here.
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


# Parity is not verified. This flag gates inference.
PREPROCESSING_PARITY_VERIFIED: bool = False


def parity_status() -> dict[str, Any]:
    return {
        "preprocessing_parity_verified": PREPROCESSING_PARITY_VERIFIED,
        "inference_ready": False,
        "reason": "Training preprocessing source and golden reference fixtures are not available.",
    }
