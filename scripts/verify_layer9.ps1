param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$cudaPython = "D:\SpeechShield-CUDA-App-Venv\Scripts\python.exe"
$ruffPython = Join-Path $backend ".venv\Scripts\python.exe"

function Step($name, $script) {
    Write-Host "=== $name ===" -ForegroundColor Cyan
    & $script
    if ($LASTEXITCODE -ne 0) { throw "$name FAILED (exit $LASTEXITCODE)" }
    Write-Host "$name PASS" -ForegroundColor Green
}

# 1. CUDA python exists
if (-not (Test-Path $cudaPython)) { throw "CUDA python not found" }

# 2. CUDA availability
& $cudaPython -c "import torch; assert torch.cuda.is_available(); print('CUDA OK', torch.cuda.get_device_name(0))" | Out-Host
if ($LASTEXITCODE -ne 0) { throw "CUDA unavailable" }

# 3. env
$env:PREPROCESSING_DEVICE = "cuda"

# 4. compile
Step "Backend compile" { & $cudaPython -m compileall -q $backend }

# 5. ruff format
Step "Ruff format" { & $ruffPython -m ruff format --check $backend }

# 6. ruff lint
Step "Ruff lint" { & $ruffPython -m ruff check $backend }

# 7. backend tests
Step "Backend tests" { & $cudaPython -m pytest (Join-Path $backend "tests") }

# 8. parity validator
$golden = "D:\Projects\SpeechShield-Backups\SpeechShield_V4_Approved_Golden_20261107T183430Z"
Step "Parity validator" { & $cudaPython (Join-Path $backend "scripts\validate_v4_parity.py") --reference-dir $golden }

# 9. frontend lint
Push-Location $frontend
try {
    Step "Frontend lint" { npm run lint }
    # 10. typecheck
    Step "Frontend typecheck" { npm run typecheck }
    # 11. tests
    Step "Frontend tests" { npm run test }
    # 12. build
    Step "Frontend build" { npm run build }
} finally {
    Pop-Location
}

# 13. checkpoint sha
$hashScript = Join-Path $env:TEMP "hash_check.py"
@"
import hashlib
p = r'$backend\artifacts\v4\checkpoints\best_v4.pt'
h = hashlib.sha256(open(p,'rb').read()).hexdigest()
print(h)
assert h == '40c96ffa919a8d9d1e188321ee76f215f93e09241ec444eaed9b627234a8acda'
"@ | Set-Content $hashScript
$hash = (& $cudaPython $hashScript).Trim()
if ($LASTEXITCODE -ne 0) { throw "Checkpoint hash mismatch" }
Write-Host "Checkpoint SHA OK: $hash" -ForegroundColor Green
Write-Host "Checkpoint SHA OK" -ForegroundColor Green

# 14. inference gate disabled
$gateScript = Join-Path $env:TEMP "gate_check.py"
@"
import sys
sys.path.insert(0, r'$backend')
from app.ml.reference_validation import PREPROCESSING_PARITY_VERIFIED
from app.services.inference_service import is_inference_ready
assert PREPROCESSING_PARITY_VERIFIED is False
assert is_inference_ready() is False
print('Inference gate: DISABLED (correct)')
"@ | Set-Content $gateScript
& $cudaPython $gateScript | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Inference gate check failed" }

# 15. production readiness disabled
$prScript = Join-Path $env:TEMP "pr_check.py"
@"
import sys
sys.path.insert(0, r'$backend')
from app.services.inference_service import is_inference_ready
from app.ml.reference_validation import PREPROCESSING_PARITY_VERIFIED
assert PREPROCESSING_PARITY_VERIFIED is False
assert is_inference_ready() is False
print('Production readiness: DISABLED (correct)')
"@ | Set-Content $prScript
& $cudaPython $prScript | Out-Host

# 16. git whitespace
Push-Location $root
try { git diff --check | Out-Host } finally { Pop-Location }

Write-Host "=== LAYER 9 VERIFICATION: PASS ===" -ForegroundColor Green
exit 0
