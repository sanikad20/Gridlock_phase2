import streamlit as st
import requests
import folium
import os
from streamlit_folium import st_folium
from datetime import datetime

try:
    from chat_utils import get_chat_response, format_prediction_for_chat
    CHAT_AVAILABLE = True
except ImportError:
    CHAT_AVAILABLE = False

API = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Gridlock — Congestion Forecaster", layout="wide")
st.title("🚦 Gridlock — Event-Driven Congestion Forecaster")
st.caption("Flipkart Gridlock Hackathon 2.0 | Digital Twin + Memory Engine")

# ══════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════
SEVERITY_DISPLAY = {
    "Severe":   {"emoji": "🔴", "folium_color": "red",    "radius": 1000},
    "Moderate": {"emoji": "🟡", "folium_color": "orange", "radius": 600},
    "Quick":    {"emoji": "🟢", "folium_color": "green",  "radius": 300},
}

ZONE_COORDS = {
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

# ══════════════════════════════════════════════
# SIDEBAR — EVENT INPUT
# ══════════════════════════════════════════════
# ── Event Details Input ──
st.sidebar.header("📋 Event Details")

event_type = st.sidebar.selectbox("Event Type", ["unplanned", "planned"])

# Define valid causes by event type
PLANNED_CAUSES = [
    "public_event",
    "procession", 
    "vip_movement",
    "construction",
    "test_demo"
]

UNPLANNED_CAUSES = [
    "accident",
    "vehicle_breakdown",
    "tree_fall",
    "water_logging",
    "debris",
    "congestion",
    "pot_holes",
    "road_conditions"
]

# Show only valid causes for selected event type
if event_type == "planned":
    event_cause = st.sidebar.selectbox(
        "Event Cause",
        PLANNED_CAUSES,
        help="Only planned event causes available"
    )
else:
    event_cause = st.sidebar.selectbox(
        "Event Cause", 
        UNPLANNED_CAUSES,
        help="Only unplanned event causes available"
    )

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
veh_type       = st.sidebar.selectbox("Vehicle Type", [
    "none", "car", "bus", "truck", "two_wheeler", "auto", "heavy_vehicle"
])
police_station = st.sidebar.text_input("Police Station", value="Unknown")
junction       = st.sidebar.text_input("Junction (optional)", value="")

st.sidebar.subheader("⏰ Time")
now         = datetime.now()
hour        = st.sidebar.slider("Hour of Day", 0, 23, now.hour)
day_of_week = st.sidebar.selectbox("Day of Week",
    ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    index=now.weekday()
)
month   = st.sidebar.slider("Month", 1, 12, now.month)
day_idx = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].index(day_of_week)

st.sidebar.subheader("🔧 Digital Twin — What If?")
attendance_multiplier = st.sidebar.slider("Attendance Multiplier", 1.0, 5.0, 1.0, 0.5)
extra_barricades      = st.sidebar.slider("Extra Barricades", 0, 10, 0)
close_main_road       = st.sidebar.checkbox("Close Main Road?")

center = ZONE_COORDS.get(zone, [12.9716, 77.5946])

payload = {
    "event_type"            : event_type,
    "event_cause"           : event_cause,
    "priority"              : priority,
    "requires_road_closure" : requires_road_closure,
    "latitude"              : center[0],
    "longitude"             : center[1],
    "zone"                  : zone,
    "corridor"              : corridor,
    "veh_type"              : veh_type,
    "police_station"        : police_station or "Unknown",
    "junction"              : junction if junction else None,
    "hour"                  : hour,
    "day_of_week"           : day_idx,
    "month"                 : month,
}

twin_payload = {**payload,
    "extra_barricades"      : extra_barricades,
    "close_main_road"       : close_main_road or requires_road_closure,
    "attendance_multiplier" : attendance_multiplier,
}

# ══════════════════════════════════════════════
# KPI CARDS (live aggregate stats)
# ══════════════════════════════════════════════
st.subheader("📈 Command Center KPIs")
st.caption("Live aggregate stats from the last 24 hours of logged events")

try:
    kpi_res = requests.get(f"{API}/kpi-summary")
    if kpi_res.status_code == 200:
        kpi = kpi_res.json()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🚨 Active Incidents",       kpi["active_incidents"])
        k2.metric("🔴 Predicted Severe Cases",  kpi["predicted_severe_cases"])
        k3.metric("⏱️ Avg Expected Delay",      f"{kpi['avg_expected_delay_mins']:.0f} min")
        k4.metric("🗺️ High Risk Zones",         kpi["high_risk_zones_flagged"])
    else:
        st.info("KPI data unavailable.")
except Exception:
    st.info("Start API to see KPI summary.")

st.divider()

# ══════════════════════════════════════════════
# COMMAND CENTER METRICS (per-prediction)
# ══════════════════════════════════════════════
st.subheader("📊 Current Prediction Summary")
m1, m2, m3, m4 = st.columns(4)

if "last_prediction" in st.session_state:
    data  = st.session_state["last_prediction"]
    level = data["severity"]
    m1.metric("🚨 Severity",        level)
    m2.metric("🎯 Confidence",      f"{(data.get('confidence') or 0)*100:.0f}%")
    m3.metric("⏱️ Est. Clearance",  f"{data.get('estimated_clearance', 60)} min")
    m4.metric("🗺️ Zone Risk",       "High" if level == "Severe" else "Medium" if level == "Moderate" else "Low")
else:
    m1.metric("🚨 Severity",       "—")
    m2.metric("🎯 Confidence",      "—")
    m3.metric("⏱️ Est. Clearance",  "—")
    m4.metric("🗺️ Zone Risk",       "—")

st.divider()

# ══════════════════════════════════════════════
# MAIN PANEL — Prediction + Map
# ══════════════════════════════════════════════
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🔮 Congestion Prediction")

    if st.button("⚡ Predict & Log Event", type="primary", use_container_width=True):
        with st.spinner("Predicting..."):
            try:
                res = requests.post(f"{API}/predict-and-log", json=payload)
            except requests.exceptions.RequestException as ex:
                st.error(f"Could not reach API: {ex}")
                res = None

        if res is not None:
            if res.status_code == 200:
                data = res.json()
                st.session_state["last_prediction"] = data
                st.session_state["last_payload"]    = payload
                st.rerun()
            else:
                st.error(f"API error {res.status_code}: {res.text}")

    if "last_prediction" in st.session_state:
        data  = st.session_state["last_prediction"]
        level = data["severity"]
        disp  = SEVERITY_DISPLAY.get(level, {"emoji": "⚪"})

        st.markdown(f"## {disp['emoji']} Severity: **{level}**")
        st.metric("Predicted Delay", f"{data['delay_minutes']:.0f} min")

        st.subheader("🎯 Recommended Response Strategy")
        resources = data["resources"]

        priority_label = {"Severe": "🚨 IMMEDIATE", "Moderate": "⚠️ HIGH", "Quick": "🟢 STANDARD"}
        st.markdown(f"**Priority: {priority_label.get(level, '⚠️ HIGH')}**")

        ap1, ap2, ap3 = st.columns(3)
        ap1.metric("👮 Officers",    resources["officers"])
        ap2.metric("🚧 Barricades", resources["barricades"])
        ap3.metric("🔀 Diversions", resources["diversions"])

        st.markdown(f"**Expected Clearance: {data.get('estimated_clearance', 60)} min**")
        st.markdown(f"**Confidence: {(data.get('confidence') or 0)*100:.0f}%**")

        action_steps = {
            "Severe"  : [
                "Deploy 8+ Officers to incident site immediately",
                "Deploy 4+ Barricades on all approach roads",
                "Activate 2 Diversion Routes",
                "Alert Traffic Control Center",
                "Notify nearest police station",
            ],
            "Moderate": [
                "Deploy 4-6 Officers to incident site",
                "Deploy 2-3 Barricades on main approach",
                "Activate 1 Diversion Route",
                "Monitor situation every 15 minutes",
            ],
            "Quick"   : [
                "Deploy 1-2 Officers to incident site",
                "Standard monitoring — no diversion needed",
                "Update status every 30 minutes",
            ],
        }
        st.markdown("**Action Steps:**")
        for step in action_steps.get(level, []):
            st.markdown(f"• {step}")

        if payload["hour"] in [8, 9, 10, 17, 18, 19]:
            st.warning("⚠️ Peak hour — expect higher congestion impact")
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

st.divider()

# ══════════════════════════════════════════════
# EXPLAINABLE AI
# ══════════════════════════════════════════════
if "last_prediction" in st.session_state:
    st.subheader("🔍 Why this prediction?")
    explanation = st.session_state["last_prediction"].get("explanation", [])
    if explanation:
        ex_cols = st.columns(min(len(explanation), 3))
        for i, reason in enumerate(explanation):
            ex_cols[i % 3].success(reason)
    else:
        st.info("Standard incident — no high-risk factors detected")

    st.divider()

# ══════════════════════════════════════════════
# DIGITAL TWIN SIMULATOR
# ══════════════════════════════════════════════
st.subheader("🔧 Digital Twin Simulator — What If?")
st.caption("Simulates how different interventions would change the predicted outcome. Post-hoc adjustment, clearly labeled.")

if st.button("🔄 Run Digital Twin Simulation", use_container_width=True):
    with st.spinner("Simulating scenarios..."):
        try:
            res = requests.post(f"{API}/digital-twin", json=twin_payload)
        except requests.exceptions.RequestException as ex:
            st.error(f"Could not reach API: {ex}")
            res = None

    if res is not None and res.status_code == 200:
        twin = res.json()
        st.session_state["twin_result"] = twin
    elif res is not None:
        st.error(f"API error {res.status_code}: {res.text}")

if "twin_result" in st.session_state:
    twin      = st.session_state["twin_result"]
    baseline  = twin["baseline"]
    scenarios = twin["scenarios"]
    best      = twin["best_scenario"]

    st.markdown("**📍 Baseline Prediction (no intervention):**")
    b1, b2, b3 = st.columns(3)
    b1.metric("Severity",        baseline["severity"])
    b2.metric("Predicted Delay", f"{baseline['delay_minutes']:.0f} min")
    b3.metric("Est. Clearance",  f"{baseline['estimated_clearance']} min")

    st.markdown("**🔄 What-If Scenarios (simulated):**")
    sc_cols = st.columns(3)
    for i, sc in enumerate(scenarios):
        with sc_cols[i]:
            is_best = sc["scenario"] == best
            label   = f"{'⭐ ' if is_best else ''}{sc['scenario']}"
            change  = sc["delay_change_mins"]
            arrow   = "📉" if change < 0 else "📈"
            st.markdown(f"**{label}**")
            st.metric(
                "Adjusted Delay",
                f"{sc['adjusted_delay_mins']:.0f} min",
                delta=f"{change:+.0f} min"
            )
            sev_disp = SEVERITY_DISPLAY.get(sc["adjusted_severity"], {"emoji":"⚪"})
            st.write(f"{sev_disp['emoji']} {sc['adjusted_severity']}")
            st.write(f"{arrow} {abs(sc['delay_change_pct']):.0f}% {'reduction' if change < 0 else 'increase'}")

    st.info(f"✅ **Best Option: {best}** — lowest predicted delay after intervention")
    st.caption(twin["simulation_note"])

st.divider()

# ══════════════════════════════════════════════
# MEMORY ENGINE — Similar Past Events (with similarity %)
# ══════════════════════════════════════════════
st.subheader("🧠 Memory Engine — Similar Past Events")
st.caption("Most unique feature — retrieves what worked in similar past incidents, ranked by similarity %")

if st.button("🔍 Find Similar Past Events", use_container_width=True):
    with st.spinner("Searching memory..."):
        try:
            res = requests.post(f"{API}/similar-events", json=payload)
        except requests.exceptions.RequestException as ex:
            st.error(f"Could not reach API: {ex}")
            res = None

    if res is not None and res.status_code == 200:
        st.session_state["similar_events"] = res.json().get("results", [])
    elif res is not None:
        st.error(f"API error {res.status_code}: {res.text}")

if "similar_events" in st.session_state:
    similar = st.session_state["similar_events"]
    if not similar:
        st.info("No similar past events found in memory yet.")
    else:
        for i, e in enumerate(similar):
            sev   = e["predicted_severity"]
            badge = SEVERITY_DISPLAY.get(sev, {"emoji": "⚪"})["emoji"]
            sim_pct = e.get("similarity_score", 0)
            with st.expander(
                f"{badge} Past Event {i+1} — {e['event_cause']} on {e['corridor']} (Similarity: {sim_pct:.0f}%)"
            ):
                # Similarity bar
                st.progress(min(int(sim_pct), 100), text=f"Match: {sim_pct:.0f}%")
                c1, c2 = st.columns(2)
                c1.write(f"**Zone:** {e['zone']}")
                c1.write(f"**Predicted Severity:** {sev}")
                c1.write(f"**Predicted Delay:** {e.get('predicted_delay_mins','N/A')} min")
                c2.write(f"**Plan Used:** {e.get('plan_used','N/A')}")
                c2.write(f"**Delay Reduced:** {e.get('delay_reduced_pct','N/A')}%")
                c2.write(f"**Notes:** {e.get('notes','—')}")
                st.success(f"✅ {e['outcome_badge']}")

st.divider()

# ══════════════════════════════════════════════
# LIVE OPERATIONS FEED
# ══════════════════════════════════════════════
st.subheader("📡 Live Operations Feed")
st.caption("Most recent incidents logged into the system, real-time command center style")

try:
    feed_res = requests.get(f"{API}/live-feed", params={"limit": 8})
    if feed_res.status_code == 200:
        feed = feed_res.json().get("feed", [])
        if not feed:
            st.info("No incidents logged yet. Predict an event to populate the feed.")
        else:
            for item in feed:
                sev_disp = SEVERITY_DISPLAY.get(item["severity"], {"emoji": "⚪"})
                status_emoji = "✅" if item["status"] == "Resolved" else "🔴"
                fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
                fc1.write(f"{sev_disp['emoji']} **{item['event_cause']}** — {item['corridor']}")
                fc2.write(f"{item['zone']}")
                fc3.write(f"{item['delay_minutes']:.0f} min" if item['delay_minutes'] else "—")
                fc4.write(f"{status_emoji} {item['status']}")
    else:
        st.info("Live feed unavailable.")
except Exception:
    st.info("Start API to see live operations feed.")

st.divider()

# ══════════════════════════════════════════════
# CORRIDOR RISK RANKING
# ══════════════════════════════════════════════
st.subheader("🛣️ Corridor Risk Ranking")
st.caption("Derived from historical Astram incident density — no extra data required")

try:
    cr_res = requests.get(f"{API}/corridor-risk")
    if cr_res.status_code == 200:
        corridors = cr_res.json()["corridors"]
        for c in corridors:
            col_name, col_bar = st.columns([2, 3])
            col_name.write(c["corridor"])
            color = "🔴" if c["risk_score"] > 75 else "🟡" if c["risk_score"] > 50 else "🟢"
            col_bar.progress(c["risk_score"], text=f"{color} {c['risk_score']}/100")
except Exception:
    st.info("Start API to see corridor risk data.")

st.divider()

# ══════════════════════════════════════════════
# ZONE HEALTH DASHBOARD
# ══════════════════════════════════════════════
st.subheader("🗺️ Zone Health Dashboard")
st.caption("Generated from historical incident density — no extra data required")

try:
    zh_res = requests.get(f"{API}/zone-health")
    if zh_res.status_code == 200:
        zones = zh_res.json()["zones"]
        z1, z2 = st.columns(2)
        for i, z in enumerate(zones):
            col   = z1 if i % 2 == 0 else z2
            color = "🔴" if z["risk_score"] > 70 else "🟡" if z["risk_score"] > 50 else "🟢"
            col.progress(z["risk_score"], text=f"{color} {z['zone']}: {z['risk_score']}/100")
except Exception:
    st.info("Start API to see zone health data.")

st.divider()

# ══════════════════════════════════════════════
# INCIDENT WORKFLOW TIMELINE
# ══════════════════════════════════════════════
st.subheader("📋 Incident Workflow")

wf_cols = st.columns(5)
if "last_prediction" in st.session_state:
    level = st.session_state["last_prediction"]["severity"]
    wf_cols[0].success("📥 Reported")
    wf_cols[1].warning(f"🔮 Predicted {level}")
    wf_cols[2].info("📋 Resources Suggested")
    wf_cols[3].warning("✅ Response Selected")
    wf_cols[4].error("📝 Outcome Pending")
else:
    for col, label in zip(wf_cols, ["📥 Reported", "🔮 Predicted", "📋 Resources", "✅ Response", "📝 Outcome"]):
        col.info(label)

st.divider()

# ══════════════════════════════════════════════
# AI ASSISTANT (Groq Llama 3.3 70B)
# ══════════════════════════════════════════════
st.subheader("💬 AI Assistant")
st.caption("Ask about this prediction, response strategy, or general traffic management guidance")

if not CHAT_AVAILABLE:
    st.warning(
        "AI Assistant unavailable — make sure `chat_utils.py` is in the same folder as "
        "`app.py`, and run `pip install groq`."
    )
else:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_question = st.chat_input("Ask the assistant about this prediction...")

    if user_question:
        st.session_state["chat_history"].append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        # Ground the assistant in the latest prediction, if one exists, without
        # polluting the chat history with the injected context every turn.
        outgoing_message = user_question
        if "last_prediction" in st.session_state:
            context = format_prediction_for_chat(st.session_state["last_prediction"])
            outgoing_message = f"{context}\n\nOperator question: {user_question}"

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = get_chat_response(
                    outgoing_message,
                    st.session_state["chat_history"][:-1],  # history before this turn
                )
            st.markdown(reply)

        st.session_state["chat_history"].append({"role": "assistant", "content": reply})

st.divider()

# ══════════════════════════════════════════════
# LOG ACTUAL OUTCOME
# ══════════════════════════════════════════════
st.subheader("📝 Log Actual Outcome")
st.caption("Self-learning — outcomes improve future memory engine recommendations")

if "last_prediction" in st.session_state:
    event_id = st.session_state["last_prediction"].get("event_id")
    with st.form("outcome_form"):
        oc1, oc2 = st.columns(2)
        actual_severity   = oc1.selectbox("Actual Severity", ["Quick", "Moderate", "Severe"])
        plan_used         = oc2.text_input("Plan Used", value="Plan A")
        officers          = oc1.number_input("Officers Deployed",  min_value=0, value=4)
        barricades        = oc2.number_input("Barricades Used",    min_value=0, value=2)
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
                "notes"             : notes,
            }
            try:
                r = requests.post(f"{API}/log-outcome", json=outcome_payload)
            except requests.exceptions.RequestException as ex:
                st.error(f"Could not reach API: {ex}")
                r = None

            if r is not None:
                if r.status_code == 200:
                    st.success(f"✅ Outcome saved! {r.json()['message']}")
                else:
                    st.error(f"API error {r.status_code}: {r.text}")
else:
    st.info("Run a prediction first to log its outcome.")