from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import math
from typing import List, Dict, Optional

app = FastAPI(title="MTC Chennai RL Bus Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MTC Route Data ───────────────────────────────────────────────────────────
ROUTES = [
    {"id": 1, "name": "Broadway → Tambaram",        "stops": 22, "base_demand": 850, "is_peripheral": False, "lat": 13.0827, "lon": 80.2707},
    {"id": 2, "name": "Koyambedu → Sholinganallur", "stops": 18, "base_demand": 720, "is_peripheral": False, "lat": 13.0694, "lon": 80.1948},
    {"id": 3, "name": "CMBT → Ambattur",             "stops": 14, "base_demand": 680, "is_peripheral": False, "lat": 13.0732, "lon": 80.1925},
    {"id": 4, "name": "Anna Nagar → Chrompet",       "stops": 16, "base_demand": 590, "is_peripheral": False, "lat": 13.0850, "lon": 80.2101},
    {"id": 5, "name": "Avadi → Broadway",             "stops": 20, "base_demand": 410, "is_peripheral": True,  "lat": 13.1149, "lon": 80.1005},
    {"id": 6, "name": "Poonamallee → Central",       "stops": 15, "base_demand": 380, "is_peripheral": True,  "lat": 13.0468, "lon": 80.1168},
    {"id": 7, "name": "Redhills → T.Nagar",           "stops": 19, "base_demand": 340, "is_peripheral": True,  "lat": 13.1899, "lon": 80.1833},
    {"id": 8, "name": "Madhavaram → Guindy",          "stops": 17, "base_demand": 460, "is_peripheral": False, "lat": 13.1481, "lon": 80.2310},
]

TOTAL_FLEET = 120
MIN_PERIPHERAL_BUSES = 3
MIN_CENTRAL_BUSES = 4

# ─── Simulation State ─────────────────────────────────────────────────────────
sim_state = {
    "hour": 8,
    "minute": 0,
    "step": 0,
    "mode": "static",
    "buses_per_route": {r["id"]: 8 for r in ROUTES},
    "wait_times": {r["id"]: 10.0 for r in ROUTES},
    "occupancy": {r["id"]: 0.5 for r in ROUTES},
    "disrupted_routes": [],
    "passengers_served": 0,
    "equity_violations": 0,
    "history": {r["id"]: [] for r in ROUTES},
    "global_wait_history": [],
    "reward_history": [],
    "fleet_used": 64,
}

# ─── Demand Model ─────────────────────────────────────────────────────────────
def get_demand_multiplier(hour: int, route_id: int) -> float:
    base_profile = {
        6: 0.5, 7: 1.2, 8: 2.0, 9: 1.7, 10: 1.0,
        11: 0.9, 12: 1.2, 13: 1.3, 14: 0.8, 15: 0.9,
        16: 1.4, 17: 1.9, 18: 2.1, 19: 1.5, 20: 1.0,
        21: 0.7, 22: 0.4, 23: 0.2,
    }
    multiplier = base_profile.get(hour, 0.5)
    noise = random.uniform(0.9, 1.1)
    if route_id in sim_state["disrupted_routes"]:
        multiplier *= 1.6  # demand spikes when service disrupted
    return multiplier * noise

def compute_wait_time(buses: int, demand_multiplier: float, capacity: int = 60) -> float:
    if buses <= 0:
        return 45.0
    effective_freq = buses  # buses per hour
    base_wait = 60.0 / effective_freq  # avg headway in minutes
    load_factor = (demand_multiplier * capacity) / (buses * capacity)
    load_factor = min(load_factor, 2.5)
    wait = base_wait * (1 + 0.4 * max(0, load_factor - 1.0))
    return round(min(max(wait, 1.0), 45.0), 2)

def compute_occupancy(buses: int, demand_multiplier: float, base_demand: int) -> float:
    if buses <= 0:
        return 1.0
    passengers_per_hour = base_demand * demand_multiplier
    capacity_per_hour = buses * 60 * (60 / max(buses, 1))
    occ = passengers_per_hour / (buses * 60)
    return round(min(max(occ, 0.1), 1.5), 2)

# ─── Rule-Based RL Agent ──────────────────────────────────────────────────────
def rl_agent_action(state: dict) -> dict:
    """
    Simple rule-based agent that mimics RL policy:
    - Observes wait times and occupancy per route
    - Reallocates buses from low-demand to high-demand routes
    - Respects equity constraints (min buses on peripheral routes)
    - Respects total fleet constraint
    """
    hour = state["hour"]
    buses = dict(state["buses_per_route"])
    wait_times = state["wait_times"]
    occupancy = state["occupancy"]
    disrupted = state["disrupted_routes"]

    demand_mults = {r["id"]: get_demand_multiplier(hour, r["id"]) for r in ROUTES}
    route_map = {r["id"]: r for r in ROUTES}

    # Score each route: higher = needs more buses
    scores = {}
    for r in ROUTES:
        rid = r["id"]
        score = (wait_times[rid] * 0.5) + (occupancy[rid] * 10) + (demand_mults[rid] * 5)
        if rid in disrupted:
            score *= 1.5
        scores[rid] = score

    # Sort routes by need
    sorted_by_need = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    sorted_by_low  = sorted(scores.keys(), key=lambda x: scores[x])

    actions_taken = []

    # Try to move buses from lowest-need to highest-need
    for low_id in sorted_by_low:
        low_route = route_map[low_id]
        min_buses = MIN_PERIPHERAL_BUSES if low_route["is_peripheral"] else MIN_CENTRAL_BUSES
        if buses[low_id] > min_buses:
            for high_id in sorted_by_need:
                if high_id == low_id:
                    continue
                if wait_times[high_id] > 8 or occupancy[high_id] > 0.85:
                    buses[low_id] -= 1
                    buses[high_id] += 1
                    actions_taken.append(f"Moved 1 bus: Route {low_id} → Route {high_id}")
                    break

    # Check equity violations
    equity_violations = 0
    for r in ROUTES:
        rid = r["id"]
        min_b = MIN_PERIPHERAL_BUSES if r["is_peripheral"] else MIN_CENTRAL_BUSES
        if buses[rid] < min_b:
            buses[rid] = min_b
            equity_violations += 1

    return {"buses_per_route": buses, "actions": actions_taken, "equity_violations": equity_violations}

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "MTC RL Backend Running"}

@app.get("/routes")
def get_routes():
    return ROUTES

@app.get("/state")
def get_state():
    return sim_state

@app.post("/set_mode/{mode}")
def set_mode(mode: str):
    sim_state["mode"] = mode
    return {"mode": mode}

@app.post("/step")
def simulation_step():
    hour = sim_state["hour"]
    mode = sim_state["mode"]

    # Static mode: fixed 8 buses per route
    if mode == "static":
        buses = {r["id"]: 8 for r in ROUTES}
    else:
        # RL agent decides
        result = rl_agent_action(sim_state)
        buses = result["buses_per_route"]
        sim_state["equity_violations"] += result["equity_violations"]

    sim_state["buses_per_route"] = buses

    total_wait = 0
    total_passengers = 0
    reward = 0

    for r in ROUTES:
        rid = r["id"]
        dm = get_demand_multiplier(hour, rid)
        wt = compute_wait_time(buses[rid], dm)
        occ = compute_occupancy(buses[rid], dm, r["base_demand"])

        sim_state["wait_times"][rid] = wt
        sim_state["occupancy"][rid] = occ

        passengers = int(r["base_demand"] * dm * (1 - min(wt / 45.0, 0.9)))
        total_passengers += passengers
        total_wait += wt

        sim_state["history"][rid].append({
            "step": sim_state["step"],
            "hour": hour,
            "wait_time": wt,
            "occupancy": occ,
            "buses": buses[rid],
        })

    avg_wait = total_wait / len(ROUTES)
    fleet_used = sum(buses.values())

    reward = -avg_wait + (total_passengers / 1000) - (sim_state["equity_violations"] * 2)

    sim_state["passengers_served"] += total_passengers
    sim_state["global_wait_history"].append(round(avg_wait, 2))
    sim_state["reward_history"].append(round(reward, 2))
    sim_state["fleet_used"] = fleet_used
    sim_state["step"] += 1

    # Advance time
    sim_state["minute"] += 15
    if sim_state["minute"] >= 60:
        sim_state["minute"] = 0
        sim_state["hour"] = (sim_state["hour"] + 1) % 24

    return {
        "step": sim_state["step"],
        "hour": hour,
        "avg_wait_time": round(avg_wait, 2),
        "total_passengers": total_passengers,
        "fleet_used": fleet_used,
        "reward": round(reward, 2),
    }

@app.post("/disrupt/{route_id}")
def disrupt_route(route_id: int):
    if route_id not in sim_state["disrupted_routes"]:
        sim_state["disrupted_routes"].append(route_id)
    return {"disrupted": sim_state["disrupted_routes"]}

@app.post("/restore/{route_id}")
def restore_route(route_id: int):
    if route_id in sim_state["disrupted_routes"]:
        sim_state["disrupted_routes"].remove(route_id)
    return {"disrupted": sim_state["disrupted_routes"]}

@app.post("/reset")
def reset():
    sim_state["hour"] = 8
    sim_state["minute"] = 0
    sim_state["step"] = 0
    sim_state["buses_per_route"] = {r["id"]: 8 for r in ROUTES}
    sim_state["wait_times"] = {r["id"]: 10.0 for r in ROUTES}
    sim_state["occupancy"] = {r["id"]: 0.5 for r in ROUTES}
    sim_state["disrupted_routes"] = []
    sim_state["passengers_served"] = 0
    sim_state["equity_violations"] = 0
    sim_state["history"] = {r["id"]: [] for r in ROUTES}
    sim_state["global_wait_history"] = []
    sim_state["reward_history"] = []
    sim_state["fleet_used"] = 64
    return {"status": "reset done"}

@app.get("/compare")
def compare_modes():
    """Run both static and RL for 24 hours and return comparison"""
    results = {"static": [], "rl": []}

    for mode_name in ["static", "rl"]:
        buses_sim = {r["id"]: 8 for r in ROUTES}
        for hour in range(6, 24):
            total_wait = 0
            if mode_name == "rl":
                temp_state = {
                    "hour": hour,
                    "buses_per_route": buses_sim,
                    "wait_times": {r["id"]: 10.0 for r in ROUTES},
                    "occupancy": {r["id"]: 0.5 for r in ROUTES},
                    "disrupted_routes": [],
                }
                result = rl_agent_action(temp_state)
                buses_sim = result["buses_per_route"]
            else:
                buses_sim = {r["id"]: 8 for r in ROUTES}

            for r in ROUTES:
                rid = r["id"]
                dm = get_demand_multiplier(hour, rid)
                wt = compute_wait_time(buses_sim[rid], dm)
                total_wait += wt

            results[mode_name].append({
                "hour": hour,
                "avg_wait": round(total_wait / len(ROUTES), 2)
            })

    return results