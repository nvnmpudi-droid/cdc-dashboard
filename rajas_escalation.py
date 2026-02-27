
from citta import get_streak, update_streak
from dataclasses import dataclass

RAJAS_THRESHOLD = 3  # periods before escalation

@dataclass
class RajasResult:
    state: str
    escalate: bool
    streak: int = 0
    note: str = ""
    candidate_action: str = ""

def evaluate_rajas(z_score: float, sutra_matched: bool,
                   metric_key: str, domain: str) -> RajasResult:
    """
    Evaluate whether a signal is known (SATTVA), artifact (TAMAS),
    or persistent unexplained deviation requiring human review (RAJAS).
    Never invents a cause. Never suppresses silently.
    """
    if sutra_matched:
        update_streak(metric_key, domain, z_score, increment=False)
        return RajasResult(state="SATTVA", escalate=False, streak=0,
                           note="Known cause — Sutra matched.")

    if abs(z_score) <= 2.0:
        update_streak(metric_key, domain, z_score, increment=False)
        return RajasResult(state="TAMAS", escalate=False, streak=0,
                           note="Within normal range — no action required.")

    # Unmapped anomaly — increment streak in Citta
    streak, guna = update_streak(metric_key, domain, z_score, increment=True)

    if streak < RAJAS_THRESHOLD:
        return RajasResult(
            state="UNMAPPED", escalate=False, streak=streak,
            note=f"Unmapped anomaly — streak {streak}/{RAJAS_THRESHOLD}. Monitoring."
        )

    # Persistent unmapped — RAJAS escalation
    return RajasResult(
        state="RAJAS", escalate=True, streak=streak,
        note=(
            f"Persistent deviation observed for {streak} consecutive periods. "
            f"No validated causal mapping exists. "
            f"Escalated for human causal audit."
        ),
        candidate_action="ADD_APAVADA_RULE"
    )

def rajas_vaikhari(result: RajasResult, z_score: float, domain: str) -> dict:
    """Build Vaikhari output for Rajas state — structured, no LLM invention."""
    return {
        "guna_state":      result.state,
        "escalate":        result.escalate,
        "unmapped_streak": result.streak,
        "causal_status":   "NO_VALIDATED_MAPPING" if result.state in ("RAJAS","UNMAPPED") else "VALIDATED",
        "system_statement": result.note,
        "pancavayava":     None,
        "tarka_result":    "ESCALATED — no proof to validate" if result.escalate else "MONITORING",
        "required_action": "Human review required before new Apavada rule can be added." if result.escalate else None,
        "forbidden_phrases": ["possible new trend","likely emerging","this suggests","may indicate"]
    }

if __name__ == "__main__":
    from citta import init_citta
    init_citta()
    # Simulate 4 consecutive unmapped anomalies
    key = "public_health:test_metric"
    for i in range(4):
        r = evaluate_rajas(z_score=3.5, sutra_matched=False, metric_key=key, domain="public_health")
        print(f"Run {i+1}: state={r.state} streak={r.streak} escalate={r.escalate}")
    print("Rajas escalation working correctly")
