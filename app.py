import streamlit as st

from common import get_base_gold_rate, gold_source_website, render_calculator
from store import load_rates

st.set_page_config(page_title="Jewellery Price Calculator", layout="centered")

st.title("Jewellery Price Calculator")

rates = load_rates()

tab_gold, tab_silver = st.tabs(["Gold", "Silver"])

with tab_gold:
    base_rate, status = get_base_gold_rate(rates)
    website = gold_source_website(status)
    render_calculator(
        rates,
        base_rate,
        status,
        website,
        key_prefix="gold",
        diamond_rate=rates["diamond_rate_per_ct"],
        labour_rate=rates["labour_rate_per_gram"],
        kt_factors=rates["kt_factors"],
        weight_label="Gold weight (grams)",
        metal_label="Gold",
    )

with tab_silver:
    render_calculator(
        rates,
        rates["silver_rate_per_gram"],
        "manual (set by admin)",
        "manual (admin-set)",
        key_prefix="silver",
        diamond_rate=rates["silver_diamond_rate_per_ct"],
        labour_rate=rates["silver_labour_rate_per_gram"],
        kt_factors=None,
        weight_label="Silver weight (grams)",
        metal_label="Silver",
    )
