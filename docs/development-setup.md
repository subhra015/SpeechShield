# Development Setup

## Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn app.main:app --reload
```

Environment: copy `backend/.env.example` to `backend/.env` and adjust. Artifacts must be present under `backend/artifacts/v4`.

Quality commands:

```powershell
cd backend
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\pytest
```

## Frontend

```powershell
cd frontend
npm ci
npm run dev
```

Quality commands:

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

## Docker (optional, Docker required)

```powershell
docker compose up --build
```

Artifacts are mounted read-only; never baked into images.

## Notes

- Python 3.13.15, PyTorch 2.11.0+cpu, torchaudio 2.11.0+cpu (pinned).
- Inference remains blocked (preprocessing parity unverified).
- FFmpeg not integrated; only WAV/FLAC claimed.
