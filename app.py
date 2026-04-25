import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import random
import time

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MTC Chennai RL Optimizer",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
    .main { background: #0a0e1a; }
    .block-container { padding: 1.5rem 2rem; }
    .rl-badge {
        background: linear-gradient(90deg, #00d4ff, #0066ff);
        color: white; padding: 3px 12px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    .static-badge {
        background: linear-gradient(90deg, #ff6b35, #ff3535);
        color: white; padding: 3px 12px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600;
    }
    div[data-testid="stMetric"] {
        background: #1a1f35; border: 1px solid #2a3050;
        border-radius: 10px; padding: 0.8rem 1rem;
    }
    div[data-testid="stMetric"] label { color: #8892b0 !important; }
    div[data-testid="stMetric"] div { color: #00d4ff !important; font-weight: 700; }
    .stButton > button { border-radius: 8px; font-weight: 600; border: none; }
    .title-header {
        background: linear-gradient(135deg, #0d1220, #1a1f35);
        border-bottom: 2px solid #00d4ff33;
        padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── MTC Route Data ───────────────────────────────────────────────────────────
ROUTES = [
    {"id": 1, "name": "Broadway → Tambaram",         "stops": 22, "base_demand": 850, "is_peripheral": False},
    {"id": 2, "name": "Koyambedu → Sholinganallur",  "stops": 18, "base_demand": 720, "is_peripheral": False},
    {"id": 3, "name": "CMBT → Ambattur",              "stops": 14, "base_demand": 680, "is_peripheral": False},
    {"id": 4, "name": "Anna Nagar → Chrompet",        "stops": 16, "base_demand": 590, "is_peripheral": False},
    {"id": 5, "name": "Avadi → Broadway",              "stops": 20, "base_demand": 410, "is_peripheral": True},
    {"id": 6, "name": "Poonamallee → Central",        "stops": 15, "base_demand": 380, "is_peripheral": True},
    {"id": 7, "name": "Redhills → T.Nagar",            "stops": 19, "base_demand": 340, "is_peripheral": True},
    {"id": 8, "name": "Madhavaram → Guindy",           "stops": 17, "base_demand": 460, "is_peripheral": False},
]

MIN_PERIPHERAL_BUSES = 3
MIN_CENTRAL_BUSES = 4

# ─── Session State Init ───────────────────────────────────────────────────────
if "hour" not in st.session_state:
    st.session_state.hour = 8
    st.session_state.minute = 0
    st.session_state.step = 0
    st.session_state.mode = "static"
    st.session_state.buses = {r["id"]: 8 for r in ROUTES}
    st.session_state.wait_times = {r["id"]: 10.0 for r in ROUTES}
    st.session_state.occupancy = {r["id"]: 0.5 for r in ROUTES}
    st.session_state.disrupted = []
    st.session_state.passengers_served = 0
    st.session_state.equity_violations = 0
    st.session_state.wait_history = []
    st.session_state.reward_history = []
    st.session_state.fleet_used = 64

# ─── Core Functions ───────────────────────────────────────────────────────────
def get_demand_multiplier(hour, route_id):
    profile = {
        6: 0.5, 7: 1.2, 8: 2.0, 9: 1.7, 10: 1.0,
        11: 0.9, 12: 1.2, 13: 1.3, 14: 0.8, 15: 0.9,
        16: 1.4, 17: 1.9, 18: 2.1, 19: 1.5, 20: 1.0,
        21: 0.7, 22: 0.4, 23: 0.2,
    }
    m = profile.get(hour, 0.5) * random.uniform(0.9, 1.1)
    if route_id in st.session_state.disrupted:
        m *= 1.6
    return m

def compute_wait_time(buses, demand_mult):
    if buses <= 0: return 45.0
    base_wait = 60.0 / buses
    load = (demand_mult * 60) / (buses * 60)
    load = min(load, 2.5)
    return round(min(max(base_wait * (1 + 0.4 * max(0, load - 1.0)), 1.0), 45.0), 2)

def compute_occupancy(buses, demand_mult, base_demand):
    if buses <= 0: return 1.0
    occ = (base_demand * demand_mult) / (buses * 60)
    return round(min(max(occ, 0.1), 1.5), 2)

def rl_agent(buses, wait_times, occupancy, hour):
    buses = dict(buses)
    route_map = {r["id"]: r for r in ROUTES}
    scores = {}
    for r in ROUTES:
        rid = r["id"]
        scores[rid] = wait_times[rid] * 0.5 + occupancy[rid] * 10
        if rid in st.session_state.disrupted:
            scores[rid] *= 1.5

    sorted_low  = sorted(scores, key=lambda x: scores[x])
    sorted_high = sorted(scores, key=lambda x: scores[x], reverse=True)
    equity_violations = 0

    for low_id in sorted_low:
        min_b = MIN_PERIPHERAL_BUSES if route_map[low_id]["is_peripheral"] else MIN_CENTRAL_BUSES
        if buses[low_id] > min_b:
            for high_id in sorted_high:
                if high_id != low_id and (wait_times[high_id] > 8 or occupancy[high_id] > 0.85):
                    buses[low_id] -= 1
                    buses[high_id] += 1
                    break

    for r in ROUTES:
        rid = r["id"]
        min_b = MIN_PERIPHERAL_BUSES if r["is_peripheral"] else MIN_CENTRAL_BUSES
        if buses[rid] < min_b:
            buses[rid] = min_b
            equity_violations += 1

    return buses, equity_violations

def simulation_step():
    hour = st.session_state.hour
    if st.session_state.mode == "static":
        buses = {r["id"]: 8 for r in ROUTES}
    else:
        buses, eq_v = rl_agent(
            st.session_state.buses,
            st.session_state.wait_times,
            st.session_state.occupancy,
            hour
        )
        st.session_state.equity_violations += eq_v

    st.session_state.buses = buses
    total_wait = 0
    total_passengers = 0

    for r in ROUTES:
        rid = r["id"]
        dm = get_demand_multiplier(hour, rid)
        wt = compute_wait_time(buses[rid], dm)
        occ = compute_occupancy(buses[rid], dm, r["base_demand"])
        st.session_state.wait_times[rid] = wt
        st.session_state.occupancy[rid] = occ
        total_wait += wt
        total_passengers += int(r["base_demand"] * dm * (1 - min(wt / 45.0, 0.9)))

    avg_wait = total_wait / len(ROUTES)
    fleet_used = sum(buses.values())
    reward = -avg_wait + (total_passengers / 1000) - (st.session_state.equity_violations * 2)

    st.session_state.passengers_served += total_passengers
    st.session_state.wait_history.append(round(avg_wait, 2))
    st.session_state.reward_history.append(round(reward, 2))
    st.session_state.fleet_used = fleet_used
    st.session_state.step += 1
    st.session_state.minute += 15
    if st.session_state.minute >= 60:
        st.session_state.minute = 0
        st.session_state.hour = (st.session_state.hour + 1) % 24

def get_compare_data():
    results = {"static": [], "rl": []}
    for mode_name in ["static", "rl"]:
        buses_sim = {r["id"]: 8 for r in ROUTES}
        for hour in range(6, 24):
            total_wait = 0
            if mode_name == "rl":
                temp_wt = {r["id"]: 10.0 for r in ROUTES}
                temp_occ = {r["id"]: 0.5 for r in ROUTES}
                buses_sim, _ = rl_agent(buses_sim, temp_wt, temp_occ, hour)
            else:
                buses_sim = {r["id"]: 8 for r in ROUTES}
            for r in ROUTES:
                dm = get_demand_multiplier(hour, r["id"])
                total_wait += compute_wait_time(buses_sim[r["id"]], dm)
            results[mode_name].append({"hour": hour, "avg_wait": round(total_wait / len(ROUTES), 2)})
    return results

def reset_sim():
    st.session_state.hour = 8
    st.session_state.minute = 0
    st.session_state.step = 0
    st.session_state.buses = {r["id"]: 8 for r in ROUTES}
    st.session_state.wait_times = {r["id"]: 10.0 for r in ROUTES}
    st.session_state.occupancy = {r["id"]: 0.5 for r in ROUTES}
    st.session_state.disrupted = []
    st.session_state.passengers_served = 0
    st.session_state.equity_violations = 0
    st.session_state.wait_history = []
    st.session_state.reward_history = []
    st.session_state.fleet_used = 64

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚌 MTC RL Control Panel")
    st.markdown("---")

    mode = st.radio("**Simulation Mode**", ["static", "rl"],
                    format_func=lambda x: "📋 Static Schedule" if x == "static" else "🤖 RL Agent (Adaptive)")
    if st.button("✅ Apply Mode", use_container_width=True):
        st.session_state.mode = mode
        st.success(f"Mode: {mode.upper()}")

    st.markdown("---")
    st.markdown("### ⚡ Disruption Simulator")
    route_names = {r["id"]: r["name"] for r in ROUTES}
    sel_route = st.selectbox("Select Route to Disrupt",
                              options=[r["id"] for r in ROUTES],
                              format_func=lambda x: route_names.get(x, str(x)))
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔴 Disrupt", use_container_width=True):
            if sel_route not in st.session_state.disrupted:
                st.session_state.disrupted.append(sel_route)
            st.warning("Disrupted!")
    with col2:
        if st.button("🟢 Restore", use_container_width=True):
            if sel_route in st.session_state.disrupted:
                st.session_state.disrupted.remove(sel_route)
            st.success("Restored!")

    st.markdown("---")
    if st.button("🔄 Reset Simulation", use_container_width=True):
        reset_sim()
        st.success("Reset done!")

    st.markdown("---")
    auto_step = st.toggle("▶️ Auto-Step (Live Sim)", value=False)
    step_speed = st.slider("Speed (seconds)", 0.3, 3.0, 1.0)

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="title-header">
    <h1 style="margin:0; color:#00d4ff; font-size:1.8rem;">
        🚌 MTC Chennai — Adaptive Bus Frequency Optimizer
    </h1>
    <p style="margin:0.3rem 0 0; color:#8892b0; font-size:0.9rem;">
        Reinforcement Learning Agent · Real-Time Frequency Optimization · 800+ Routes · 45 Lakh Daily Passengers
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Buttons ──────────────────────────────────────────────────────────────────
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
with col_btn1:
    if st.button("⏩ Step +15min", use_container_width=True, type="primary"):
        simulation_step()
with col_btn2:
    compare_clicked = st.button("📊 Compare Modes", use_container_width=True)

# ─── KPIs ─────────────────────────────────────────────────────────────────────
st.markdown("### 📊 Live KPIs")
wait_times = st.session_state.wait_times
occupancy  = st.session_state.occupancy
avg_wait   = sum(wait_times.values()) / len(wait_times)
badge = '<span class="rl-badge">🤖 RL ACTIVE</span>' if st.session_state.mode == "rl" else '<span class="static-badge">📋 STATIC</span>'

m1, m2, m3, m4, m5 = st.columns(5)
with m1: st.metric("⏱️ Avg Wait Time", f"{avg_wait:.1f} min", delta=f"{avg_wait-10:.1f} vs baseline", delta_color="inverse")
with m2: st.metric("🚌 Fleet Deployed", f"{st.session_state.fleet_used} buses", delta="of 120 total")
with m3: st.metric("👥 Passengers Served", f"{st.session_state.passengers_served:,}")
with m4: st.metric("🕐 Sim Time", f"{st.session_state.hour:02d}:{st.session_state.minute:02d}")
with m5: st.metric("⚠️ Equity Violations", st.session_state.equity_violations,
                    delta="✅ All OK" if st.session_state.equity_violations == 0 else "peripheral routes",
                    delta_color="inverse")

st.markdown(f"**Current Mode:** {badge}", unsafe_allow_html=True)
st.markdown("---")

# ─── Route Table ─────────────────────────────────────────────────────────────
st.markdown("### 🗺️ Route-Level Status")
table_rows = []
for r in ROUTES:
    rid = r["id"]
    wt   = wait_times[rid]
    occ  = occupancy[rid]
    buses = st.session_state.buses[rid]
    status = "🔴 DISRUPTED" if rid in st.session_state.disrupted else ("🟡 HIGH LOAD" if occ > 0.9 else "🟢 Normal")
    table_rows.append({
        "Route": r["name"], "Type": "⚠️ Peripheral" if r["is_peripheral"] else "Central",
        "Buses": buses, "Wait (min)": wt, "Occupancy": f"{occ*100:.0f}%", "Status": status,
    })

df = pd.DataFrame(table_rows)

def color_wait(val):
    if val > 12: return "color:#ff4444;font-weight:700"
    elif val > 8: return "color:#ffaa00"
    return "color:#00ff88"

def color_occ(val):
    pct = float(val.replace("%",""))
    if pct < 40: return "color:#ff4444;font-weight:700"
    elif pct > 90: return "color:#ffaa00;font-weight:700"
    return "color:#00ff88"

st.dataframe(df.style.map(color_wait, subset=["Wait (min)"]).map(color_occ, subset=["Occupancy"]),
             use_container_width=True, hide_index=True)

# ─── Performance Charts ───────────────────────────────────────────────────────
st.markdown("### 📈 Performance Trends")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**Average Wait Time Over Simulation**")
    if len(st.session_state.wait_history) > 1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=st.session_state.wait_history, mode="lines+markers",
                                  line=dict(color="#00d4ff", width=2), marker=dict(size=4),
                                  fill="tozeroy", fillcolor="rgba(0,212,255,0.1)"))
        fig.add_hline(y=10, line_dash="dash", line_color="#ff6b35", annotation_text="Static Baseline")
        fig.update_layout(paper_bgcolor="#0d1220", plot_bgcolor="#0d1220", font=dict(color="#8892b0"),
                          xaxis=dict(gridcolor="#1a2040"), yaxis=dict(gridcolor="#1a2040", title="Wait (min)"),
                          margin=dict(l=40,r=20,t=20,b=40), height=280)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run simulation steps to see trend...")

with chart_col2:
    st.markdown("**Buses Per Route (Current Allocation)**")
    r_labels = [r["name"].split("→")[0].strip() for r in ROUTES]
    bus_vals  = [st.session_state.buses[r["id"]] for r in ROUTES]
    colors    = ["#ff6b35" if r["is_peripheral"] else "#00d4ff" for r in ROUTES]
    fig2 = go.Figure(go.Bar(x=r_labels, y=bus_vals, marker_color=colors,
                             text=bus_vals, textposition="outside"))
    fig2.update_layout(paper_bgcolor="#0d1220", plot_bgcolor="#0d1220", font=dict(color="#8892b0"),
                       xaxis=dict(gridcolor="#1a2040", tickangle=-30),
                       yaxis=dict(gridcolor="#1a2040", title="Buses"),
                       margin=dict(l=40,r=20,t=20,b=80), height=280)
    st.plotly_chart(fig2, use_container_width=True)

# ─── Demand Analysis ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🚌 Passenger Demand Analysis & Bus Utilisation")
demand_col1, demand_col2 = st.columns(2)

with demand_col1:
    st.markdown("**Empty vs Overcrowded Buses**")
    occ_vals   = [round(occupancy[r["id"]] * 100, 1) for r in ROUTES]
    bar_colors = ["#ff4444" if v < 40 else ("#ffaa00" if v > 90 else "#00ff88") for v in occ_vals]
    fig_occ = go.Figure(go.Bar(x=r_labels, y=occ_vals, marker_color=bar_colors,
                                text=[f"{v}%" for v in occ_vals], textposition="outside"))
    fig_occ.add_hline(y=40, line_dash="dash", line_color="#ff4444", annotation_text="Empty (<40%)")
    fig_occ.add_hline(y=90, line_dash="dash", line_color="#ffaa00", annotation_text="Overcrowded (>90%)")
    fig_occ.update_layout(paper_bgcolor="#0d1220", plot_bgcolor="#0d1220", font=dict(color="#8892b0"),
                          xaxis=dict(gridcolor="#1a2040", tickangle=-30),
                          yaxis=dict(gridcolor="#1a2040", title="Occupancy %", range=[0,130]),
                          margin=dict(l=40,r=20,t=20,b=80), height=300)
    st.plotly_chart(fig_occ, use_container_width=True)
    st.markdown("🔴 Empty (<40%) &nbsp;&nbsp; 🟠 Overcrowded (>90%) &nbsp;&nbsp; 🟢 Optimal", unsafe_allow_html=True)

with demand_col2:
    st.markdown("**Passenger Demand vs Bus Capacity**")
    demand_vals = [r["base_demand"] for r in ROUTES]
    capacity_vals = [st.session_state.buses[r["id"]] * 60 for r in ROUTES]
    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(name="Passenger Demand", x=r_labels, y=demand_vals,
                            marker_color="#00d4ff", opacity=0.85))
    fig_d.add_trace(go.Bar(name="Bus Capacity", x=r_labels, y=capacity_vals,
                            marker_color="#ff6b35", opacity=0.85))
    fig_d.update_layout(barmode="group", paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
                        font=dict(color="#8892b0"),
                        xaxis=dict(gridcolor="#1a2040", tickangle=-30),
                        yaxis=dict(gridcolor="#1a2040", title="Count"),
                        legend=dict(bgcolor="#1a1f35"), margin=dict(l=40,r=20,t=20,b=80), height=300)
    st.plotly_chart(fig_d, use_container_width=True)

# ─── RL Reallocation Panel ────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔄 RL Agent — Bus Reallocation Decisions")
act_col1, act_col2, act_col3 = st.columns(3)

empty_routes      = [(r["name"], st.session_state.buses[r["id"]], occupancy[r["id"]]*100)
                     for r in ROUTES if occupancy[r["id"]] < 0.4]
high_demand_routes = [(r["name"], st.session_state.buses[r["id"]], wait_times[r["id"]])
                      for r in ROUTES if wait_times[r["id"]] > 10 or occupancy[r["id"]] > 0.85]

with act_col1:
    st.markdown("**🔴 Low Utilisation Routes**")
    if empty_routes:
        for name, buses, occ in empty_routes:
            st.markdown(f"""<div style="background:#1a0f0f;border:1px solid #ff444440;border-radius:8px;
                padding:0.6rem 1rem;margin-bottom:0.5rem;font-size:0.85rem;">
                🚌 <b>{name.split('→')[0].strip()}</b><br>
                <span style="color:#ff4444">{buses} buses · {occ:.0f}% — Underused!</span></div>""",
                unsafe_allow_html=True)
    else:
        st.success("✅ No empty buses!")

with act_col2:
    st.markdown("**🟠 High Demand Routes**")
    if high_demand_routes:
        for name, buses, wt in high_demand_routes:
            st.markdown(f"""<div style="background:#1a1200;border:1px solid #ffaa0040;border-radius:8px;
                padding:0.6rem 1rem;margin-bottom:0.5rem;font-size:0.85rem;">
                🚌 <b>{name.split('→')[0].strip()}</b><br>
                <span style="color:#ffaa00">{buses} buses · {wt:.1f} min wait!</span></div>""",
                unsafe_allow_html=True)
    else:
        st.success("✅ All routes balanced!")

with act_col3:
    st.markdown("**🤖 RL Decision**")
    if empty_routes and high_demand_routes:
        fr = empty_routes[0][0].split("→")[0].strip()
        to = high_demand_routes[0][0].split("→")[0].strip()
        st.markdown(f"""<div style="background:#0f1a0f;border:1px solid #00ff8840;border-radius:8px;
            padding:0.8rem 1rem;font-size:0.85rem;">
            ✅ <b>Action Taken:</b><br><br>
            <span style="color:#ff4444">📤 {fr}</span><br>
            <span style="color:#8892b0;font-size:1.2rem;margin-left:1rem;">↓ Move 1 bus</span><br>
            <span style="color:#00ff88">📥 {to}</span><br><br>
            <span style="color:#00d4ff">⚡ Wait time reduced · Fleet optimised</span></div>""",
            unsafe_allow_html=True)
    elif st.session_state.mode == "static":
        st.warning("📋 Static mode — No reallocation!")
    else:
        st.success("✅ Fleet optimally distributed!")

# ─── Compare Chart ────────────────────────────────────────────────────────────
if compare_clicked:
    st.markdown("---")
    st.markdown("### ⚔️ Static vs RL Agent — 24-Hour Comparison")
    compare = get_compare_data()
    static_df = pd.DataFrame(compare["static"])
    rl_df     = pd.DataFrame(compare["rl"])
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=static_df["hour"], y=static_df["avg_wait"],
                               name="Static Schedule", mode="lines+markers",
                               line=dict(color="#ff6b35", width=3, dash="dot"), marker=dict(size=6)))
    fig3.add_trace(go.Scatter(x=rl_df["hour"], y=rl_df["avg_wait"],
                               name="RL Agent", mode="lines+markers",
                               line=dict(color="#00d4ff", width=3), marker=dict(size=6),
                               fill="tonexty", fillcolor="rgba(0,212,255,0.08)"))
    fig3.add_vrect(x0=7, x1=9,   fillcolor="rgba(255,200,0,0.07)", annotation_text="Morning Peak", line_width=0)
    fig3.add_vrect(x0=17, x1=19, fillcolor="rgba(255,200,0,0.07)", annotation_text="Evening Peak",  line_width=0)
    fig3.update_layout(paper_bgcolor="#0d1220", plot_bgcolor="#0d1220", font=dict(color="#8892b0", size=13),
                       xaxis=dict(gridcolor="#1a2040", title="Hour of Day", dtick=1),
                       yaxis=dict(gridcolor="#1a2040", title="Avg Wait Time (min)"),
                       legend=dict(bgcolor="#1a1f35", bordercolor="#2a3050"),
                       height=380, margin=dict(l=50,r=30,t=30,b=50))
    st.plotly_chart(fig3, use_container_width=True)

    static_avg   = sum(d["avg_wait"] for d in compare["static"]) / len(compare["static"])
    rl_avg       = sum(d["avg_wait"] for d in compare["rl"])     / len(compare["rl"])
    improvement  = ((static_avg - rl_avg) / static_avg) * 100
    c1, c2, c3 = st.columns(3)
    c1.metric("📋 Static Avg Wait", f"{static_avg:.1f} min")
    c2.metric("🤖 RL Avg Wait",     f"{rl_avg:.1f} min")
    c3.metric("📉 Improvement",     f"{improvement:.1f}%", delta="better with RL")

# ─── Reward Chart ─────────────────────────────────────────────────────────────
if len(st.session_state.reward_history) > 1:
    st.markdown("---")
    st.markdown("### 🎯 RL Reward Signal")
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(y=st.session_state.reward_history, mode="lines",
                               line=dict(color="#00ff88", width=2),
                               fill="tozeroy", fillcolor="rgba(0,255,136,0.07)"))
    fig4.update_layout(paper_bgcolor="#0d1220", plot_bgcolor="#0d1220", font=dict(color="#8892b0"),
                       xaxis=dict(gridcolor="#1a2040", title="Step"),
                       yaxis=dict(gridcolor="#1a2040", title="Reward"),
                       height=220, margin=dict(l=40,r=20,t=20,b=40))
    st.plotly_chart(fig4, use_container_width=True)

# ─── Auto Step ────────────────────────────────────────────────────────────────
if auto_step:
    time.sleep(step_speed)
    simulation_step()
    st.rerun()
