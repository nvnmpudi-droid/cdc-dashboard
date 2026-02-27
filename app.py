import streamlit as st
import json
import subprocess
import sys
from pathlib import Path
from dataset_config import get_default_config
from conversation_agent import translate_query, contextualize

st.set_page_config(page_title="OSIS — Epistemic Truth Engine", layout="wide")

# ── Load dataset registry ──────────────────────────────────────────────────
def load_registry():
    p = Path("dataset_registry.json")
    if not p.exists():
        return [{"id":"cdc_mortality","label":"CDC NVSS Weekly Mortality","domain":"public_health","status":"active"}]
    return json.loads(p.read_text())["datasets"]

def load_json(path):
    p = Path(path)
    if p.exists():
        try: return json.loads(p.read_text())
        except: return None
    return None

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚔️ OSIS")
    st.caption("Epistemic Truth Engine")
    st.markdown("---")

    datasets = load_registry()
    dataset_labels = {d["label"]: d for d in datasets}
    selected_label = st.selectbox("📊 Select Dataset", list(dataset_labels.keys()))
    selected_ds = dataset_labels[selected_label]

    st.markdown(f"**Domain:** {selected_ds['domain']}")
    st.markdown(f"**Status:** {selected_ds['status']}")
    st.markdown("---")

    st.markdown("#### 💬 Ask a Question")
    user_query = st.text_input("", placeholder="e.g. Show me worst anomaly this year")

    if user_query:
        with st.spinner("Translating query..."):
            structured = translate_query(user_query, datasets)
        st.caption("🔄 Translated to structured query:")
        st.json(structured)
        if structured.get("ambiguous"):
            st.warning(f"Clarification needed: {structured.get('clarification_needed')}")

    st.markdown("---")
    run_btn = st.button("▶ Run Analysis", type="primary", use_container_width=True)
    skip_db = st.checkbox("Skip data refresh (use cached)", value=True)

    st.markdown("---")
    st.markdown("#### ℹ️ Explain a term")
    explain_term = st.text_input("", placeholder="e.g. z-score, tamas, reporting lag", key="explain")
    if explain_term:
        st.info(contextualize(explain_term))

# ── Main panel ─────────────────────────────────────────────────────────────
st.title("OSIS — Organizational Strategy Intelligence System")
st.caption("LLM = Vocal Cord Only | All reasoning is deterministic | Every claim is auditable")

if run_btn:
    with st.spinner("Running OSIS pipeline..."):
        cmd = [sys.executable, "main.py"]
        if skip_db:
            cmd.append("--skip-db")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
    if result.returncode != 0:
        st.error("Pipeline error:")
        st.code(result.stderr)
    else:
        st.success("Pipeline complete")

# ── Load outputs ───────────────────────────────────────────────────────────
logic    = load_json("logic_output.json")
forecast = load_json("forecast_output.json")
chanakya = load_json("chanakya_output.json")

if not logic:
    st.info("Select a dataset and click **Run Analysis** to begin.")
    st.stop()

# ── Row 1: Key metrics ─────────────────────────────────────────────────────
payload  = logic.get("payload", {})
analysis = payload.get("analysis", {})
baseline = payload.get("baseline_stats", {})

col1, col2, col3, col4 = st.columns(4)
z = analysis.get("z_score", 0)
sev = analysis.get("severity", "NORMAL")
sev_color = {"CRITICAL":"🔴","WARNING":"🟡","NORMAL":"🟢"}.get(sev,"⚪")
col1.metric("Z-Score", f"{z:.4f}")
col2.metric("Severity", f"{sev_color} {sev}")
col3.metric("Rolling Mean", f"{baseline.get('rolling_mean',0):,.0f}")
col4.metric("Anomalies (total)", payload.get("total_anomalies","—"))

# ── Row 2: Chanakya urgency ────────────────────────────────────────────────
if chanakya:
    urgency = chanakya.get("urgency","—")
    guna    = chanakya.get("finding",{}).get("systemic_state","—")
    escalate = chanakya.get("escalate", False)
    u_color = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🔵","MONITOR":"🟢"}.get(urgency,"⚪")
    g_color = {"RAJAS":"🔴","TAMAS":"🟤","SATTVA":"🟢"}.get(guna,"⚪")

    st.markdown("---")
    c1,c2,c3 = st.columns(3)
    c1.metric("Urgency",  f"{u_color} {urgency}")
    c2.metric("Guṇa State", f"{g_color} {guna}")
    c3.metric("Escalate",   "⚠️ YES" if escalate else "✅ NO")

# ── Row 3: Pañcavayava justification ──────────────────────────────────────
if chanakya and chanakya.get("justification_block"):
    st.markdown("---")
    st.subheader("📐 Pañcavayava — Causal Justification")
    st.caption("Deterministic 5-member proof constructed by ML Brain. LLM did not generate this.")
    jb = chanakya["justification_block"]
    labels = {"pratijna":"1. Pratijñā (Proposition)","hetu":"2. Hetu (Reason)","udaharana":"3. Udāharaṇa (Example)","upanaya":"4. Upanaya (Application)","nigamana":"5. Nigamana (Conclusion)"}
    for key, label in labels.items():
        if jb.get(key):
            st.markdown(f"**{label}**")
            st.info(jb[key])

# ── Row 4: Chanakya recommendations ───────────────────────────────────────
if chanakya and chanakya.get("recommendations"):
    st.markdown("---")
    st.subheader("⚔️ Strategic Recommendations")
    st.caption("Generated by deterministic policy registry. LLM vocal cord renders below.")
    recs = sorted(chanakya["recommendations"], key=lambda r: r.get("priority",99))
    for rec in recs:
        icon = "🚨" if rec.get("escalate") else "📋"
        cat  = rec.get("category","").replace("_"," ").title()
        st.markdown(f"{icon} **[{cat}]** {rec['action']}")

    if chanakya.get("narration") and chanakya.get("narration_firewall") == "PASSED":
        st.markdown("---")
        st.markdown("**🗣️ LLM Narration** *(vocal cord — rendered from validated proof)*")
        st.success(chanakya["narration"])
        st.caption(f"Narration Firewall: {chanakya['narration_firewall']}")
    elif chanakya.get("narration_firewall","").startswith("REJECTED"):
        st.warning(f"Narration rejected by firewall: {chanakya['narration_firewall']}")

# ── Row 5: Top anomalies ───────────────────────────────────────────────────
top = payload.get("top_anomalies", [])
if top:
    st.markdown("---")
    st.subheader("📊 Top Anomalies Detected")
    import pandas as pd
    df = pd.DataFrame(top)
    if "time_period" in df.columns:
        df["time_period"] = pd.to_datetime(df["time_period"]).dt.strftime("%Y-%m-%d")
    st.dataframe(df, use_container_width=True)

# ── Row 6: Forecast ────────────────────────────────────────────────────────
if forecast and forecast.get("forecast"):
    st.markdown("---")
    st.subheader("📈 Forecast — Next 4 Periods")
    trend = forecast.get("trend",{})
    direction = trend.get("direction","—")
    pct = trend.get("pct_change",0)
    d_icon = "📈" if direction=="increasing" else ("📉" if direction=="decreasing" else "➡️")
    st.caption(f"Trend: {d_icon} {direction} ({pct:+.1f}%)")
    fc_rows = []
    for fc in forecast["forecast"]:
        fc_rows.append({"Period":fc["ds"][:10],"Forecast":f"{fc['forecast']:,}","Lower 95%":f"{fc['lower_95']:,}","Upper 95%":f"{fc['upper_95']:,}"})
    st.table(fc_rows)

# ── Row 7: Audit trail ─────────────────────────────────────────────────────
with st.expander("🔍 Audit Trail"):
    if logic:
        st.caption("Logic Agent Vaikharī")
        st.json({"payload_hash": payload.get("payload_hash","—"), "schema_version": logic.get("schema_version","—"), "generated_at": payload.get("timestamp","—"), "tarka_result": logic.get("tarka_result","—")})
    if chanakya:
        st.caption("Chanakya Vaikharī")
        st.json({"payload_hash": chanakya.get("payload_hash","—"), "pancavayava_complete": chanakya.get("pancavayava_complete"), "narration_firewall": chanakya.get("narration_firewall","—"), "sutra_applied": chanakya.get("sutra_applied",{})})

st.markdown("---")
st.caption("OSIS v3.0 | LLM = Vocal Cord Only | Pañcavayava proof is deterministic | Every output is hashed")
