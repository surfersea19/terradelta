# TerraDelta 🌍

**AI-powered human change detection from Sentinel-2 satellite imagery**

ISRO Capstone Project | Undergraduate CSE

---

## What It Does

TerraDelta detects and quantifies human-caused land changes (buildings, roads, infrastructure)
between two Sentinel-2 satellite image dates over a user-defined area.
It separates human development from natural/seasonal changes using a trained Random Forest
model with 42 spectral, temporal, and texture features.

---

## Features

| Feature | Description |
|---|---|
| **Change Analysis** | Select dates + AOI → get before/after imagery + change map + statistics + interpretation |
| **Change Explorer** | Explore pre-analyzed notable development events worldwide (GeoGuessr-style) |
| **Area Monitoring** | Compare an area across 2–6 dates, see development timeline |
| **PDF Report** | One-click PDF export of analysis results |

---

## Quick Start (Development)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # add CDSE credentials if you have them
uvicorn main:app --reload --port 8000
```

Backend runs at http://localhost:8000
API docs at http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

### With Docker Compose

```bash
cp backend/.env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000

---

## ML Training

### Train Random Forest (recommended, no GPU needed)

```bash
cd ml

# With real labeled data (OSCD format):
python prepare_data.py --data-dir ./raw_scenes --output-dir ./data
python train_rf.py --data-dir ./data --output-dir ./models

# Demo mode (synthetic data, no labeling needed):
python train_rf.py
```

Model is automatically copied to `backend/models/rf_change_detector.pkl`.

### Train Siamese ResNet-18 (Google Colab recommended)

```bash
# On Colab (T4 GPU):
python train_siamese.py --data-dir ./data --output-dir ./models --epochs 30
```

---

## Project Structure

```
terradelta/
├── backend/
│   ├── main.py                  # FastAPI application
│   ├── routers/                 # API route handlers
│   │   ├── analysis.py          # F1: Change Analysis
│   │   ├── explorer.py          # F2: Change Explorer
│   │   └── monitoring.py        # F3: Area Monitoring
│   ├── pipeline/                # ML pipeline stages
│   │   ├── data_access.py       # Sentinel-2 data fetch (CDSE)
│   │   ├── preprocessing.py     # Band prep, indices
│   │   ├── features.py          # Feature engineering
│   │   ├── inference.py         # RF + Siamese inference
│   │   ├── postprocessing.py    # Threshold, morphology, vectorize
│   │   ├── filtering.py         # Human-change filter + interpretation
│   │   ├── statistics.py        # Statistics computation
│   │   └── orchestrator.py      # Full pipeline coordinator
│   ├── models/                  # Trained model files (.pkl, .pt)
│   ├── reports/                 # PDF generation
│   ├── db/                      # SQLite + SQLAlchemy
│   └── tests/                   # Pytest test suite
├── frontend/
│   └── src/
│       ├── pages/               # ChangeAnalysis, ChangeExplorer, AreaMonitoring
│       ├── components/          # Map, panels, shared UI
│       ├── services/api.js      # All backend API calls
│       └── store/               # Zustand state
└── ml/
    ├── train_rf.py              # RF training script
    ├── train_siamese.py         # Siamese ResNet-18 training
    └── prepare_data.py          # Feature extraction from raw imagery
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/analysis/submit` | POST | Submit change analysis job |
| `/api/analysis/status/{id}` | GET | Poll job status |
| `/api/analysis/result/{id}` | GET | Fetch results |
| `/api/analysis/download/report/{id}` | GET | Download PDF |
| `/api/explorer/locations` | GET | List Explorer locations |
| `/api/explorer/location/{id}` | GET | Full location data + reveal |
| `/api/monitoring/submit` | POST | Submit multi-date monitoring |
| `/api/monitoring/status/{id}` | GET | Poll status |
| `/api/monitoring/result/{id}` | GET | Timeline results |
| `/health` | GET | Health check |
| `/docs` | GET | OpenAPI documentation |

---

## Data Source

Primary: **ESA Copernicus Sentinel-2 L2A**
- 10 m / 20 m resolution, 13 bands
- Free access via [CDSE](https://dataspace.copernicus.eu)
- Archive from 2015 to present
- No API key required (free registration)

In demo mode (no CDSE credentials): synthetic Sentinel-2-like data is generated
with realistic spectral properties and simulated urban change.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Leaflet + Tailwind + Zustand |
| Backend | FastAPI + Uvicorn + SQLAlchemy |
| ML | scikit-learn (RF) + PyTorch (Siamese) |
| Raster ops | Rasterio + NumPy + OpenCV + scikit-image |
| Vector ops | GeoPandas + Shapely |
| Reports | ReportLab |
| Database | SQLite (MVP) |
| Deployment | Docker Compose |

---

## Limitations

- Sentinel-2 at 10 m/px: objects < 30 m are unreliably detected
- Demo mode uses synthetic data; real CDSE imagery requires free account + credentials
- Single job queue in MVP; multiple concurrent users will queue
- Max AOI: ~100 km² (1° × 1°) in MVP
- Seasonal agricultural changes may occasionally appear as false positives

---

## Team Responsibilities

| Role | Tasks |
|---|---|
| ML Engineer | Data labeling, RF/Siamese training, evaluation, filtering |
| Backend Engineer | FastAPI, CDSE integration, pipeline, PDF, deployment |
| Frontend Engineer | React/Leaflet, all pages, map tools, result rendering |
| Integration | Glue code, Explorer data, demo prep, documentation |

---

*Data: ESA Copernicus Sentinel-2 (free, open access)*
*Platform: TerraDelta — ISRO Capstone Project*
