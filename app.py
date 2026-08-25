import streamlit as st

from common import get_base_gold_rate, gold_source_website, render_calculator
from store import load_rates

st.set_page_config(page_title="Jewellery Price Calculator", layout="centered")

st.title("Jewellery Price Calculator")

rates = load_rates()
base_rate, status = get_base_gold_rate(rates)
website = gold_source_website(status)
render_calculator(rates, base_rate, status, website, key_prefix="main", currency_mode="dgft")
