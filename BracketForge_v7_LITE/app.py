# app.py — BracketForge v7.1 (LITE)
# Fixes: Auto-Assign updates the table (session_state), fills roles for all rows.
# Features: CSV upload (+ Excel if enabled), manual roster, regen window, objectives,
# opener reserve, cycles calc, SB/Mag/Grand totals, per-player plan, CSV export.

import io, csv
from typing import List, Dict, Tuple
import streamlit as st

EXCEL_SUPPORT = False

if EXCEL_SUPPORT:
    try:
        import pandas as pd
    except Exception:
        pd = None
else:
    pd = None

st.set_page_config(page_title="BracketForge v7.1", page_icon="⚔️", layout="wide")
st.title("⚔️ BracketForge — War Role Calculator (v7.1, LITE)")

# ----------------------------
# Built-in points matrix (levels 1–20)
# ----------------------------
LEVELS = list(range(1, 21))
MAG_POINTS = [300,330,365,400,440,485,535,590,650,715,785,865,950,1045,1150,1265,1390,1530,1685,1855]
SB_POINTS  = [700,850,1000,1150,1300,1450,1600,1750,1900,2050,2200,2300,2500,2650,2800,2950,3100,3250,3400,3550]
MAG_LOOKUP = {lvl: pts for lvl, pts in zip(LEVELS, MAG_POINTS)}
SB_LOOKUP  = {lvl: pts for lvl, pts in zip(LEVELS, SB_POINTS)}

def pts_mag(level) -> int:
    try: return MAG_LOOKUP.get(int(level), 0)
    except: return 0

def pts_sb(level) -> int:
    try: return SB_LOOKUP.get(int(level), 0)
    except: return 0

# ----------------------------
# Roles & energy
# ----------------------------
ROLE_DEFS = {
    "— Select —":         {"sb": 0, "mag": 0},
    "SB-only (3 SB)":     {"sb": 3, "mag": 0},
    "1 SB + 7 Mag":       {"sb": 1, "mag": 7},
    "2 SB + 3 Mag":       {"sb": 2, "mag": 3},
    "Mag-only (10 Mag)":  {"sb": 0, "mag": 10},
}
ROLES_ORDER = ["SB-only (3 SB)", "1 SB + 7 Mag", "2 SB + 3 Mag", "Mag-only (10 Mag)"]

ENERGY_COST_SB = 7
ENERGY_COST_MAG = 2

# ----------------------------
# Sidebar: setup
# ----------------------------
st.sidebar.header("Setup")

team_size = st.sidebar.number_input("How many players?", min_value=1, max_value=100, value=25, step=1)
duration_min = st.sidebar.number_input("Play window (minutes)", min_value=5, max_value=120, value=30, step=5)

regen_mode = st.sidebar.selectbox("Energy regen", ["Standard (1 per 3 min)", "GLW (1 per 1 min)", "Custom"], index=0)
if regen_mode == "Standard (1 per 3 min)":
    tick_minutes = 3
elif regen_mode == "GLW (1 per 1 min)":
    tick_minutes = 1
else:
    tick_minutes = st.sidebar.number_input("Custom: 1 energy every ... minutes", min_value=1, max_value=10, value=3, step=1)

energy_cap = st.sidebar.number_input("Energy cap per player", min_value=1, max_value=50, value=21, step=1)
start_energy = st.sidebar.number_input("Starting energy per player", min_value=0, max_value=50, value=21, step=1)

reserve_opener = st.sidebar.checkbox("Reserve 6× Mag for opener (kill from 16 HP)", value=True)

objective = st.sidebar.selectbox("Auto-assign objective", ["Max Points", "Max SB casts", "Best Points per Energy"], index=0)
auto_clicked = st.sidebar.button("⚡ Auto-Assign Roles")

with st.sidebar.expander("Points matrix (built-in)"):
    st.table({"Level": LEVELS, "Mag": MAG_POINTS, "SB": SB_POINTS})

# ----------------------------
# Roster I/O
# ----------------------------
DATA_KEY = "roster_data_v7_lite"   # holds the current table content (list of dicts)
WIDGET_KEY = "roster_editor_v7_lite"

def default_roster(n: int):
    return [{"name": f"Player {i}", "sb_level": 0, "mag_level": 0, "role": "— Select —"} for i in range(1, n+1)]

def normalize_rows(rows):
    norm = []
    for r in rows:
        name = str(r.get("name", "")).strip() or ""
        try: sb = int(r.get("sb_level", 0))
        except: sb = 0
        try: mag = int(r.get("mag_level", 0))
        except: mag = 0
        role = r.get("role", "— Select —")
        if role not in ROLE_DEFS: role = "— Select —"
        norm.append({"name": name, "sb_level": sb, "mag_level": mag, "role": role})
    return norm

st.subheader("Roster")

if EXCEL_SUPPORT:
    upload_help = "Upload CSV or Excel. Headers: name, sb_level, mag_level, role (role optional)."
    upload_types = ["csv", "xlsx"]
else:
    upload_help = "Upload CSV (Excel disabled in Lite). Headers: name, sb_level, mag_level, role (role optional)."
    upload_types = ["csv"]

uploaded = st.file_uploader(upload_help, type=upload_types)

# Seed session_state on first run or when team size changes
if DATA_KEY not in st.session_state:
    st.session_state[DATA_KEY] = default_roster(team_size)

# If user uploaded a file, replace session data with file content
try:
    if uploaded:
        filename = uploaded.name.lower()
        if filename.endswith(".csv"):
            text = uploaded.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            raw = [row for row in reader]
            roster_in = normalize_rows(raw)
        elif EXCEL_SUPPORT and filename.endswith(".xlsx"):
            if pd is None:
                st.error("Excel parsing not available. (pandas/openpyxl missing)")
                roster_in = default_roster(team_size)
            else:
                df = pd.read_excel(uploaded)
                rename = {}
                for c in df.columns:
                    lc = str(c).strip().lower()
                    if lc in ("name","sb_level","mag_level","role"):
                        rename[c] = lc
                df = df.rename(columns=rename)
                for col in ["name","sb_level","mag_level"]:
                    if col not in df.columns:
                        df[col] = "" if col=="name" else 0
                if "role" not in df.columns:
                    df["role"] = "— Select —"
                roster_in = normalize_rows(df[["name","sb_level","mag_level","role"]].to_dict("records"))
        else:
            roster_in = default_roster(team_size)
        st.session_state[DATA_KEY] = roster_in
        st.success(f"Loaded roster from file: {len(roster_in)} players.")
        team_size = len(roster_in)
except Exception as e:
    st.error(f"Failed to read file: {e}")

# If team_size was changed manually, resize the roster
current_len = len(st.session_state[DATA_KEY])
if team_size != current_len:
    if team_size > current_len:
        st.session_state[DATA_KEY] += default_roster(team_size - current_len)
    else:
        st.session_state[DATA_KEY] = st.session_state[DATA_KEY][:team_size]

# Render editor using the session-stored data
edited = st.data_editor(
    st.session_state[DATA_KEY],
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "name":      st.column_config.TextColumn("Name", width="medium"),
        "sb_level":  st.column_config.NumberColumn("SB Level", min_value=0, max_value=20, step=1),
        "mag_level": st.column_config.NumberColumn("Mag Level", min_value=0, max_value=20, step=1),
        "role":      st.column_config.SelectboxColumn("Assigned Role", options=["— Select —"] + ROLES_ORDER),
    },
    key=WIDGET_KEY,
)
# Keep manual edits
st.session_state[DATA_KEY] = edited

# ----------------------------
# Energy & evaluation helpers
# ----------------------------
def spendable_energy_per_player(start: int, cap: int, duration_min: int, tick_minutes: int) -> int:
    base = min(start, cap)
    ticks = duration_min // tick_minutes
    return base + ticks

def evaluate_role(role: str, sb_level: int, mag_level: int, energy_spendable: int):
    if role == "SB-only (3 SB)":
        sb_casts = energy_spendable // 7
        mag_casts = 0
    elif role == "Mag-only (10 Mag)":
        sb_casts = 0
        mag_casts = energy_spendable // 2
    elif role == "2 SB + 3 Mag":
        units = energy_spendable // 20
        sb_casts = 2*units
        mag_casts = 3*units
    elif role == "1 SB + 7 Mag":
        units = energy_spendable // 21
        sb_casts = 1*units
        mag_casts = 7*units
    else:
        sb_casts = mag_casts = 0
    sb_pts = sb_casts * pts_sb(sb_level)
    mag_pts = mag_casts * pts_mag(mag_level)
    energy_used = sb_casts*7 + mag_casts*2
    return sb_casts, mag_casts, sb_pts, mag_pts, energy_used

def auto_assign(rows, energy_spendable: int, objective: str):
    new_rows = []
    for r in rows:
        allowed = ROLES_ORDER if r["sb_level"] > 0 else ["Mag-only (10 Mag)"]
        cand = []
        for role in allowed:
            sb_casts, mag_casts, sb_pts, mag_pts, e_used = evaluate_role(role, r["sb_level"], r["mag_level"], energy_spendable)
            total_pts = sb_pts + mag_pts
            ppe = (total_pts / e_used) if e_used > 0 else 0.0
            if objective == "Max Points":
                score = (total_pts, sb_casts, mag_casts)
            elif objective == "Max SB casts":
                score = (sb_casts, total_pts, mag_casts)
            else:
                score = (ppe, sb_casts, total_pts)
            cand.append((score, role))
        best = max(cand, key=lambda x: x[0]) if cand else (((0,0,0), "— Select —"))
        new_rows.append({**r, "role": best[1]})
    return new_rows

energy_spendable = spendable_energy_per_player(start_energy, energy_cap, duration_min, tick_minutes)

# Auto-Assign: write back to session and rerun so the editor shows new roles
if auto_clicked:
    st.session_state[DATA_KEY] = auto_assign(st.session_state[DATA_KEY], energy_spendable, objective)
    st.success(f"Auto-assign complete ({objective}). Spendable energy per player ≈ {energy_spendable}.")
    st.experimental_rerun()

# ----------------------------
# Totals & cycles
# ----------------------------
def compute_totals(rows, energy_spendable: int, reserve_opener: bool):
    per = []
    total_sb_casts = total_mag_casts = 0
    total_sb_points = total_mag_points = 0
    total_energy_used = 0
    for r in rows:
        sb_casts, mag_casts, sb_pts, mag_pts, e_used = evaluate_role(r['role'], r['sb_level'], r['mag_level'], energy_spendable)
        total_sb_casts += sb_casts
        total_mag_casts += mag_casts
        total_sb_points += sb_pts
        total_mag_points += mag_pts
        total_energy_used += e_used
        per.append({**r,
                    "sb_casts": sb_casts,
                    "mag_casts": mag_casts,
                    "pts_per_sb": pts_sb(r["sb_level"]),
                    "pts_per_mag": pts_mag(r["mag_level"]),
                    "sb_points": sb_pts,
                    "mag_points": mag_pts,
                    "player_points": sb_pts + mag_pts,
                    "energy_used": e_used})
    opener_needed = 6 if reserve_opener else 0
    if total_mag_casts < opener_needed:
        cycles = 0
        leftover_mag = total_mag_casts
        sb_used_in_cycles = 0
    else:
        mag_after_opener = total_mag_casts - opener_needed
        cycles = min(total_sb_casts, mag_after_opener // 3)
        sb_used_in_cycles = cycles
        leftover_mag = mag_after_opener - 3*cycles

    sb_leftover = total_sb_casts - sb_used_in_cycles
    status = "OK" if cycles > 0 else "Insufficient Mag for opener" if reserve_opener and total_mag_casts < 6 else "No cycles possible"
    grand_total = total_sb_points + total_mag_points
    return per, total_sb_casts, total_mag_casts, total_sb_points, total_mag_points, grand_total, total_energy_used, cycles, sb_leftover, leftover_mag, status

(per_rows, tot_sb_casts, tot_mag_casts, tot_sb_points, tot_mag_points,
 grand_total, total_energy_used, cycles, sb_left, mag_left, status) = compute_totals(st.session_state[DATA_KEY], energy_spendable, reserve_opener)

# ----------------------------
# Summary
# ----------------------------
st.subheader("Summary")
c1, c2, c3 = st.columns(3)
c1.metric("Spendable energy / player", energy_spendable)
c2.metric("Total SB casts", int(tot_sb_casts))
c3.metric("Total Mag casts", int(tot_mag_casts))

c4, c5, c6 = st.columns(3)
c4.metric("Cycles (SB + 3×Mag)", int(cycles))
c5.metric("SB leftover", int(sb_left))
c6.metric("Mag leftover", int(mag_left))

st.info(f"Status: {status}")

c7, c8, c9 = st.columns(3)
c7.metric("SB Points", int(tot_sb_points))
c8.metric("Mag Points", int(tot_mag_points))
c9.metric("Grand Total", int(grand_total))

st.metric("Total Energy Used", int(total_energy_used))
ppe = (grand_total / total_energy_used) if total_energy_used > 0 else 0.0
st.caption(f"Points per Energy: {ppe:.2f}  |  Objective: {objective}")

st.divider()

# ----------------------------
# Plan Details
# ----------------------------
st.subheader("Plan Details")
plan_cols = ["name","sb_level","mag_level","role","pts_per_sb","pts_per_mag","sb_casts","mag_casts","sb_points","mag_points","player_points","energy_used"]
st.dataframe([{k: r[k] for k in plan_cols} for r in per_rows], use_container_width=True, hide_index=True)

out = io.StringIO()
w = csv.DictWriter(out, fieldnames=plan_cols)
w.writeheader()
w.writerows([{k: r[k] for k in plan_cols} for r in per_rows])
st.download_button("Download Plan CSV", data=out.getvalue().encode("utf-8"),
                   file_name="bracketforge_v7_1_plan.csv", mime="text/csv")

# ----------------------------
# Team Role Summary
# ----------------------------
st.divider()
st.subheader("Team Role Summary")
role_counts = {}
for r in st.session_state[DATA_KEY]:
    if r["role"] != "— Select —":
        role_counts[r["role"]] = role_counts.get(r["role"], 0) + 1

if role_counts:
    for role in ROLES_ORDER:
        if role in role_counts:
            st.markdown(f"- {role}: **{role_counts[role]}**")
    flat = ", ".join(f"{cnt} {role}" for role, cnt in role_counts.items())
    st.info(f"Assigned roles: {flat}.")
else:
    st.write("No roles assigned yet. Use Auto-Assign or pick roles manually.")
