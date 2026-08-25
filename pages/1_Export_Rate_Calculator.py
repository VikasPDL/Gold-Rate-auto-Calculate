import streamlit as st

from common import get_gjepc_rate_with_fallback, render_calculator
from gjepc_scraper import GjepcScrapeError
from store import load_rates

st.set_page_config(page_title="Export Rate Calculator", layout="wide")

st.title("Export Rate Calculator — GJEPC Notional Rate")
st.caption(
    "Gold rate is always from today's GJEPC DGJEPS notional rate circular "
    "(gjepc.org/gold-rates.php), independent of the gold source picked on the main "
    "Price Calculator / Admin page. Currency conversion is from DGFT's export rates "
    "(dgft.gov.in) — same source as the main calculator."
)

rates = load_rates()

try:
    data, stale = get_gjepc_rate_with_fallback(rates)
except GjepcScrapeError as exc:
    st.error(
        f"Could not fetch the GJEPC rate PDF, and no previously cached rate is available yet: {exc}\n\n"
        "This can happen if gjepc.org is blocking requests from this server's network "
        "(common with cloud hosts). Try again from a different network, or check back "
        "once a rate has been fetched successfully at least once."
    )
    st.stop()

if stale:
    st.warning(
        f"Live fetch from gjepc.org failed (likely blocked from this server's network) — "
        f"showing the last successfully fetched rate instead, from circular dated {data['effective_date']}. "
        "This may not be today's rate."
    )

purity_ref = rates["gold_purity_reference"]
base_rate = data["gold_inr_per_gram"] * (purity_ref / data["purity"])
status = f"dated {data['effective_date']}" + (", cached" if stale else "")
rate_display = f"${data['gold_usd_per_oz']:,.2f} / troy oz ({data['purity']} fine)"

render_calculator(
    rates,
    base_rate,
    status,
    "gjepc.org",
    key_prefix="export",
    rate_display=rate_display,
    currency_mode="dgft",
    show_inr_breakdown=False,
    currency_layout="grid",
)
