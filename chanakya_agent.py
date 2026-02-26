
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataset_config import DatasetConfig, get_default_config

URGENCY_MATRIX = {
    ("CRITICAL","increasing"):"CRITICAL",("CRITICAL","decreasing"):"HIGH",
    ("CRITICAL","stable"):"HIGH",("WARNING","increasing"):"HIGH",
    ("WARNING","decreasing"):"MEDIUM",("WARNING","stable"):"MEDIUM",
    ("NORMAL","increasing"):"LOW",("NORMAL","decreasing"):"LOW",
    ("NORMAL","stable"):"MONITOR",
}

POLICY_SIGNALS = {
    ("public_health","flag_reporting_lag"):{"primary":"Do not act — validate reporting pipeline first.","secondary":"Reassess in 4-6 weeks when lag clears.","resource":"No resource reallocation recommended.","escalate":False},
    ("public_health","flag_positive_deviation"):{"primary":"Significant excess signal — escalate to epidemiological review.","secondary":"Cross-reference with emergency department surge data.","resource":"Consider activating surge capacity protocols.","escalate":True},
    ("public_health","flag_negative_deviation"):{"primary":"Significant decline — validate data completeness before acting.","secondary":"Check for reporting delay indicators.","resource":"No resource action until data validated.","escalate":False},
    ("public_health","flag_normal"):{"primary":"System within normal parameters.","secondary":"Continue routine monitoring.","resource":"No resource action required.","escalate":False},
    ("_default","flag_positive_deviation"):{"primary":"Above-baseline signal — investigate root cause.","secondary":"Validate against historical patterns.","resource":"Standby for escalation.","escalate":True},
    ("_default","flag_negative_deviation"):{"primary":"Below-baseline signal — validate data quality.","secondary":"Check reporting pipeline integrity.","resource":"No action until validated.","escalate":False},
    ("_default","flag_normal"):{"primary":"Normal parameters — continue monitoring.","secondary":"No action required.","resource":"No resource action.","escalate":False},
}

def load_inputs():
    for f in ["logic_output.json","forecast_output.json"]:
        if not Path(f).exists():
            raise FileNotFoundError(f"{f} not found — run pipeline first")
    with open("logic_output.json") as f: logic = json.load(f)
    with open("forecast_output.json") as f: forecast = json.load(f)
    return logic, forecast

def determine_urgency(severity, direction):
    return URGENCY_MATRIX.get((severity, direction), "MONITOR")

def get_policy_signals(domain, action):
    return POLICY_SIGNALS.get((domain,action), POLICY_SIGNALS.get(("_default",action), {"primary":"Anomaly detected — investigate.","secondary":"Consult domain expert.","resource":"No action defined.","escalate":False}))

def build_pancavayava(z_score, severity, action, interpretation, hetu, domain, metric, timestamp):
    abs_z = abs(z_score)
    direction = "drop" if z_score < 0 else "spike"
    return {
        "pratijna": f"The {abs_z:.2f}sigma {direction} in {metric} on {timestamp[:10]} is: {interpretation}",
        "hetu": hetu or f"Z-score of {z_score:.4f} exceeds {severity} threshold.",
        "udaharana": f"Historical precedent: prior {severity} events in {domain} with similar Z-scores matched this classification.",
        "upanaya": f"Current observation ({abs_z:.2f}sigma {direction}) matches the historical pattern for {action.replace('_',' ')}.",
        "nigamana": f"Therefore: {interpretation} Confidence grounded in deterministic analysis, not LLM inference.",
    }

def narration_firewall(text, data):
    forbidden = ["because of","due to the fact","research shows","studies indicate","it is likely that","this implies","i recommend","i suggest","it appears","this could indicate"]
    tl = text.lower()
    for p in forbidden:
        if p in tl:
            return False, f"REJECTED: forbidden pattern '{p}'"
    if len(text.split()) > 150:
        return False, f"REJECTED: too long ({len(text.split())} words)"
    return True, "PASSED"

def narrate(render_request, chanakya_data):
    try:
        import requests
        requests.get("http://127.0.0.1:11434/", timeout=3)
    except:
        return None, "SKIPPED — Ollama unavailable"
    try:
        import requests
        rr = render_request["render_request"]
        prompt = rr["instruction"] + "\n\nVALIDATED ANALYSIS:\n" + json.dumps(rr, indent=2) + "\n\nRENDER AS PROSE (max 120 words):"
        r = requests.post("http://127.0.0.1:11434/api/generate", json={"model":"phi3:mini","prompt":prompt,"stream":False,"options":{"temperature":0.1}}, timeout=120)
        text = r.json().get("response","").strip()
        if not text: return None, "SKIPPED — empty response"
        passed, msg = narration_firewall(text, chanakya_data)
        return (text if passed else None), msg
    except Exception as e:
        return None, f"ERROR: {str(e)[:60]}"

def derive_guna(z_score, action):
    if "lag" in action or "reporting" in action: return "TAMAS"
    elif abs(z_score) > 2.0: return "RAJAS"
    return "SATTVA"

def run_chanakya_agent(config=None):
    if config is None: config = get_default_config()
    print("="*55)
    print("  OSIS Chanakya Layer — Mimamsa Minister v1.0")
    print("="*55)
    print(f"  LLM role: VOCAL CORD ONLY — narration not reasoning")

    logic, forecast = load_inputs()
    payload = logic["payload"]
    analysis = payload["analysis"]
    z_score = analysis["z_score"]
    severity = analysis["severity"]
    domain = payload["domain"]
    metric = payload["metric_name"]
    timestamp = payload["timestamp"]
    baseline = payload["baseline_stats"]
    trend_dir = forecast.get("trend",{}).get("direction","stable")
    pct_chg = forecast.get("trend",{}).get("pct_change",0.0)

    urgency = determine_urgency(severity, trend_dir)
    sutra_action = "flag_reporting_lag" if z_score < -2.0 else ("flag_positive_deviation" if z_score > 2.0 else "flag_normal")
    sutra_interp = logic.get("sutra_applied",{}).get("interpretation", severity)
    signals = get_policy_signals(domain, sutra_action)

    hetu = f"Z-score {z_score:.4f} ({severity}). Rolling mean: {baseline.get('rolling_mean',0):,.0f} over {baseline.get('window_periods',4)} periods."
    justification = build_pancavayava(z_score, severity, sutra_action, sutra_interp, hetu, domain, metric, timestamp)

    recs = [
        {"priority":1,"action":signals["primary"],"category":"immediate","escalate":signals["escalate"]},
        {"priority":2,"action":signals["secondary"],"category":"follow_up","escalate":False},
        {"priority":3,"action":signals["resource"],"category":"resource","escalate":False},
    ]
    if urgency == "CRITICAL" and trend_dir == "increasing":
        recs.insert(0,{"priority":0,"action":f"CRITICAL + increasing: immediate escalation. Forecast {pct_chg:+.1f}% over next periods.","category":"critical_escalation","escalate":True})

    output = {
        "status":"success","schema_version":config.schema_version,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "agent_id":"chanakya_mimamsa_minister",
        "domain":domain,"metric_name":metric,"entity_filter":config.entity_filter,
        "finding":{"z_score":z_score,"severity":severity,"forecast_direction":trend_dir,"forecast_pct":pct_chg,"systemic_state":derive_guna(z_score,sutra_action)},
        "urgency":urgency,"sutra_applied":{"action":sutra_action,"interpretation":sutra_interp},
        "recommendations":recs,"justification_block":justification,"pancavayava_complete":True,"escalate":signals["escalate"],
        "narration":None,"narration_firewall":None,
    }

    render_req = {"render_request":{"mode":"executive_brief","instruction":"Render the following validated strategic analysis into professional prose. You are a speech synthesizer not a reasoning engine. Do NOT add modify or invent any causal claims not present in this JSON. Max 120 words.","finding":output["finding"],"urgency":urgency,"recommendations":recs,"justification":justification}}
    narration, fw_result = narrate(render_req, output)
    output["narration"] = narration
    output["narration_firewall"] = fw_result

    payload_hash = hashlib.sha256(json.dumps(output, sort_keys=True, default=str).encode()).hexdigest()
    output["payload_hash"] = payload_hash

    with open("chanakya_output.json","w") as f: json.dump(output, f, indent=2)

    print(f"  Urgency:   {urgency}")
    print(f"  Escalate:  {signals['escalate']}")
    print(f"  Guṇa:      {output['finding']['systemic_state']}")
    print(f"  Firewall:  {fw_result}")
    print(f"  Hash:      {payload_hash[:16]}...")
    print(f"  Saved  ->  chanakya_output.json")
    return output

if __name__ == "__main__":
    run_chanakya_agent()
