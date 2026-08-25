import streamlit as st

from common import get_base_gold_rate, render_calculator
from store import load_rates

st.set_page_config(page_title="Jewellery Price Calculator", layout="centered")

st.title("Jewellery Price Calculator")

rates = load_rates()
base_rate, source = get_base_gold_rate(rates)
render_calculator(rates, base_rate, source, key_prefix="main", currency_mode="dgft")
