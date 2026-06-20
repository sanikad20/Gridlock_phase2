"""
Gridlock Hackathon 2.0 — api/main.py (UPDATED v3)
===================================================
New in this version:
  - /similar-events now returns a similarity_score (cosine-like match %)
  - /live-feed endpoint — recent events for the Live Operations Feed
  - /kpi-summary endpoint — aggregate stats for KPI cards
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import joblib, json, sqlite3, uuid, os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

app = FastAPI(title="Gridlock Congestion API", version="3.0")

# ══════════════════════════════════════════════
# LOAD MODEL ARTIFACTS
# ══════════════════════════════════════════════
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DB_PATH    = os.path.join(BASE_DIR, "gridlock_memory.db")

classifier = joblib.load(os.path.join(MODELS_DIR, "classifier.pkl"))
regressor  = joblib.load(os.path.join(MODELS_DIR, "regressor.pkl"))
le         = joblib.load(os.path.join(MODELS_DIR, "label_encoders.pkl"))
kmeans_geo = joblib.load(os.path.join(MODELS_DIR, "kmeans_geo.pkl"))
geo_fill   = joblib.load(os.path.join(MODELS_DIR, "geo_fill.pkl"))

with open(os.path.join(MODELS_DIR, "features.json")) as f:
    FEATURES = json.load(f)

with open(os.path.join(MODELS_DIR, "target_encoding_maps.json")) as f:
    TE_MAPS = json.load(f)

try:
    ensemble_models = joblib.load(os.path.join(MODELS_DIR, "ensemble.pkl"))
    HAS_ENSEMBLE = True
except FileNotFoundError:
    ensemble_models = {}
    HAS_ENSEMBLE = False

SEVERITY_LABEL = {0: "Quick", 1: "Moderate", 2: "Severe"}

RECOMMENDATION = {
    "Severe":   "Deploy 8+ officers, 4+ barricades. Activate diversion via alternate road immediately.",
    "Moderate": "Deploy 4-6 officers, 2-3 barricades. Monitor every 15 mins.",
    "Quick":    "Deploy 1-2 officers. Minimal barricades. Standard monitoring.",
}

RESOURCE_TABLE = {
    "Severe":   {"officers": 12, "barricades": 6, "diversions": 2},
    "Moderate": {"officers": 6,  "barricades": 3, "diversions": 1},
    "Quick":    {"officers": 2,  "barricades": 1, "diversions": 0},
}

CLEARANCE_MINS = {"Severe": 120, "Moderate": 60, "Quick": 20}

CORRIDOR_RISK = {
    "ORR East 1": 89, "Tumkur Road": 84, "Bellary Road 1": 79, "Mysore Road": 74,
    "Hosur Road": 68, "Old Madras Road": 61, "Bellary Road 2": 57,
    "ORR North 1": 52, "Magadi Road": 45, "Non-corridor": 32,
}

ZONE_RISK = {
    "Central Zone 2": 82, "North Zone 1": 76, "South Zone 1": 71,
    "Central Zone 1": 68, "East Zone 1": 63, "South Zone 2": 57,
    "North Zone 2": 52, "West Zone 1": 44, "East Zone 2": 41, "West Zone 2": 35,
}

HIGH_RISK_CORRIDORS = ["ORR East 1", "Tumkur Road", "Bellary Road 1", "Mysore Road"]
HIGH_RISK_CAUSES    = ["accident", "congestion", "protest", "procession", "vip_movement"]
HIGH_RISK_ZONES     = ["Central Zone 2", "North Zone 1", "South Zone 1"]

# ══════════════════════════════════════════════
# DB INIT
# ══════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS events (
        id                    TEXT PRIMARY KEY,
        event_type            TEXT,
        event_cause           TEXT,
        latitude              REAL,
        longitude             REAL,
        zone                  TEXT,
        corridor              TEXT,
        priority              TEXT,
        requires_road_closure INTEGER,
        veh_type              TEXT,
        police_station        TEXT,
        junction              TEXT,
        hour                  INTEGER,
        day_of_week           INTEGER,
        month                 INTEGER,
        pred_severity         TEXT,
        pred_delay_mins       REAL,
        created_at            TEXT
    );
    CREATE TABLE IF NOT EXISTS outcomes (
        id                  TEXT PRIMARY KEY,
        event_id            TEXT REFERENCES events(id),
        actual_severity     TEXT,
        actual_delay_mins   REAL,
        officers_deployed   INTEGER,
        barricades_used     INTEGER,
        delay_reduced_pct   REAL,
        plan_used           TEXT,
        notes               TEXT,
        logged_at           TEXT
    );
    """)
    conn.commit()
    conn.close()

init_db()

# ══════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════
class EventInput(BaseModel):
    event_type            : str
    event_cause            : str
    priority               : str
    requires_road_closure  : bool
    latitude                : float
    longitude                : float
    zone                      : str
    corridor                   : Optional[str] = "Non-corridor"
    veh_type                    : Optional[str] = "none"
    police_station                : Optional[str] = "Unknown"
    junction                       : Optional[str] = None
    hour                             : int
    day_of_week                       : int
    month                               : int

class OutcomeInput(BaseModel):
    event_id          : str
    actual_severity    : str
    actual_delay_mins   : float
    officers_deployed    : int
    barricades_used        : int
    delay_reduced_pct       : float = 0.0
    plan_used                : str
    notes                      : Optional[str] = ""

class DigitalTwinInput(BaseModel):
    event_type            : str
    event_cause            : str
    priority                : str
    requires_road_closure    : bool
    latitude                  : float
    longitude                  : float
    zone                        : str
    corridor                     : Optional[str] = "Non-corridor"
    veh_type                      : Optional[str] = "none"
    police_station                  : Optional[str] = "Unknown"
    junction                         : Optional[str] = None
    hour                               : int
    day_of_week                         : int
    month                                 : int
    extra_barricades                       : int   = 0
    close_main_road                         : bool  = False
    attendance_multiplier                    : float = 1.0

# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════
def safe_label_encode(encoder, value, fallback_value=0):
    try:
        return int(encoder.transform([value])[0])
    except ValueError:
        return 0

def te_lookup(group_key: str, raw_key: str) -> float:
    entry = TE_MAPS[group_key]
    val   = entry["map"].get(raw_key)
    return float(val) if val is not None else float(entry["global"])

def build_feature_row(e: EventInput) -> pd.DataFrame:
    is_peak    = 1 if e.hour in [8, 9, 10, 17, 18, 19] else 0
    is_weekend = 1 if e.day_of_week >= 5 else 0

    lat = e.latitude  if e.latitude  is not None else geo_fill["lat_med"]
    lon = e.longitude if e.longitude is not None else geo_fill["lon_med"]
    geo_cluster = int(kmeans_geo.predict([[lat, lon]])[0])

    junction_is_null = 1 if not e.junction else 0
    junction_val     = e.junction if e.junction else "__null__"

    event_cause_enc    = safe_label_encode(le["cause"], e.event_cause)
    zone_enc           = safe_label_encode(le["zone"],  e.zone)
    veh_type_enc       = safe_label_encode(le["veh"],   e.veh_type or "none")
    corridor_enc       = safe_label_encode(le["corr"],  e.corridor or "Non-corridor")
    police_station_enc = safe_label_encode(le["ps"],    e.police_station or "Unknown")
    junction_enc       = safe_label_encode(le["junc"],  junction_val)

    event_type_enc   = 1 if e.event_type == "planned" else 0
    priority_enc     = 2 if e.priority == "High" else 1
    road_closure_enc = int(e.requires_road_closure)

    cause_zone_key  = f"{e.event_cause}_{e.zone}"
    cause_ps_key    = f"{e.event_cause}_{e.police_station or 'Unknown'}"
    cause_hour_key  = f"{e.event_cause}_{e.hour}"

    row = {
        "event_cause_enc"   : event_cause_enc,
        "zone_enc"          : zone_enc,
        "veh_type_enc"      : veh_type_enc,
        "corridor_enc"      : corridor_enc,
        "event_type_enc"    : event_type_enc,
        "priority_enc"      : priority_enc,
        "road_closure_enc"  : road_closure_enc,
        "hour"              : e.hour,
        "day_of_week"       : e.day_of_week,
        "month"             : e.month,
        "is_peak_hour"      : is_peak,
        "is_weekend"        : is_weekend,
        "latitude"          : lat,
        "longitude"         : lon,
        "geo_cluster"       : geo_cluster,
        "police_station_enc": police_station_enc,
        "junction_enc"      : junction_enc,
        "junction_is_null"  : junction_is_null,
        "cause_te"          : te_lookup("cause",      e.event_cause),
        "zone_te"           : te_lookup("zone",       e.zone),
        "ps_te"             : te_lookup("ps",         e.police_station or "Unknown"),
        "geo_te"            : te_lookup("geo",        str(geo_cluster)),
        "cause_zone_te"     : te_lookup("cause_zone", cause_zone_key),
        "cause_ps_te"       : te_lookup("cause_ps",   cause_ps_key),
        "cause_hour_te"     : te_lookup("cause_hour", cause_hour_key),
    }
    return pd.DataFrame([row])[FEATURES]

def get_explanation(e: EventInput, severity: str) -> list:
    reasons = []
    if e.hour in [8, 9, 10, 17, 18, 19]:
        reasons.append("✓ Peak Hour — traffic spike expected")
    if e.corridor in HIGH_RISK_CORRIDORS:
        reasons.append(f"✓ High Risk Corridor — {e.corridor} has high incident density")
    if e.event_cause in HIGH_RISK_CAUSES:
        reasons.append(f"✓ High Severity Cause — {e.event_cause} historically causes long delays")
    if e.requires_road_closure:
        reasons.append("✓ Road Closure Required — diverts all traffic")
    if e.priority == "High":
        reasons.append("✓ High Priority Incident")
    if e.zone in HIGH_RISK_ZONES:
        reasons.append(f"✓ High Risk Zone — {e.zone} has elevated incident density")
    if e.day_of_week >= 5:
        reasons.append("✓ Weekend — higher incident density historically")
    if not reasons:
        reasons.append("✓ Standard incident — low risk factors detected")
    return reasons

def apply_digital_twin_adjustment(base_delay, base_severity, extra_barricades,
                                    close_main_road, attendance_multiplier):
    adjusted_delay = base_delay
    barricade_reduction = extra_barricades * 0.05
    adjusted_delay *= (1 - barricade_reduction)
    if close_main_road:
        adjusted_delay *= 1.35
    if attendance_multiplier > 1:
        adjusted_delay *= (1 + (attendance_multiplier - 1) * 0.20)
    adjusted_delay = max(5.0, adjusted_delay)

    if adjusted_delay < 30:
        adj_severity = "Quick"
    elif adjusted_delay < 120:
        adj_severity = "Moderate"
    else:
        adj_severity = "Severe"

    delay_change = adjusted_delay - base_delay
    pct_change   = (delay_change / base_delay * 100) if base_delay > 0 else 0

    return {
        "adjusted_delay_mins": round(adjusted_delay, 1),
        "adjusted_severity"  : adj_severity,
        "delay_change_mins"  : round(delay_change, 1),
        "delay_change_pct"   : round(pct_change, 1),
        "simulation_note"    : "Post-hoc simulated adjustment — not a model prediction",
        "factors_applied"    : {
            "extra_barricades"     : extra_barricades,
            "close_main_road"      : close_main_road,
            "attendance_multiplier": attendance_multiplier,
        }
    }

def event_to_vector(event: dict) -> np.ndarray:
    """Numeric vector for cosine similarity matching between events."""
    cause_map = {
        'accident': 3, 'congestion': 3, 'vip_movement': 3, 'procession': 3, 'protest': 3,
        'public_event': 2, 'tree_fall': 2, 'water_logging': 2, 'Debris': 2, 'debris': 2,
        'Fog / Low Visibility': 2, 'vehicle_breakdown': 1, 'construction': 1,
        'road_conditions': 1, 'pot_holes': 1, 'others': 1, 'test_demo': 0
    }
    return np.array([
        1 if event.get("event_type") == "unplanned" else 0,
        cause_map.get(event.get("event_cause", "others"), 1),
        2 if event.get("priority") == "High" else 1,
        int(event.get("requires_road_closure", 0)),
        event.get("hour", 0) / 23.0,
        event.get("day_of_week", 0) / 6.0,
        event.get("month", 1) / 12.0,
        1 if event.get("day_of_week", 0) >= 5 else 0,
        1 if event.get("hour", 0) in [8, 9, 10, 17, 18, 19] else 0,
    ], dtype=float)

def cosine_sim(v1: np.ndarray, v2: np.ndarray) -> float:
    norm1, norm2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))

# ══════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "running", "message": "Gridlock Congestion API v3.0", "features": len(FEATURES)}

@app.get("/health")
def health():
    return {
        "status"            : "ok",
        "model"             : type(classifier).__name__,
        "features"          : len(FEATURES),
        "ensemble_available": HAS_ENSEMBLE,
        "timestamp"         : datetime.utcnow().isoformat(),
    }

@app.post("/predict-event")
def predict_event(e: EventInput):
    row       = build_feature_row(e)
    pred_code = int(np.array(classifier.predict(row)).flatten()[0])
    severity  = SEVERITY_LABEL.get(pred_code, "Moderate")
    delay     = float(np.array(regressor.predict(row)).flatten()[0])
    delay     = max(0.0, min(delay, 1440.0))

    confidence = None
    if hasattr(classifier, "predict_proba"):
        try:
            confidence = float(np.array(classifier.predict_proba(row)).max())
        except Exception:
            confidence = None

    return {
        "severity"             : severity,
        "confidence"           : round(confidence, 2) if confidence else None,
        "delay_minutes"        : round(delay, 1),
        "estimated_clearance"  : CLEARANCE_MINS[severity],
        "recommendation"       : RECOMMENDATION[severity],
        "resources"            : RESOURCE_TABLE[severity],
        "explanation"          : get_explanation(e, severity),
        "event_cause"          : e.event_cause,
        "zone"                 : e.zone,
        "corridor"              : e.corridor,
        "is_peak_hour"           : bool(e.hour in [8, 9, 10, 17, 18, 19]),
        "requires_road_closure"   : e.requires_road_closure,
    }

@app.post("/predict-and-log")
def predict_and_log(e: EventInput):
    row       = build_feature_row(e)
    pred_code = int(np.array(classifier.predict(row)).flatten()[0])
    severity  = SEVERITY_LABEL.get(pred_code, "Moderate")
    delay     = float(np.array(regressor.predict(row)).flatten()[0])
    delay     = max(0.0, min(delay, 1440.0))

    confidence = None
    if hasattr(classifier, "predict_proba"):
        try:
            confidence = float(np.array(classifier.predict_proba(row)).max())
        except Exception:
            confidence = None

    event_id = "EV" + uuid.uuid4().hex[:8].upper()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO events (
            id, event_type, event_cause, latitude, longitude, zone, corridor,
            priority, requires_road_closure, veh_type, police_station, junction,
            hour, day_of_week, month, pred_severity, pred_delay_mins, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        event_id, e.event_type, e.event_cause, e.latitude, e.longitude,
        e.zone, e.corridor, e.priority, int(e.requires_road_closure),
        e.veh_type, e.police_station, e.junction, e.hour, e.day_of_week,
        e.month, severity, round(delay, 1), datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "event_id"             : event_id,
        "severity"              : severity,
        "confidence"             : round(confidence, 2) if confidence else None,
        "delay_minutes"           : round(delay, 1),
        "estimated_clearance"      : CLEARANCE_MINS[severity],
        "recommendation"            : RECOMMENDATION[severity],
        "resources"                  : RESOURCE_TABLE[severity],
        "explanation"                 : get_explanation(e, severity),
        "is_peak_hour"                 : bool(e.hour in [8, 9, 10, 17, 18, 19]),
        "requires_road_closure"          : e.requires_road_closure,
    }

@app.post("/digital-twin")
def digital_twin(e: DigitalTwinInput):
    base_event = EventInput(
        event_type=e.event_type, event_cause=e.event_cause,
        priority=e.priority, requires_road_closure=e.requires_road_closure,
        latitude=e.latitude, longitude=e.longitude, zone=e.zone,
        corridor=e.corridor, veh_type=e.veh_type,
        police_station=e.police_station, junction=e.junction,
        hour=e.hour, day_of_week=e.day_of_week, month=e.month
    )
    row       = build_feature_row(base_event)
    pred_code = int(np.array(classifier.predict(row)).flatten()[0])
    severity  = SEVERITY_LABEL.get(pred_code, "Moderate")
    delay     = float(np.array(regressor.predict(row)).flatten()[0])
    delay     = max(5.0, min(delay, 1440.0))

    confidence = None
    if hasattr(classifier, "predict_proba"):
        try:
            confidence = float(np.array(classifier.predict_proba(row)).max())
        except Exception:
            confidence = None

    scenario_a = apply_digital_twin_adjustment(
        delay, severity, e.extra_barricades, False, 1.0)
    scenario_a["scenario"] = f"A — {e.extra_barricades} Extra Barricades Only"

    scenario_b = apply_digital_twin_adjustment(
        delay, severity, 0, e.close_main_road, 1.0)
    scenario_b["scenario"] = "B — Diversion Activated Only"

    scenario_c = apply_digital_twin_adjustment(
        delay, severity, e.extra_barricades, e.close_main_road, e.attendance_multiplier)
    scenario_c["scenario"] = "C — Combined (your settings)"

    scenarios = [scenario_a, scenario_b, scenario_c]
    best = min(scenarios, key=lambda x: x["adjusted_delay_mins"])

    return {
        "baseline": {
            "severity"            : severity,
            "delay_minutes"        : round(delay, 1),
            "confidence"            : round(confidence, 2) if confidence else None,
            "estimated_clearance"    : CLEARANCE_MINS[severity],
            "recommendation"          : RECOMMENDATION[severity],
            "resources"                : RESOURCE_TABLE[severity],
        },
        "scenarios"    : scenarios,
        "best_scenario" : best["scenario"],
        "simulation_note": "Scenarios are post-hoc simulated adjustments, not model predictions."
    }

@app.post("/predict-ensemble")
def predict_ensemble(e: EventInput):
    if not HAS_ENSEMBLE:
        raise HTTPException(400, "Ensemble not found.")
    row, preds, names = build_feature_row(e), [], []

    if "lgbm" in ensemble_models:
        preds.append(int(np.array(ensemble_models["lgbm"].predict(row)).flatten()[0])); names.append("LightGBM")
    if "cat" in ensemble_models:
        preds.append(int(np.array(ensemble_models["cat"].predict(row)).flatten()[0])); names.append("CatBoost")
    if "rf" in ensemble_models:
        preds.append(int(np.array(ensemble_models["rf"].predict(row)).flatten()[0])); names.append("RandomForest")
    if "reg" in ensemble_models:
        delay_pred = float(np.array(ensemble_models["reg"].predict(row)).flatten()[0])
        reg_class  = 0 if delay_pred < 30 else (1 if delay_pred < 120 else 2)
        preds.append(reg_class); names.append("Regressor→Class")

    final_code = int(np.bincount(preds, minlength=3).argmax())
    severity   = SEVERITY_LABEL.get(final_code, "Moderate")
    delay      = float(np.array(regressor.predict(row)).flatten()[0])

    return {
        "severity"         : severity,
        "delay_minutes"     : round(delay, 1),
        "recommendation"     : RECOMMENDATION[severity],
        "resources"            : RESOURCE_TABLE[severity],
        "individual_votes"      : dict(zip(names, [SEVERITY_LABEL[p] for p in preds])),
        "models_used"             : names,
    }

@app.post("/log-outcome")
def log_outcome(o: OutcomeInput):
    conn   = sqlite3.connect(DB_PATH)
    exists = conn.execute("SELECT 1 FROM events WHERE id=?", (o.event_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(404, f"Event {o.event_id} not found.")

    oid = "OUT" + uuid.uuid4().hex[:8].upper()
    conn.execute("""
        INSERT INTO outcomes (
            id, event_id, actual_severity, actual_delay_mins,
            officers_deployed, barricades_used, delay_reduced_pct,
            plan_used, notes, logged_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        oid, o.event_id, o.actual_severity, o.actual_delay_mins,
        o.officers_deployed, o.barricades_used, o.delay_reduced_pct,
        o.plan_used, o.notes, datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "status"    : "logged",
        "event_id"  : o.event_id,
        "outcome_id": oid,
        "message"   : f"Plan '{o.plan_used}' reduced delay by {o.delay_reduced_pct}%",
    }

@app.post("/similar-events")
def similar_events(e: EventInput, top_k: int = 3):
    """
    Returns top-k similar past events ranked by cosine similarity score (%).
    Falls back across same-cause matches first, then broadens to all events
    if too few same-cause matches exist, so the panel is never empty.
    """
    query_vec = event_to_vector(e.dict())

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT ev.id, ev.event_type, ev.event_cause, ev.zone, ev.corridor,
               ev.priority, ev.requires_road_closure, ev.hour, ev.day_of_week, ev.month,
               ev.pred_severity, ev.pred_delay_mins, ev.created_at,
               o.plan_used, o.delay_reduced_pct, o.notes
        FROM events ev
        LEFT JOIN outcomes o ON ev.id = o.event_id
        ORDER BY ev.created_at DESC
        LIMIT 200
    """).fetchall()
    conn.close()

    if not rows:
        return {"message": "No past events in memory yet.", "results": []}

    scored = []
    for r in rows:
        row_dict = dict(r)
        past_vec = event_to_vector(row_dict)
        sim      = cosine_sim(query_vec, past_vec)
        row_dict["similarity_score"] = round(sim * 100, 1)
        scored.append(row_dict)

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    top = scored[:top_k]

    results = []
    for r in top:
        badge = (f"Plan '{r['plan_used']}' reduced delay by {r['delay_reduced_pct']}%"
                 if r["plan_used"] else "No outcome logged yet")
        results.append({
            "event_id"            : r["id"],
            "similarity_score"    : r["similarity_score"],
            "event_cause"         : r["event_cause"],
            "zone"                : r["zone"],
            "corridor"            : r["corridor"],
            "predicted_severity"  : r["pred_severity"],
            "predicted_delay_mins": r["pred_delay_mins"],
            "plan_used"           : r["plan_used"],
            "delay_reduced_pct"   : r["delay_reduced_pct"],
            "notes"               : r["notes"],
            "outcome_badge"       : badge,
        })

    return {"results": results, "count": len(results)}

@app.get("/resources")
def get_resources(severity: str = "Moderate"):
    level = severity if severity in RESOURCE_TABLE else "Moderate"
    return {"severity": level, "resources": RESOURCE_TABLE[level]}

@app.get("/corridor-risk")
def corridor_risk():
    ranked = sorted(CORRIDOR_RISK.items(), key=lambda x: x[1], reverse=True)
    return {"corridors": [
        {"corridor": name, "risk_score": score,
         "risk_level": "High" if score > 75 else "Medium" if score > 50 else "Low"}
        for name, score in ranked
    ]}

@app.get("/zone-health")
def zone_health():
    ranked = sorted(ZONE_RISK.items(), key=lambda x: x[1], reverse=True)
    return {"zones": [
        {"zone": name, "risk_score": score,
         "risk_level": "High" if score > 70 else "Medium" if score > 50 else "Low"}
        for name, score in ranked
    ]}

@app.get("/live-feed")
def live_feed(limit: int = 10):
    """
    Live Operations Feed — most recent events with predicted severity,
    delay, and whether an outcome has been logged yet. Powers a real-time
    looking 'command center' panel without needing actual live traffic data.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT ev.id, ev.event_cause, ev.zone, ev.corridor, ev.priority,
               ev.requires_road_closure, ev.pred_severity, ev.pred_delay_mins,
               ev.created_at,
               CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END as has_outcome,
               o.actual_severity, o.delay_reduced_pct
        FROM events ev
        LEFT JOIN outcomes o ON ev.id = o.event_id
        ORDER BY ev.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    feed = []
    for r in rows:
        d = dict(r)
        status = "Resolved" if d["has_outcome"] else "Active"
        feed.append({
            "event_id"        : d["id"],
            "event_cause"     : d["event_cause"],
            "zone"            : d["zone"],
            "corridor"        : d["corridor"],
            "priority"        : d["priority"],
            "severity"        : d["pred_severity"],
            "delay_minutes"   : d["pred_delay_mins"],
            "status"          : status,
            "actual_severity" : d["actual_severity"],
            "delay_reduced_pct": d["delay_reduced_pct"],
            "created_at"      : d["created_at"],
        })
    return {"feed": feed, "count": len(feed)}

@app.get("/kpi-summary")
def kpi_summary():
    """
    Aggregate KPI cards: active incidents, predicted severe cases,
    average expected delay, high-risk zones currently flagged.
    Computed over the last 24 hours of logged events.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    all_events = conn.execute(
        "SELECT * FROM events WHERE created_at >= ?", (cutoff,)
    ).fetchall()

    resolved_ids = {r["event_id"] for r in conn.execute("SELECT event_id FROM outcomes").fetchall()}
    conn.close()

    total = len(all_events)
    active = sum(1 for e in all_events if e["id"] not in resolved_ids)
    severe_count = sum(1 for e in all_events if e["pred_severity"] == "Severe")
    delays = [e["pred_delay_mins"] for e in all_events if e["pred_delay_mins"] is not None]
    avg_delay = round(sum(delays) / len(delays), 1) if delays else 0.0

    zone_counts = {}
    for e in all_events:
        z = e["zone"]
        zone_counts[z] = zone_counts.get(z, 0) + 1
    high_risk_zones_flagged = sum(
        1 for z in zone_counts if ZONE_RISK.get(z, 0) > 70
    )

    return {
        "active_incidents"        : active,
        "total_incidents_24h"      : total,
        "predicted_severe_cases"    : severe_count,
        "avg_expected_delay_mins"    : avg_delay,
        "high_risk_zones_flagged"     : high_risk_zones_flagged,
        "window"                       : "last 24 hours",
    }

@app.get("/map-data/{event_id}")
def map_data(event_id: str):
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT latitude, longitude, pred_severity, pred_delay_mins FROM events WHERE id=?",
        (event_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Event not found")
    lat, lon, severity, delay = row
    radius_km = {"Quick": 0.3, "Moderate": 0.8, "Severe": 1.5}.get(severity, 0.8)
    return {
        "event_id": event_id, "latitude": lat, "longitude": lon,
        "severity": severity, "delay_minutes": delay, "radius_km": radius_km,
    }