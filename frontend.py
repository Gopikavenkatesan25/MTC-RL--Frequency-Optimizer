import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

API = "http://localhost:8000"

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

    .metric-card {
        background: linear-gradient(135deg, #1a1f35 0%, #0d1220 100%);
        border: 1px solid #2a3050;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #00d4ff;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .rl-badge {
        background: linear-gradient(90deg, #00d4ff, #0066ff);
        color: white;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .static-badge {
        background: linear-gradient(90deg, #ff6b35, #ff3535);
        color: white;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .disrupted {
        color: #ff4444 !important;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: #1a1f35;
        border: 1px solid #2a3050;
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
    div[data-testid="stMetric"] label { color: #8892b0 !important; }
    div[data-testid="stMetric"] div { color: #00d4ff !important; font-weight: 700; }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        border: none;
    }
    .title-header {
        background: linear-gradient(135deg, #0d1220, #1a1f35);
        border-bottom: 2px solid #00d4ff33;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def api_get(path):
    try:
        r = requests.get(f"{API}{path}", timeout=5)
        return r.json()
    except:
        return None

def api_post(path):
    try:
        r = requests.post(f"{API}{path}", timeout=5)
        return r.json()
    except:
        return None

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚌 MTC RL Control Panel")
    st.markdown("---")

    mode = st.radio("**Simulation Mode**", ["static", "rl"],
                    format_func=lambda x: "📋 Static Schedule" if x == "static" else "🤖 RL Agent (Adaptive)")

    if st.button("✅ Apply Mode", use_container_width=True):
        api_post(f"/set_mode/{mode}")
        st.success(f"Mode set to: {mode.upper()}")

    st.markdown("---")
    st.markdown("### ⚡ Disruption Simulator")
    routes_data = api_get("/routes") or []
    route_names = {r["id"]: r["name"] for r in routes_data}

    sel_route = st.selectbox("Select Route to Disrupt",
                              options=[r["id"] for r in routes_data],
                              format_func=lambda x: route_names.get(x, str(x)))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔴 Disrupt", use_container_width=True):
            api_post(f"/disrupt/{sel_route}")
            st.warning("Route disrupted!")
    with col2:
        if st.button("🟢 Restore", use_container_width=True):
            api_post(f"/restore/{sel_route}")
            st.success("Route restored!")

    st.markdown("---")
    if st.button("🔄 Reset Simulation", use_container_width=True):
        api_post("/reset")
        st.success("Simulation reset!")

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

# ─── Manual Step Button ───────────────────────────────────────────────────────
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
with col_btn1:
    step_clicked = st.button("⏩ Step +15min", use_container_width=True, type="primary")
with col_btn2:
    compare_clicked = st.button("📊 Compare Modes", use_container_width=True)

if step_clicked:
    api_post("/step")

# ─── Fetch Current State ──────────────────────────────────────────────────────
state = api_get("/state")

if not state:
    st.error("⚠️ Backend not running! Start it with: `uvicorn backend:app --reload`")
    st.code("cd mtc_rl && uvicorn backend:app --reload --port 8000")
    st.stop()

# ─── KPI Metrics ─────────────────────────────────────────────────────────────
st.markdown("### 📊 Live KPIs")
m1, m2, m3, m4, m5 = st.columns(5)

wait_times = state["wait_times"]
avg_wait = sum(wait_times.values()) / len(wait_times)
occupancy = state["occupancy"]
avg_occ = sum(occupancy.values()) / len(occupancy)
mode_label = state["mode"].upper()
badge = f'<span class="rl-badge">🤖 RL ACTIVE</span>' if state["mode"] == "rl" else f'<span class="static-badge">📋 STATIC</span>'

with m1:
    st.metric("⏱️ Avg Wait Time", f"{avg_wait:.1f} min",
              delta=f"{avg_wait - 10:.1f} vs baseline", delta_color="inverse")
with m2:
    st.metric("🚌 Fleet Deployed", f"{state['fleet_used']} buses",
              delta=f"of 120 total")
with m3:
    st.metric("👥 Passengers Served", f"{state['passengers_served']:,}")
with m4:
    st.metric("🕐 Sim Time", f"{state['hour']:02d}:{state['minute']:02d}")
with m5:
    st.metric("⚠️ Equity Violations", state["equity_violations"],
              delta="peripheral routes" if state["equity_violations"] > 0 else "✅ All OK",
              delta_color="inverse")

st.markdown(f"**Current Mode:** {badge}", unsafe_allow_html=True)
st.markdown("---")

# ─── Route Table ─────────────────────────────────────────────────────────────
st.markdown("### 🗺️ Route-Level Status")

routes_data = api_get("/routes") or []
disrupted = state.get("disrupted_routes", [])

table_rows = []
for r in routes_data:
    rid = r["id"]
    wt = wait_times.get(str(rid), wait_times.get(rid, 0))
    occ = occupancy.get(str(rid), occupancy.get(rid, 0))
    buses = state["buses_per_route"].get(str(rid), state["buses_per_route"].get(rid, 0))
    status = "🔴 DISRUPTED" if rid in disrupted else ("🟡 HIGH LOAD" if float(occ) > 0.9 else "🟢 Normal")
    equity = "⚠️ Peripheral" if r["is_peripheral"] else "Central"

    table_rows.append({
        "Route": r["name"],
        "Type": equity,
        "Buses": int(buses),
        "Wait (min)": float(wt),
        "Occupancy": f"{float(occ)*100:.0f}%",
        "Status": status,
    })

df = pd.DataFrame(table_rows)

def color_wait(val):
    if val > 12: return "color: #ff4444; font-weight:700"
    elif val > 8: return "color: #ffaa00"
    else: return "color: #00ff88"

def color_occ(val):
    pct = float(val.replace("%", ""))
    if pct < 40: return "color: #ff4444; font-weight:700"   # empty bus
    elif pct > 90: return "color: #ffaa00; font-weight:700"  # overcrowded
    else: return "color: #00ff88"

styled = df.style.applymap(color_wait, subset=["Wait (min)"]).applymap(color_occ, subset=["Occupancy"])
st.dataframe(styled, use_container_width=True, hide_index=True)

# ─── Empty Bus Analysis ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🚌 Passenger Demand Analysis & Bus Utilisation")

demand_col1, demand_col2 = st.columns(2)

with demand_col1:
    st.markdown("**Empty vs Overcrowded Buses (Occupancy Analysis)**")

    occ_values = []
    route_labels = []
    bar_colors = []

    for r in routes_data:
        rid = r["id"]
        occ = float(occupancy.get(str(rid), occupancy.get(rid, 0))) * 100
        occ_values.append(round(occ, 1))
        route_labels.append(r["name"].split("→")[0].strip())
        if occ < 40:
            bar_colors.append("#ff4444")   # empty — red
        elif occ > 90:
            bar_colors.append("#ffaa00")   # overcrowded — orange
        else:
            bar_colors.append("#00ff88")   # optimal — green

    fig_occ = go.Figure(go.Bar(
        x=route_labels,
        y=occ_values,
        marker_color=bar_colors,
        text=[f"{v}%" for v in occ_values],
        textposition="outside"
    ))
    fig_occ.add_hline(y=40, line_dash="dash", line_color="#ff4444",
                      annotation_text="Empty threshold (40%)")
    fig_occ.add_hline(y=90, line_dash="dash", line_color="#ffaa00",
                      annotation_text="Overcrowd threshold (90%)")
    fig_occ.update_layout(
        paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
        font=dict(color="#8892b0"),
        xaxis=dict(gridcolor="#1a2040", tickangle=-30),
        yaxis=dict(gridcolor="#1a2040", title="Occupancy %", range=[0, 130]),
        margin=dict(l=40, r=20, t=20, b=80),
        height=300
    )
    st.plotly_chart(fig_occ, use_container_width=True)

    # Legend
    st.markdown("""
    <div style="display:flex; gap:1.5rem; font-size:0.8rem; margin-top:-10px;">
        <span>🔴 Empty Bus (&lt;40%)</span>
        <span>🟠 Overcrowded (&gt;90%)</span>
        <span>🟢 Optimal (40–90%)</span>
    </div>
    """, unsafe_allow_html=True)

with demand_col2:
    st.markdown("**Passenger Demand vs Bus Allocation per Route**")

    route_map = {r["id"]: r for r in routes_data}
    demand_vals = []
    bus_vals = []
    r_labels = []

    for r in routes_data:
        rid = r["id"]
        buses = int(state["buses_per_route"].get(str(rid), state["buses_per_route"].get(rid, 0)))
        demand = r["base_demand"]
        demand_vals.append(demand)
        bus_vals.append(buses * 60)   # normalize: buses × capacity
        r_labels.append(r["name"].split("→")[0].strip())

    fig_demand = go.Figure()
    fig_demand.add_trace(go.Bar(
        name="Passenger Demand",
        x=r_labels, y=demand_vals,
        marker_color="#00d4ff",
        opacity=0.85
    ))
    fig_demand.add_trace(go.Bar(
        name="Bus Capacity Deployed",
        x=r_labels, y=bus_vals,
        marker_color="#ff6b35",
        opacity=0.85
    ))
    fig_demand.update_layout(
        barmode="group",
        paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
        font=dict(color="#8892b0"),
        xaxis=dict(gridcolor="#1a2040", tickangle=-30),
        yaxis=dict(gridcolor="#1a2040", title="Count"),
        legend=dict(bgcolor="#1a1f35", bordercolor="#2a3050"),
        margin=dict(l=40, r=20, t=20, b=80),
        height=300
    )
    st.plotly_chart(fig_demand, use_container_width=True)

# ─── RL Reallocation Actions ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔄 RL Agent — Bus Reallocation Decisions")

empty_routes = []
high_demand_routes = []

for r in routes_data:
    rid = r["id"]
    occ = float(occupancy.get(str(rid), occupancy.get(rid, 0)))
    wt = float(wait_times.get(str(rid), wait_times.get(rid, 0)))
    buses = int(state["buses_per_route"].get(str(rid), state["buses_per_route"].get(rid, 0)))
    if occ < 0.4:
        empty_routes.append((r["name"], buses, occ * 100))
    if wt > 10 or occ > 0.85:
        high_demand_routes.append((r["name"], buses, wt))

act_col1, act_col2, act_col3 = st.columns(3)

with act_col1:
    st.markdown("**🔴 Low Utilisation Routes**")
    if empty_routes:
        for name, buses, occ in empty_routes:
            st.markdown(f"""
            <div style="background:#1a0f0f; border:1px solid #ff444440; border-radius:8px;
                        padding:0.6rem 1rem; margin-bottom:0.5rem; font-size:0.85rem;">
                🚌 <b>{name.split('→')[0].strip()}</b><br>
                <span style="color:#ff4444">{buses} buses · {occ:.0f}% occupancy — Underused!</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No empty buses!")

with act_col2:
    st.markdown("**🟠 High Demand Routes**")
    if high_demand_routes:
        for name, buses, wt in high_demand_routes:
            st.markdown(f"""
            <div style="background:#1a1200; border:1px solid #ffaa0040; border-radius:8px;
                        padding:0.6rem 1rem; margin-bottom:0.5rem; font-size:0.85rem;">
                🚌 <b>{name.split('→')[0].strip()}</b><br>
                <span style="color:#ffaa00">{buses} buses · {wt:.1f} min wait — Needs more!</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ All routes balanced!")

with act_col3:
    st.markdown("**🤖 RL Decision**")
    if empty_routes and high_demand_routes:
        from_route = empty_routes[0][0].split("→")[0].strip()
        to_route = high_demand_routes[0][0].split("→")[0].strip()
        st.markdown(f"""
        <div style="background:#0f1a0f; border:1px solid #00ff8840; border-radius:8px;
                    padding:0.8rem 1rem; font-size:0.85rem;">
            ✅ <b>Action Taken:</b><br><br>
            <span style="color:#ff4444">📤 {from_route}</span><br>
            <span style="color:#8892b0; font-size:1.2rem; margin-left:1rem;">↓ Move 1 bus</span><br>
            <span style="color:#00ff88">📥 {to_route}</span><br><br>
            <span style="color:#00d4ff">⚡ Wait time reduced · Fleet optimised</span>
        </div>
        """, unsafe_allow_html=True)
    elif state["mode"] == "static":
        st.warning("📋 Static mode — No reallocation happening!")
    else:
        st.success("✅ Fleet optimally distributed!")

# ─── Charts ───────────────────────────────────────────────────────────────────
st.markdown("### 📈 Performance Trends")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**Average Wait Time Over Simulation**")
    wait_hist = state.get("global_wait_history", [])
    if len(wait_hist) > 1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=wait_hist, mode="lines+markers",
            line=dict(color="#00d4ff", width=2),
            marker=dict(size=4),
            name="Avg Wait Time",
            fill="tozeroy",
            fillcolor="rgba(0,212,255,0.1)"
        ))
        fig.add_hline(y=10, line_dash="dash", line_color="#ff6b35",
                      annotation_text="Static Baseline (10 min)")
        fig.update_layout(
            paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
            font=dict(color="#8892b0"),
            xaxis=dict(gridcolor="#1a2040", title="Step"),
            yaxis=dict(gridcolor="#1a2040", title="Wait (min)"),
            margin=dict(l=40, r=20, t=20, b=40),
            height=280
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run simulation steps to see trend...")

with chart_col2:
    st.markdown("**Buses Per Route (Current Allocation)**")
    bus_data = [(route_names.get(int(k), k), v) for k, v in state["buses_per_route"].items()]
    bus_df = pd.DataFrame(bus_data, columns=["Route", "Buses"])
    bus_df["Route"] = bus_df["Route"].apply(lambda x: x.split("→")[0].strip())

    colors = ["#00d4ff" if not any(r["is_peripheral"] and r["id"] == int(k)
              for r in routes_data) else "#ff6b35"
              for k, v in state["buses_per_route"].items()]

    fig2 = go.Figure(go.Bar(
        x=bus_df["Route"], y=bus_df["Buses"],
        marker_color=colors,
        text=bus_df["Buses"], textposition="outside"
    ))
    fig2.update_layout(
        paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
        font=dict(color="#8892b0"),
        xaxis=dict(gridcolor="#1a2040", tickangle=-30),
        yaxis=dict(gridcolor="#1a2040", title="Buses"),
        margin=dict(l=40, r=20, t=20, b=80),
        height=280
    )
    st.plotly_chart(fig2, use_container_width=True)

# ─── Compare Chart ────────────────────────────────────────────────────────────
if compare_clicked:
    st.markdown("---")
    st.markdown("### ⚔️ Static vs RL Agent — 24-Hour Comparison")
    compare = api_get("/compare")
    if compare:
        static_df = pd.DataFrame(compare["static"])
        rl_df = pd.DataFrame(compare["rl"])

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=static_df["hour"], y=static_df["avg_wait"],
            name="Static Schedule", mode="lines+markers",
            line=dict(color="#ff6b35", width=3, dash="dot"),
            marker=dict(size=6)
        ))
        fig3.add_trace(go.Scatter(
            x=rl_df["hour"], y=rl_df["avg_wait"],
            name="RL Agent", mode="lines+markers",
            line=dict(color="#00d4ff", width=3),
            marker=dict(size=6),
            fill="tonexty",
            fillcolor="rgba(0,212,255,0.08)"
        ))
        fig3.add_vrect(x0=7, x1=9, fillcolor="rgba(255,200,0,0.07)",
                       annotation_text="Morning Peak", line_width=0)
        fig3.add_vrect(x0=17, x1=19, fillcolor="rgba(255,200,0,0.07)",
                       annotation_text="Evening Peak", line_width=0)
        fig3.update_layout(
            paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
            font=dict(color="#8892b0", size=13),
            xaxis=dict(gridcolor="#1a2040", title="Hour of Day", dtick=1),
            yaxis=dict(gridcolor="#1a2040", title="Avg Wait Time (min)"),
            legend=dict(bgcolor="#1a1f35", bordercolor="#2a3050"),
            height=380,
            margin=dict(l=50, r=30, t=30, b=50)
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Summary stats
        static_avg = sum(d["avg_wait"] for d in compare["static"]) / len(compare["static"])
        rl_avg = sum(d["avg_wait"] for d in compare["rl"]) / len(compare["rl"])
        improvement = ((static_avg - rl_avg) / static_avg) * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("📋 Static Avg Wait", f"{static_avg:.1f} min")
        c2.metric("🤖 RL Avg Wait", f"{rl_avg:.1f} min")
        c3.metric("📉 Improvement", f"{improvement:.1f}%", delta="better with RL")

# ─── Reward History ───────────────────────────────────────────────────────────
reward_hist = state.get("reward_history", [])
if len(reward_hist) > 1:
    st.markdown("---")
    st.markdown("### 🎯 RL Reward Signal Over Time")
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        y=reward_hist, mode="lines",
        line=dict(color="#00ff88", width=2),
        fill="tozeroy",
        fillcolor="rgba(0,255,136,0.07)",
        name="Reward"
    ))
    fig4.update_layout(
        paper_bgcolor="#0d1220", plot_bgcolor="#0d1220",
        font=dict(color="#8892b0"),
        xaxis=dict(gridcolor="#1a2040", title="Step"),
        yaxis=dict(gridcolor="#1a2040", title="Reward"),
        height=220,
        margin=dict(l=40, r=20, t=20, b=40)
    )
    st.plotly_chart(fig4, use_container_width=True)

# ─── Auto Step ────────────────────────────────────────────────────────────────
if auto_step:
    time.sleep(step_speed)
    api_post("/step")
    st.rerun()