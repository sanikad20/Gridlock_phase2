# 🚦 Gridlock — Event-Driven Congestion Forecaster

**Flipkart Gridlock Hackathon 2.0**
Digital Twin + Memory Engine for traffic police resource planning.

## 🚀 Live Demo

### Dashboard
https://gridlock-dashboard-xwmt.onrender.com/

### API Base URL
https://gridlock-api-xwmt.onrender.com

### Health Check
https://gridlock-api-xwmt.onrender.com/health

### API Documentation (Swagger)
https://gridlock-api-xwmt.onrender.com/docs


> Hosted on Render's free tier — both services spin down after 15 minutes
> of inactivity and take ~30–60s to wake on the first request after idle.
> If the dashboard looks slow to respond on first load, that's why.

---

## What it does

Given a traffic-affecting event (accident, procession, protest, road closure,
etc.), Gridlock predicts how severe the resulting congestion will be, how
long it will take to clear, and what resources (officers, barricades,
diversions) should be deployed — then lets a planner simulate "what-if"
interventions before committing resources on the ground.

| Module | Purpose |
|---|---|
| **Congestion Prediction** | Classifies severity (Quick / Moderate / Severe) and predicts delay in minutes for a new event |
| **Digital Twin Simulator** | Post-hoc what-if simulation: extra barricades, road closure, crowd-size multiplier — shows 3 scenarios and recommends the best one |
| **Explainable AI panel** | Plain-language reasons behind each prediction (peak hour, high-risk corridor, event cause, etc.) |
| **Corridor Risk / Zone Health** | Ranked risk scores for known high-incident corridors and zones, from historical density |
| **Memory Engine** | Looks up similar past events and what response plan worked, with the resulting delay reduction |
| **Outcome Logging** | Closes the loop — log what actually happened after an incident, building the dataset for future similar-event lookups |

---

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  Streamlit Dashboard │ ──────▶ │   FastAPI Backend     │
│  (gridlock-dashboard)│  HTTPS  │   (gridlock-api)      │
└─────────────────────┘         └──────────┬───────────┘
                                            │
                                  ┌─────────┴─────────┐
                                  │   SQLite (events,  │
                                  │   outcomes)         │
                                  └─────────┬─────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │  Trained model artifacts    │
                              │  (CatBoost classifier +     │
                              │  regressor + LGBM/RF         │
                              │  ensemble, target encoders) │
                              └─────────────────────────────┘
```

Two independently deployed services (see `render.yaml`):
- **`gridlock-api`** — FastAPI backend serving predictions and simulations
- **`gridlock-dashboard`** — Streamlit frontend, calls the API over HTTPS

---

## Repo structure

```
gridlock/
├── render.yaml              ← one-click deploy blueprint (Render)
├── README.md
├── train/
│   ├── train.py              ← full model training pipeline (see below)
│   └── requirements.txt      ← training-only deps
├── api/
│   ├── main.py                ← FastAPI app, all endpoints
│   ├── seed_demo_data.py      ← optional demo data seeder
│   ├── requirements.txt       ← production API deps
│   └── models/                ← trained artifacts (output of train.py)
│       ├── classifier.pkl
│       ├── regressor.pkl
│       ├── ensemble.pkl
│       ├── label_encoders.pkl
│       ├── kmeans_geo.pkl
│       ├── geo_fill.pkl
│       ├── features.json
│       └── target_encoding_maps.json
└── streamlit_app/
    ├── app.py                 ← dashboard UI
    └── requirements.txt
```

---

## Modeling approach (`train/train.py`)

**Target:** real incident resolution time (`closed_datetime − start_datetime`),
not a synthetic label — binned into Quick (<30 min) / Moderate (30–120 min) /
Severe (>120 min). Only events with a real closure timestamp are used, so
the target has genuine ground truth rather than formula-derived leakage.

**Features (25 total):**
- 7 base categorical encodings (event cause, zone, vehicle type, corridor, event type, priority, road closure)
- 5 temporal (hour, day of week, month, is-peak-hour, is-weekend)
- 3 spatial: raw lat/lon **and** a 20-cluster KMeans geo-cluster, used together
- 3 location encodings (police station, junction, junction-is-null)
- 4 single-column target encodings (cause, zone, police station, geo-cluster), 5-fold leak-free with Bayesian smoothing
- 3 interaction target encodings (cause×zone, cause×police-station, cause×hour) — captures combinations like "protest in Central Zone 2" being riskier than either factor alone

**Models trained:**
1. **CatBoost Classifier** (primary) — handles categoricals natively, class-weighted to boost the minority "Quick" class
2. **LightGBM Classifier** — gradient boosting baseline/ensemble member
3. **Random Forest Classifier** — ensemble member
4. **CatBoost Regressor** — predicts duration directly in minutes, then bins to a class; avoids forcing the model to learn hard class boundaries up front
5. **Ensemble** — majority vote across all four

Validated with stratified 5-fold cross-validation. Full console output
(class distributions, per-model accuracy, classification report, feature
importances) is printed during training — see `train/train.py` for the
exact numbers from the run that produced the deployed `models/` artifacts.

**To retrain:**
```bash
cd train
pip install -r requirements.txt
# point CSV in train.py to your dataset path, then:
python train.py
# copy the resulting train/models/*.pkl and *.json into api/models/
```

---

## API endpoints (`api/main.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service + model status |
| `/predict-event` | POST | Predict severity/delay, no logging |
| `/predict-and-log` | POST | Predict + persist event to DB, returns `event_id` |
| `/predict-ensemble` | POST | Run all 4 models, return individual votes + majority |
| `/digital-twin` | POST | What-if simulation (extra barricades / road closure / attendance multiplier) — clearly labeled as a post-hoc heuristic adjustment, not a separate model |
| `/similar-events` | POST | Look up recent similar events and their logged outcomes |
| `/log-outcome` | POST | Record actual severity/delay/plan-used for a logged event |
| `/corridor-risk` | GET | Ranked corridor risk scores |
| `/zone-health` | GET | Ranked zone risk scores |
| `/map-data/{event_id}` | GET | Lat/lon + severity for map rendering |
| `/resources` | GET | Resource table lookup by severity level |

Interactive docs: `/docs` (Swagger UI, auto-generated by FastAPI).

---

## Running locally

```bash
# Terminal 1 — API
cd api
pip install -r requirements.txt
uvicorn main:app --reload
# → http://127.0.0.1:8000

# Terminal 2 — Dashboard
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
# → http://localhost:8501  (defaults to calling the local API)
```

Optional: seed 5 demo events with logged outcomes for the Memory Engine panel:
```bash
cd api
python seed_demo_data.py
```

---

## Deploying your own copy (Render, free tier)

1. Push this repo to GitHub.
2. Render Dashboard → **New** → **Blueprint** → connect the repo.
3. Render reads `render.yaml` and proposes two services — click **Apply**.
4. Once both show **Live**, open the `gridlock-dashboard` service's URL — wired to its API automatically via the `API_URL` environment variable.

Free-tier note: SQLite storage is **ephemeral** on Render's free plan — data
resets on redeploy or after extended inactivity. Fine for demoing; for a
persistent deployment, add a Render Disk or move to Postgres.

---

## Known limitations / honest notes

- Free-tier cold starts (~30–60s) on first request after idling.
- SQLite on free tier doesn't persist across redeploys (see above).
- The Digital Twin is a **labeled heuristic adjustment** (barricades reduce
  delay ~5% each, road closure adds ~35%, attendance multiplier scales
  delay), not a separately trained causal model — this is intentional and
  stated in every API response (`simulation_note` field) so it's never
  confused with a genuine model prediction.
- `confidence` in `/predict-and-log` is the classifier's max predicted
  probability, not a calibrated confidence interval.
