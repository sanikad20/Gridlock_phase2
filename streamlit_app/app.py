import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os

# In local dev, set API_URL=http://127.0.0.1:8000 (or rely on the default).
# In Render, render.yaml injects API_URL as "host:port" from the gridlock-api
# service, so we add the scheme here.
_raw_api_url = os.environ.get("API_URL", "http://127.0.0.1:8000")
API = _raw_api_url if _raw_api_url.startswith("http") else f"https://{_raw_api_url}"

st.set_page_config(page_title="Gridlock — Congestion Forecaster", layout="wide")
st.title("🚦 Gridlock — Event-Driven Congestion Forecaster")
st.caption("Flipkart Gridlock Hackathon 2.0 | Digital Twin + Memory Engine")

# ── Sidebar: Event Input Form ──────────────────────────────────
st.sidebar.header("📋 Event Details")

event_type = st.sidebar.selectbox("Event Type", ["unplanned", "planned"])
event_cause = st.sidebar.selectbox("Event Cause", [
    "accident", "congestion", "vehicle_breakdown", "public_event",
    "procession", "protest", "vip_movement", "tree_fall",
    "water_logging", "construction", "pot_holes", "road_conditions",
    "Debris", "Fog / Low Visibility", "others"
])
priority = st.sidebar.selectbox("Priority", ["High", "Low"])
requires_road_closure = st.sidebar.checkbox("Requires Road Closure?")
corridor = st.sidebar.selectbox("Corridor", [
    "Non-corridor", "Mysore Road", "Bellary Road 1", "Bellary Road 2",
    "Tumkur Road", "Hosur Road", "ORR North 1", "Old Madras Road",
    "Magadi Road", "ORR East 1"
])
zone = st.sidebar.selectbox("Zone", [
    "Central Zone 1", "Central Zone 2", "North Zone 1", "North Zone 2",
    "South Zone 1", "South Zone 2", "East Zone 1", "East Zone 2",
    "West Zone 1", "West Zone 2"
])

veh_type = st.sidebar.selectbox("Vehicle Type", [
    "none", "car", "bus", "truck", "two_wheeler", "auto", "heavy_vehicle"
])
police_station = st.sidebar.text_input("Police Station", value="Unknown")
junction = st.sidebar.text_input("Junction (optional)", value="")

st.sidebar.subheader("⏰ Time")
now = datetime.now()
hour        = st.sidebar.slider("Hour of Day", 0, 23, now.hour)
day_of_week = st.sidebar.selectbox("Day of Week",
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    index=now.weekday()
)
month = st.sidebar.slider("Month", 1, 12, now.month)
day_idx = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day_of_week)

# Digital Twin sliders — these feed ONLY the /digital-twin simulation below,
# not the baseline /predict-and-log call. Keeping them separate from
# requires_road_closure avoids conflating a real event fact with a
# hypothetical what-if (api/main.py's apply_digital_twin_adjustment treats
# close_main_road the same way: a scenario-only toggle).
st.sidebar.subheader("🪄 Digital Twin — What If?")
attendance_multiplier = st.sidebar.slider("Attendance Multiplier", 1, 5, 1)
extra_barricades      = st.sidebar.slider("Extra Barricades", 0, 10, 0)
close_main_road       = st.sidebar.checkbox("Close Main Road?")
st.sidebar.caption("These feed the Digital Twin Simulator section, not the baseline prediction.")

# ── Zone coordinates for Bengaluru (also used as lat/lon for the model) ──
zone_coords = {
    "Central Zone 1": [12.9716, 77.5946],
    "Central Zone 2": [12.9800, 77.6000],
    "North Zone 1"  : [13.0500, 77.5800],
    "North Zone 2"  : [13.0800, 77.6000],
    "South Zone 1"  : [12.9000, 77.5700],
    "South Zone 2"  : [12.8700, 77.6000],
    "East Zone 1"   : [12.9900, 77.6500],
    "East Zone 2"   : [12.9600, 77.7000],
    "West Zone 1"   : [12.9700, 77.5300],
    "West Zone 2"   : [12.9400, 77.5000],
}
center = zone_coords.get(zone, [12.9716, 77.5946])

payload = {
    "event_type"            : event_type,
    "event_cause"           : event_cause,
    "priority"               : priority,
    "requires_road_closure"   : requires_road_closure,
    "latitude"                 : center[0],
    "longitude"                 : center[1],
    "zone"                       : zone,
    "corridor"                    : corridor,
    "veh_type"                     : veh_type,
    "police_station"                 : police_station or "Unknown",
    "junction"                         : junction if junction else None,
    "hour"                               : hour,
    "day_of_week"                         : day_idx,
    "month"                                : month,
}

SEVERITY_DISPLAY = {
    "Severe":   {"emoji": "🔴", "folium_color": "red",    "radius": 1000},
    "Moderate": {"emoji": "🟡", "folium_color": "orange", "radius": 600},
    "Quick":    {"emoji": "🟢", "folium_color": "green",  "radius": 300},
}

PRIORITY_LABEL = {"Severe": "🚨 IMMEDIATE", "Moderate": "⚠️ HIGH", "Quick": "🟢 STANDARD"}

ACTION_STEPS = {
    "Severe": [
        "Deploy {officers} officers to incident site",
        "Deploy {barricades} barricades on approach roads",
        "Activate {diversions} diversion route(s) immediately",
        "Alert Traffic Control Center",
        "Notify nearest police station",
    ],
    "Moderate": [
        "Deploy {officers} officers to incident site",
        "Deploy {barricades} barricades on main approach",
        "Activate {diversions} diversion route(s)",
        "Monitor situation every 15 minutes",
    ],
    "Quick": [
        "Deploy {officers} officer(s) to incident site",
        "Standard monitoring — no diversion needed",
        "Update status every 30 minutes",
    ],
}


def get_smart_action_plan(severity, resources, clearance_mins):
    steps = ACTION_STEPS.get(severity, ACTION_STEPS["Moderate"])
    actions = [
        s.format(officers=resources["officers"], barricades=resources["barricades"],
                  diversions=resources["diversions"])
        for s in steps
    ]
    return {
        "priority"  : PRIORITY_LABEL.get(severity, "⚠️ HIGH"),
        "actions"   : actions,
        "clearance" : clearance_mins,
    }


def fetch_corridor_risk():
    try:
        r = requests.get(f"{API}/corridor-risk", timeout=10)
        return r.json().get("corridors", []) if r.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


def fetch_zone_health():
    try:
        r = requests.get(f"{API}/zone-health", timeout=10)
        return r.json().get("zones", []) if r.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


# ── Command Center Metrics ──────────────────────────────────────
if "last_prediction" in st.session_state:
    cc_data = st.session_state["last_prediction"]
    cc_level = cc_data["severity"]
    cc_conf  = cc_data.get("confidence")
    cc_zone  = st.session_state.get("last_payload", payload)["zone"]

    zone_scores = {z["zone"]: z for z in fetch_zone_health()}
    cc_zone_level = zone_scores.get(cc_zone, {}).get("risk_level", "—")

    st.subheader("📊 Command Center")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🚨 Severity", cc_level)
    m2.metric("🎯 Confidence", f"{cc_conf*100:.0f}%" if cc_conf is not None else "—")
    m3.metric("⏱️ Est. Clearance", f"{cc_data.get('estimated_clearance', 60)} min")
    m4.metric("🗺️ Zone Risk", cc_zone_level)
    st.divider()

# ── Main Panel: Prediction + Map ────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🔮 Congestion Prediction")

    if st.button("⚡ Predict & Log Event", type="primary", use_container_width=True):
        with st.spinner("Predicting..."):
            try:
                res = requests.post(f"{API}/predict-and-log", json=payload, timeout=15)
            except requests.exceptions.RequestException as ex:
                st.error(f"Could not reach API: {ex}")
                res = None

        if res is not None:
            if res.status_code == 200:
                data = res.json()
                st.session_state["last_prediction"] = data
                st.session_state["last_payload"]    = payload
                st.session_state.pop("digital_twin_result", None)
                st.session_state.pop("outcome_logged", None)
            else:
                st.error(f"API error {res.status_code}: {res.text}")

    if "last_prediction" in st.session_state:
        data  = st.session_state["last_prediction"]
        level = data["severity"]
        disp  = SEVERITY_DISPLAY.get(level, {"emoji": "⚪"})

        st.markdown(f"## {disp['emoji']} Severity: **{level}**")
        st.metric("Predicted Delay", f"{data['delay_minutes']:.0f} min")
        st.info(f"📌 **Recommendation:** {data['recommendation']}")

        res_data = data["resources"]
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("👮 Officers",    res_data["officers"])
        rc2.metric("🚧 Barricades", res_data["barricades"])
        rc3.metric("🔀 Diversions", res_data["diversions"])

        if payload["hour"] in [8, 9, 10, 17, 18, 19]:
            st.warning("⚠️ Peak hour detected — expect higher congestion impact")
        if payload["requires_road_closure"]:
            st.error("🚫 Road closure required — activate diversion plan immediately")

        st.caption(f"Event ID: {data.get('event_id','—')} | Corridor: {payload['corridor']} | Zone: {payload['zone']}")

with col2:
    st.subheader("🗺️ Congestion Map")

    m = folium.Map(location=center, zoom_start=13)

    if "last_prediction" in st.session_state:
        level = st.session_state["last_prediction"]["severity"]
        disp  = SEVERITY_DISPLAY.get(level, {"folium_color": "blue", "radius": 400})

        folium.Circle(
            location=center, radius=disp["radius"],
            color=disp["folium_color"], fill=True, fill_opacity=0.4,
            popup=f"{level} Severity — {zone}"
        ).add_to(m)

        folium.Marker(
            location=center,
            popup=f"{event_cause} | {corridor}",
            icon=folium.Icon(color=disp["folium_color"], icon="warning-sign", prefix="glyphicon")
        ).add_to(m)

    st_folium(m, width=500, height=380)

# ── Smart Action Plan + Explainable AI ──────────────────────────
if "last_prediction" in st.session_state:
    data  = st.session_state["last_prediction"]
    level = data["severity"]

    st.divider()
    ap_col, ex_col = st.columns(2)

    with ap_col:
        st.subheader("🎯 Recommended Response Strategy")
        plan = get_smart_action_plan(level, data["resources"], data.get("estimated_clearance", 60))
        st.markdown(f"**Priority: {plan['priority']}**")
        st.markdown(f"**Expected Clearance: {plan['clearance']} min**")
        if data.get("confidence") is not None:
            st.markdown(f"**Confidence: {data['confidence']*100:.0f}%**")
        st.markdown("**Action Steps:**")
        for action in plan["actions"]:
            st.markdown(f"• {action}")

    with ex_col:
        st.subheader("🔍 Why This Prediction?")
        for reason in data.get("explanation", []):
            st.success(reason)

# ── Digital Twin Simulator (Option B — post-hoc simulated adjustment) ───
st.divider()
st.subheader("🪄 Digital Twin Simulator")
st.caption("What-if simulation applied on top of the baseline prediction.")

if st.button("▶️ Run Digital Twin Simulation", use_container_width=True):
    twin_payload = {
        **payload,
        "extra_barricades"     : extra_barricades,
        "close_main_road"      : close_main_road,
        "attendance_multiplier": float(attendance_multiplier),
    }
    with st.spinner("Simulating scenarios..."):
        try:
            res = requests.post(f"{API}/digital-twin", json=twin_payload, timeout=15)
        except requests.exceptions.RequestException as ex:
            st.error(f"Could not reach API: {ex}")
            res = None

    if res is not None:
        if res.status_code == 200:
            st.session_state["digital_twin_result"] = res.json()
        else:
            st.error(f"API error {res.status_code}: {res.text}")

if "digital_twin_result" in st.session_state:
    twin     = st.session_state["digital_twin_result"]
    baseline = twin["baseline"]
    base_disp = SEVERITY_DISPLAY.get(baseline["severity"], {"emoji": "⚪"})

    st.markdown(
        f"**Baseline:** {base_disp['emoji']} {baseline['severity']} — "
        f"{baseline['delay_minutes']:.0f} min"
    )

    sc_cols = st.columns(3)
    for sc_col, scenario in zip(sc_cols, twin["scenarios"]):
        is_best = scenario["scenario"] == twin["best_scenario"]
        sc_disp = SEVERITY_DISPLAY.get(scenario["adjusted_severity"], {"emoji": "⚪"})
        with sc_col:
            st.markdown(f"**{'⭐ ' if is_best else ''}{scenario['scenario']}**")
            st.markdown(f"{sc_disp['emoji']} {scenario['adjusted_severity']}")
            st.metric(
                "Delay",
                f"{scenario['adjusted_delay_mins']:.0f} min",
                delta=f"{scenario['delay_change_mins']:+.0f} min",
                delta_color="inverse",
            )

    st.success(f"⭐ Best option: **{twin['best_scenario']}**")
    st.caption(twin.get("simulation_note", ""))

# ── Corridor Risk Ranking ───────────────────────────────────────
st.divider()
st.subheader("🛣️ Top Risk Corridors")
corridors = fetch_corridor_risk()
if corridors:
    for c in corridors:
        risk  = c["risk_score"]
        color = "🔴" if risk > 75 else "🟡" if risk > 50 else "🟢"
        name_col, bar_col = st.columns([2, 3])
        name_col.write(c["corridor"])
        bar_col.progress(risk, text=f"{color} {risk}/100")
else:
    st.info("Corridor risk data unavailable — check that the API is running.")

# ── Zone Health Dashboard ───────────────────────────────────────
st.divider()
st.subheader("🗺️ Zone Health Dashboard")
zones = fetch_zone_health()
if zones:
    z1, z2 = st.columns(2)
    for i, z in enumerate(zones):
        risk  = z["risk_score"]
        color = "🔴" if risk > 70 else "🟡" if risk > 50 else "🟢"
        target_col = z1 if i % 2 == 0 else z2
        target_col.progress(risk, text=f"{color} {z['zone']}: {risk}/100")
else:
    st.info("Zone health data unavailable — check that the API is running.")

# ── Incident Workflow Timeline ──────────────────────────────────
st.divider()
st.subheader("📋 Incident Workflow")

has_prediction = "last_prediction" in st.session_state
has_twin       = "digital_twin_result" in st.session_state
has_outcome    = st.session_state.get("outcome_logged", False)

wf1, wf2, wf3, wf4, wf5 = st.columns(5)

if has_prediction:
    wf1.success("📥 Reported")
    wf2.warning(f"🔮 Predicted {st.session_state['last_prediction']['severity']}")
    wf3.info("📋 Resources Suggested")
else:
    wf1.info("📥 Not Reported")
    wf2.info("🔮 Pending")
    wf3.info("📋 Pending")

if has_twin:
    wf4.success("✅ Response Selected")
else:
    wf4.info("✅ Pending")

if has_outcome:
    wf5.success("📝 Outcome Logged")
else:
    wf5.error("📝 Outcome Pending")

# ── Memory Engine Panel ────────────────────────────────────────
st.divider()
st.subheader("🧠 Memory Engine — Similar Past Events")

if st.button("🔍 Find Similar Past Events", use_container_width=True):
    with st.spinner("Searching memory..."):
        try:
            res = requests.post(f"{API}/similar-events", json=payload, timeout=15)
        except requests.exceptions.RequestException as ex:
            st.error(f"Could not reach API: {ex}")
            res = None

    if res is not None and res.status_code == 200:
        similar = res.json().get("results", [])
        if not similar:
            st.info("No similar past events found in memory.")
        else:
            for i, e in enumerate(similar):
                sev   = e["predicted_severity"]
                badge = SEVERITY_DISPLAY.get(sev, {"emoji": "⚪"})["emoji"]
                with st.expander(f"{badge} Past Event {i+1} — {e['event_cause']} on {e['corridor']}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"**Zone:** {e['zone']}")
                    c1.write(f"**Predicted Severity:** {sev}")
                    c1.write(f"**Predicted Delay:** {e.get('predicted_delay_mins','N/A')} min")
                    c2.write(f"**Plan Used:** {e.get('plan_used','N/A')}")
                    c2.write(f"**Delay Reduced:** {e.get('delay_reduced_pct','N/A')}%")
                    c2.write(f"**Notes:** {e.get('notes','—')}")
                    st.success(f"✅ {e['outcome_badge']}")
    elif res is not None:
        st.error(f"API error {res.status_code}: {res.text}")

# ── Log Outcome Panel ──────────────────────────────────────────
st.divider()
st.subheader("📝 Log Actual Outcome")

if "last_prediction" in st.session_state:
    event_id = st.session_state["last_prediction"].get("event_id")
    with st.form("outcome_form"):
        oc1, oc2 = st.columns(2)
        actual_severity   = oc1.selectbox("Actual Severity", ["Quick", "Moderate", "Severe"])
        plan_used         = oc2.text_input("Plan Used", value="Plan A")
        officers          = oc1.number_input("Officers Deployed", min_value=0, value=4)
        barricades        = oc2.number_input("Barricades Used",   min_value=0, value=2)
        actual_delay_mins = st.number_input("Actual Delay (minutes)", min_value=0.0, value=30.0, step=1.0)
        delay_reduced     = st.slider("Delay Reduced (%)", 0, 100, 30)
        notes             = st.text_area("Notes")

        if st.form_submit_button("💾 Save Outcome", type="primary"):
            outcome_payload = {
                "event_id"          : event_id,
                "actual_severity"   : actual_severity,
                "actual_delay_mins" : float(actual_delay_mins),
                "officers_deployed" : officers,
                "barricades_used"   : barricades,
                "delay_reduced_pct" : float(delay_reduced),
                "plan_used"         : plan_used,
                "notes"             : notes
            }
            try:
                r = requests.post(f"{API}/log-outcome", json=outcome_payload, timeout=15)
            except requests.exceptions.RequestException as ex:
                st.error(f"Could not reach API: {ex}")
                r = None

            if r is not None:
                if r.status_code == 200:
                    st.session_state["outcome_logged"] = True
                    st.success(f"✅ Outcome saved! {r.json()['message']}")
                else:
                    st.error(f"API error {r.status_code}: {r.text}")
else:
    st.info("Run a prediction first to log its outcome.")
