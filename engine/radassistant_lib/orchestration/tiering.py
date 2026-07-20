"""Model tiering — pick the cheapest backend that fits, and NEVER leak PHI to cloud.

Research (RouteLLM/FrugalGPT): routing most turns to a small/local model while escalating
only hard ones keeps ~95% of quality at a fraction of the cost. RadAssistant is already
multi-backend, so this is just a decision function over the router's advice + what's
actually available. The one hard rule: anything the policy tagged phi_egress, or any turn
touching patient data, is PINNED on-machine — cloud is never chosen for it.

Pure logic, unit-tested (tests/test_infra.py).
"""

# tier -> which backend kind it prefers, cheapest first
_TIER_ORDER = {
    "small_local": ["ollama_small", "ollama", "openai_local", "anthropic"],
    "large_local": ["ollama", "openai_local", "anthropic", "ollama_small"],
    "cloud":       ["anthropic", "openai_local", "ollama"],
}


def choose_backend(decision, available, *, phi=False):
    """Return (backend_key, reason). `available` is the set/list of backend keys that
    are actually configured/reachable (e.g. {'ollama','anthropic'})."""
    available = list(available)
    tier = getattr(decision, "model_tier", "large_local")
    wants_cloud = tier == "cloud" or getattr(decision, "risk", "") == "phi_egress"

    # HARD RULE: PHI (or a phi_egress action) never goes to a cloud backend.
    phi = phi or getattr(decision, "risk", "") == "phi_egress"
    order = list(_TIER_ORDER.get(tier, _TIER_ORDER["large_local"]))
    if phi:
        order = [b for b in order if b != "anthropic"]
        if not any(b in available for b in order):
            return (None, "PHI/off-machine request but only a cloud backend is configured — "
                          "refusing to send patient-derived data to the cloud.")

    for key in order:
        if key in available:
            note = f"tier '{tier}' -> {key}"
            if phi:
                note += " (PHI pinned on-machine)"
            elif wants_cloud and key != "anthropic":
                note += " (cloud unavailable; using local)"
            return key, note
    # fallback: anything available
    if available:
        return available[0], f"no preferred backend for tier '{tier}'; using {available[0]}"
    return None, "no backend configured"
