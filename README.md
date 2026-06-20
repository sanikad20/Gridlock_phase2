# Gridlock — Deployment Guide (Render, free tier)

# Gridlock — Deployment Guide (Render, free tier)

## 0. Status: models included and tested ✅
`api/models/` already contains your trained artifacts (classifier.pkl,
regressor.pkl, ensemble.pkl, label_encoders.pkl, kmeans_geo.pkl, geo_fill.pkl,
features.json, target_encoding_maps.json — 11MB total, no Git LFS needed).

This was verified end-to-end against your real CatBoost classifier/regressor
and LightGBM+CatBoost+RandomForest ensemble before packaging:
- `/health` ✅
- `/predict-and-log` ✅ (real prediction: Moderate, 74.8 min, correct explanation)
- `/digital-twin` ✅ (3 scenarios computed correctly)
- `/predict-ensemble` ✅ (all 4 models voted, returned individual votes)
- `/corridor-risk`, `/zone-health` ✅
- `/similar-events` ✅ (tested against seeded demo data)
- `seed_demo_data.py` ✅ (fixed indentation bug, runs cleanly)

`api/requirements.txt` pins `scikit-learn==1.4.2` to match the version your
`.pkl` files were trained with (avoids version-mismatch warnings in prod).
Both `lightgbm` and `catboost` are kept since `ensemble.pkl` uses both.

Note: `congestion_classifier.pkl` and `lgbm_congestion.pkl` from your upload
were standalone extras not referenced by `main.py` (which only loads
`classifier.pkl`, `regressor.pkl`, and `ensemble.pkl`), so they were left out
of the deployment package to keep things lean. Say the word if you actually
need them wired in somewhere.

## 1. Push to GitHub
```bash
cd gridlock
git init
git add .
git commit -m "Gridlock hackathon app"
git branch -M main
git remote add origin https://github.com/<you>/gridlock.git
git push -u origin main
```
(Model `.pkl` files are usually small enough for normal git; if any single
file is over 100MB, use Git LFS — `git lfs track "*.pkl"` before committing.)

## 2. Deploy on Render
1. Go to https://dashboard.render.com → **New** → **Blueprint**.
2. Connect your GitHub repo. Render auto-detects `render.yaml` at the repo
   root and proposes two services:
   - `gridlock-api` (FastAPI, port from `$PORT`)
   - `gridlock-dashboard` (Streamlit, port from `$PORT`, with `API_URL`
     wired automatically to the API service's internal host:port)
3. Click **Apply**. Both services build and deploy on the free plan.
4. Once live, open the `gridlock-dashboard` URL Render gives you — that's
   your public app. The API itself is reachable at the `gridlock-api` URL
   (try `/health` to confirm it's up).

## 3. Seed demo data (optional, one-time)
Render's free-tier filesystem is ephemeral — anything written to disk
(including `gridlock_memory.db`) is wiped on every redeploy or restart
after idling. Two options:

- **Quick demo only**: open the Render Shell for `gridlock-api`
  (Dashboard → service → Shell tab) and run:
  ```bash
  python seed_demo_data.py
  ```
  Fine for a hackathon demo, but data disappears next time the free
  instance spins down and back up.
- **Persistent data**: upgrade `gridlock-api` to a paid plan with a
  Render Disk mounted at the API's working directory, or swap SQLite
  for Render's free Postgres tier. Not required to demo the app.

## 4. Free-tier behavior to expect
- Both services **spin down after 15 minutes of inactivity** and take
  ~30–60s to wake on the next request — the first prediction after idle
  will feel slow. This is normal for Render's free plan, not a bug.
- 750 free instance-hours/month total, shared across your free services.

## Local testing before you deploy
```bash
# Terminal 1
cd api
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
# API_URL env var not set locally -> defaults to http://127.0.0.1:8000
```
