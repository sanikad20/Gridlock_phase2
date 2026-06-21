# 🚦 Gridlock — Event-Driven Congestion Forecaster

**Flipkart Gridlock Hackathon 2.0  — Round 2 Prototype**

**Team:** Genai
**Team Leader:** Sanika Deshmukh — [@sanikad20](https://github.com/sanikad20)
**Team Members:** Pragati Kharat — [@pragatikharat17](https://github.com/pragatikharat17), Divya Addagatla — [@adivya15](https://github.com/adivya15)

---

## Problem Statement

**Theme:** Event-Driven Congestion (Planned & Unplanned)

**Operational Challenge:** Political rallies, festivals, sports events, construction activities, and sudden gatherings create localized traffic breakdowns.

**Why It's Hard Today:**
- Event impact is not quantified in advance.
- Resource deployment is experience-driven.
- No post-event learning system.

**Problem Statement Direction:** How can historical and real-time data be used to forecast event-related traffic impact and recommend optimal manpower, barricading, and diversion plans?

---

## Our Solution

Gridlock takes any traffic-affecting event — planned or unplanned — and turns it into a data-backed action plan in seconds. It predicts how severe the congestion will be and how long it'll take to clear, recommends exact officer/barricade/diversion counts, lets operators simulate "what-if" interventions before committing resources, and pulls up what actually worked in similar past incidents. Every outcome operators log feeds back in, so the system gets sharper with every incident it sees — closing the loop that's currently missing in manual, experience-driven deployment.

---

AI-powered traffic congestion prediction, digital twin simulation, and memory-driven resource planning for Bengaluru Traffic Police.

---

## 🌐 Live Demo

| Service | URL |
|---|---|
| **Dashboard** | https://gridlock-dashboard-xwmt.onrender.com |
| **API** | https://gridlock-api-xwmt.onrender.com |
| **API Docs (Swagger)** | https://gridlock-api-xwmt.onrender.com/docs |
| **Health Check** | https://gridlock-api-xwmt.onrender.com/health |

> Hosted on Render free tier — services spin down after 15 min inactivity. First request after idle may take 30–60s to wake.

---

## What It Does

Given a traffic-affecting event (accident, procession, protest, road closure, etc.), Gridlock:

1. **Predicts** severity (Quick / Moderate / Severe) and expected delay in minutes
2. **Recommends** exact officer, barricade, and diversion counts
3. **Simulates** what-if interventions via Digital Twin before deploying resources
4. **Retrieves** similar past events and what response plan worked (Memory Engine)
5. **Learns** — operators log actual outcomes, improving future recommendations
6. **Explains** predictions in plain language (peak hour, high-risk corridor, etc.)

| Module | Purpose |
|---|---|
| **Congestion Prediction** | ML ensemble classifies Quick / Moderate / Severe + predicts delay minutes |
| **Digital Twin Simulator** | What-if: extra barricades, road closure, attendance multiplier → 3 scenarios |
| **Memory Engine** | Cosine-similarity search over past events — retrieves what plan worked and delay reduction % |
| **AI Operations Assistant** | Groq Llama 3.3 70B chat — ask about prediction, deployment strategy, or past incidents |
| **Live Operations Feed** | Real-time table of recent incidents with status (Active / Resolved) |
| **KPI Summary** | Active incidents, severe predictions, avg delay, high-risk zones — last 24 hours |
| **Corridor Risk Ranking** | Ranked risk scores from historical Astram incident density |
| **Zone Health Dashboard** | Risk scores per zone with trend indicators |
| **Explainability Panel** | Plain-language reasons behind each prediction |
| **Outcome Logging** | Close the loop — log actual severity and plan used after the incident |

---

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  Streamlit Dashboard │ ──────▶ │   FastAPI Backend     │
│  (app.py)            │  HTTPS  │   (main.py)           │
│  + chat_utils.py     │         └──────────┬────────────┘
└─────────────────────┘                     │
                                  ┌──────────┴──────────┐
                                  │  SQLite              │
                                  │  events + outcomes   │
                                  └──────────┬──────────┘
                                             │
                              ┌──────────────┴──────────────┐
                              │  Model artifacts (api/models/)│
                              │  CatBoost + LightGBM + RF +  │
                              │  regressor, target encoders, │
                              │  KMeans geo-cluster          │
                              └──────────────────────────────┘
                                             │
                                  ┌──────────┴──────────┐
                                  │  Groq API            │
                                  │  (Llama 3.3 70B)     │
                                  │  AI chat assistant   │
                                  └─────────────────────┘
```

Two deployed services on Render:
- **`gridlock-api`** — FastAPI serving all prediction, simulation, and memory endpoints
- **`gridlock-dashboard`** — Streamlit UI calling the API over HTTPS

---

## Repo Structure

```
gridlock/
├── render.yaml                  ← one-click Render deploy blueprint
├── README.md
├── .env.example                 ← set GROQ_API_KEY here
├── train/
│   ├── train.py                  ← full model training pipeline
│   └── requirements.txt
├── api/
│   ├── main.py                    ← FastAPI app (v3.2), all endpoints
│   ├── chat_utils.py              ← Groq Llama 3.3 70B chat integration
│   ├── seed_demo_data.py          ← seeds 5 demo events with outcomes
│   ├── requirements.txt
│   └── models/                    ← trained artifacts (output of train.py)
│       ├── classifier.pkl          ← CatBoost (primary model)
│       ├── regressor.pkl           ← duration regressor → delay minutes
│       ├── ensemble.pkl            ← CatBoost + LightGBM + RF + regressor
│       ├── label_encoders.pkl      ← cause / zone / veh / corr / ps / junc
│       ├── kmeans_geo.pkl          ← 20-cluster spatial encoder
│       ├── geo_fill.pkl            ← lat/lon medians for missing values
│       ├── features.json           ← ordered feature list (25 features)
│       └── target_encoding_maps.json ← OOF-safe target encoding lookup tables
└── streamlit_app/
    ├── app.py                     ← dashboard (dark theme, full UI)
    ├── chat_utils.py              ← copy of api/chat_utils.py
    └── requirements.txt
```

---

## Modeling Approach

**Training data:** Astram event dataset — 8,173 real Bengaluru traffic incidents

**Target (real ground truth, not synthetic):**
Actual incident resolution time `closed_datetime − start_datetime`, binned into:
- `Quick` — < 30 min
- `Moderate` — 30–120 min
- `Severe` — > 120 min

Only events with a real closure timestamp are used (2,467 rows). No formula-derived label leakage.

**Features (25 total):**

| Group | Features |
|---|---|
| Base encodings (7) | event_cause, zone, vehicle_type, corridor, event_type, priority, road_closure |
| Temporal (5) | hour, day_of_week, month, is_peak_hour, is_weekend |
| Spatial (3) | latitude, longitude, KMeans geo_cluster (20 clusters) |
| Location (3) | police_station_enc, junction_enc, junction_is_null |
| Single target encodings (4) | cause_te, zone_te, ps_te, geo_te — OOF, Bayesian smoothed |
| Interaction target encodings (3) | cause×zone, cause×police_station, cause×hour |

**Models:**
1. **CatBoost Classifier** (primary) — class-weighted, handles categoricals natively
2. **LightGBM Classifier** — ensemble member
3. **Random Forest Classifier** — ensemble member
4. **CatBoost Regressor** — predicts duration directly in minutes, then bins to class
5. **Ensemble** — majority vote across all four

**Validation:** 5-fold stratified cross-validation throughout. OOF target encodings computed per fold. Train/OOF accuracy gap ≤ 0.05 (no overfitting).

**To retrain:**
```bash
cd train
pip install -r requirements.txt
# update CSV path in train.py, then:
python train.py
cp train/models/*.pkl api/models/
cp train/models/*.json api/models/
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service + model status |
| `/predict-event` | POST | Predict severity/delay, no logging |
| `/predict-and-log` | POST | Predict + persist to DB, returns `event_id` |
| `/predict-ensemble` | POST | Run all 4 models, return individual votes + majority |
| `/digital-twin` | POST | What-if simulation — 3 scenarios, clearly labeled heuristic |
| `/similar-events` | POST | Cosine-similarity search over past events + outcomes |
| `/log-outcome` | POST | Record actual severity/delay/plan after incident |
| `/corridor-risk` | GET | Ranked corridor risk scores |
| `/zone-health` | GET | Ranked zone risk scores |
| `/live-feed` | GET | Most recent N incidents with Active/Resolved status |
| `/kpi-summary` | GET | Aggregate KPIs — last 24 hours |
| `/map-data/{event_id}` | GET | Lat/lon + severity + radius for map rendering |
| `/resources` | GET | Resource table lookup by severity |

Full interactive docs at `/docs` (Swagger UI, auto-generated by FastAPI).

---

## AI Operations Assistant

Powered by **Groq Llama 3.3 70B** via the Groq API.

The assistant is embedded in the dashboard and has access to the current event context (cause, zone, corridor, predicted severity, delay, explanation factors). It can answer questions like:
- "Why was this predicted as Severe?"
- "How many officers should I deploy?"
- "Have we seen similar incidents on this corridor before?"

**Setup:**
```bash
# Create .env in project root:
GROQ_API_KEY=your_key_here

# Or export directly:
export GROQ_API_KEY=your_key_here
```

Get a free API key at https://console.groq.com

---

## Running Locally

```bash
# Terminal 1 — API
cd api
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here   # optional, for AI assistant
uvicorn main:app --reload
# → http://127.0.0.1:8000

# Terminal 2 — Dashboard
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
# → http://localhost:8501
```

Seed 5 demo events with logged outcomes for the Memory Engine:
```bash
cd api
python seed_demo_data.py
```

---

## Deploy Your Own Copy (Render)

1. Push repo to GitHub
2. Render Dashboard → **New** → **Blueprint** → connect repo
3. Render reads `render.yaml` and proposes two services — click **Apply**
4. Add `GROQ_API_KEY` as an environment variable in the dashboard service settings
5. Both services go live — dashboard is wired to API via `API_URL` env var automatically

> **Free-tier note:** SQLite is ephemeral on Render's free plan — resets on redeploy or extended inactivity. Fine for demo. For persistence, add a Render Disk or migrate to Postgres.

---

## Event Type / Cause Validation

The API enforces valid event type + cause combinations:

| Planned causes | Unplanned causes |
|---|---|
| public_event, procession, vip_movement, construction, test_demo | accident, vehicle_breakdown, tree_fall, water_logging, debris, congestion, pot_holes, road_conditions |

Invalid combinations return HTTP 400 with a clear error message.

---

## Honest Notes

- **Digital Twin is a labeled heuristic**, not a causal model. Each API response includes a `simulation_note` field stating this explicitly. Barricades reduce delay ~5% each, road closure adds ~35%, attendance multiplier scales linearly.
- **62% OOF accuracy** on a balanced 3-class problem where random baseline is 33%. Real ground truth, no leakage.
- **`confidence`** is the classifier's max predicted probability — not a calibrated confidence interval.
- **Memory Engine** uses cosine similarity over 9-dimensional event vectors (cause severity, priority, road closure, hour, day, month, weekend flag, peak-hour flag, event type). Returns top-k matches with similarity score (%).
- **Cold starts** on free tier: ~30–60s after 15 min idle.
