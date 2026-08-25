import streamlit as st

from common import get_gjepc_rate, render_calculator
from gjepc_scraper import GjepcScrapeError
from store import load_rates

st.set_page_config(page_title="Export Rate Calculator", layout="centered")

st.title("Export Rate Calculator — GJEPC Notional Rate")
st.caption(
    "Always uses today's GJEPC DGJEPS notional rate circular (gjepc.org/gold-rates.php) "
    "for both the gold rate and the USD/EUR conversion — independent of the gold source "
    "picked on the main Price Calculator / Admin page."
)

rates = load_rates()

try:
    data = get_gjepc_rate()
except GjepcScrapeError as exc:
    st.error(f"Could not fetch the GJEPC rate PDF: {exc}")
    st.stop()

purity_ref = rates["gold_purity_reference"]
base_rate = data["gold_inr_per_gram"] * (purity_ref / data["purity"])
source = f"GJEPC circular dated {data['effective_date']}"
purity_note = f" (from ${data['gold_usd_per_oz']:,.2f}/oz @ {data['purity']} fine, USD-INR {data['usd_inr']})"

render_calculator(
    rates,
    base_rate,
    source,
    key_prefix="export",
    purity_note=purity_note,
    currency_mode="gjepc",
    gjepc_fx=data,
)
