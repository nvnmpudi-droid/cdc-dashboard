
import re, json

COMMON_WORDS = {
    "the","a","an","is","are","was","were","has","have","had","be","been",
    "this","that","these","those","it","its","in","on","at","to","for",
    "of","with","by","from","as","or","and","but","not","no","will",
    "would","could","should","may","might","than","then","when","where",
    "which","who","what","how","all","any","each","every","both","more",
    "most","other","such","very","so","also","just","now","about","into"
}

CAUSAL_VERBS = [
    "caused","resulted","triggered","led to","produced","generated",
    "created","induced","drove","forced","caused by","due to","because of",
    "resulted in","stemming from","arising from","attributable to"
]

FORBIDDEN_PATTERNS = [
    "research shows","studies indicate","evidence suggests",
    "it is likely that","this implies","this means that",
    "i recommend","i suggest","it appears","this could indicate",
    "possible new trend","likely emerging","may indicate","seems to suggest"
]

def extract_significant_nouns(text: str) -> set:
    """Extract significant nouns — skip common words and short tokens."""
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    return {w for w in words if w not in COMMON_WORDS}

def check_forbidden_patterns(rendered: str) -> tuple[bool, str]:
    tl = rendered.lower()
    for p in FORBIDDEN_PATTERNS:
        if p in tl:
            return False, f"Forbidden pattern: '{p}'"
    return True, "OK"

def check_causal_verb_drift(rendered: str, proof_text: str) -> tuple[bool, str]:
    rl = rendered.lower()
    pl = proof_text.lower()
    for verb in CAUSAL_VERBS:
        if verb in rl and verb not in pl:
            return False, f"Causal verb not in proof: '{verb}'"
    return True, "OK"

def check_entity_drift(rendered: str, proof_text: str) -> tuple[bool, str]:
    rendered_nouns = extract_significant_nouns(rendered)
    proof_nouns    = extract_significant_nouns(proof_text)
    # Allow domain terms we always expect
    always_allowed = {"mortality","deaths","weekly","reporting","lag","anomaly",
                      "escalate","baseline","critical","warning","normal","trend",
                      "forecast","health","hospital","admissions","public","data",
                      "system","pipeline","period","analysis","signal","score",
                      "deviation","standard","mean","rolling","threshold","cause"}
    new_nouns = rendered_nouns - proof_nouns - always_allowed
    if len(new_nouns) > 3:  # allow small drift for prose connectors
        return False, f"Entity drift — new nouns: {list(new_nouns)[:5]}"
    return True, "OK"

def check_length(rendered: str, max_words: int = 150) -> tuple[bool, str]:
    wc = len(rendered.split())
    if wc > max_words:
        return False, f"Too long: {wc} words (max {max_words})"
    return True, "OK"

def run_full_firewall(rendered: str, proof: dict) -> tuple[bool, str]:
    """
    Full upgraded Narration Firewall v2.
    Four checks: forbidden patterns, causal verb drift,
    entity drift, length enforcement.
    """
    if not rendered or not rendered.strip():
        return False, "Empty output"

    proof_text = json.dumps(proof, default=str)

    checks = [
        check_forbidden_patterns(rendered),
        check_causal_verb_drift(rendered, proof_text),
        check_entity_drift(rendered, proof_text),
        check_length(rendered),
    ]

    for passed, reason in checks:
        if not passed:
            return False, f"REJECTED — {reason}"

    return True, "PASSED"

def narrate_with_budget(render_fn, render_request, proof, max_attempts=2):
    """
    Attempt narration with one regeneration budget.
    If both attempts fail firewall, return deterministic fallback.
    Never silent failure.
    """
    for attempt in range(max_attempts):
        stricter = attempt > 0
        text = render_fn(render_request, stricter=stricter)
        if text:
            passed, reason = run_full_firewall(text, proof)
            if passed:
                return text, "PASSED"
    # Deterministic fallback — always available
    jb = proof.get("justification_block", {})
    urgency = proof.get("urgency", "UNKNOWN")
    fallback = (
        f"Analysis complete. Urgency: {urgency}. "
        f"{jb.get('pratijna','')} "
        f"{jb.get('nigamana','')} "
        f"(Deterministic output — narration firewall enforced.)"
    ).strip()
    return fallback, "FALLBACK — deterministic output used"

if __name__ == "__main__":
    test_proof = {"justification_block":{"pratijna":"4.31 sigma drop is reporting lag","hetu":"Within 7 days of Labor Day","udaharana":"Historical holiday lags matched","upanaya":"Pattern consistent","nigamana":"Do not act"},"urgency":"CRITICAL"}
    # Test: valid narration
    good = "Analysis indicates a reporting lag with CRITICAL severity. No action recommended until pipeline is validated."
    passed, msg = run_full_firewall(good, test_proof)
    print(f"Good narration: {passed} — {msg}")
    # Test: forbidden pattern
    bad = "Research shows this is likely a new emerging trend that could indicate systemic failure."
    passed, msg = run_full_firewall(bad, test_proof)
    print(f"Bad narration:  {passed} — {msg}")
