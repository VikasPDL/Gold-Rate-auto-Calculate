"""Persistence for admin-controlled rates (diamond rate, labour rate, KT factors, gold rate overrides)."""
import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "rates.json")

DEFAULTS = {
    "admin_password": "admin123",
    "diamond_rate_per_ct": 50000.0,
    "labour_rate_per_gram": 700.0,
    "gold_purity_reference": 0.995,
    "kt_factors": {
        "22K": 92.96,
        "18K": 75.37,
        "14K": 58.6,
        "10K": 41.07,
        "9K": 38.0,
    },
    "gold_rate_source": "live",  # "live" (ronakgold), "gjepc" (GJEPC notional PDF), or "manual"
    "manual_gold_rate_per_gram": 0.0,
    "last_known_gold_rate": None,
    "last_known_gold_rate_time": None,
}


def load_rates():
    if not os.path.exists(DATA_PATH):
        save_rates(DEFAULTS.copy())
        return DEFAULTS.copy()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = False
    for key, val in DEFAULTS.items():
        if key not in data:
            data[key] = val
            changed = True
    if "use_manual_gold_rate" in data:
        if "gold_rate_source" not in data or changed and data.get("gold_rate_source") == "live":
            data["gold_rate_source"] = "manual" if data["use_manual_gold_rate"] else "live"
        del data["use_manual_gold_rate"]
        changed = True
    if changed:
        save_rates(data)
    return data


def save_rates(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
