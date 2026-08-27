"""Shared scraping wrappers and calculator UI used by all pages of the app."""
import datetime as dt

import streamlit as st

from gjepc_scraper import GjepcScrapeError, fetch_gjepc_gold_rate
from scraper import ScrapeError, fetch_gold_995_rate_per_gram
from store import save_rates

def gold_source_website(status):
    """Website name for a status string returned by get_base_gold_rate."""
    if status.startswith("manual"):
        return "manual (admin-set)"
    if status.startswith("GJEPC"):
        return "gjepc.org"
    return "ronakgold.com"  # "live" or "last known (...)"


@st.cache_data(ttl=20, show_spinner=False)
def get_live_gold_rate():
    return fetch_gold_995_rate_per_gram()


@st.cache_data(ttl=3600, show_spinner=False)
def get_gjepc_rate():
    return fetch_gjepc_gold_rate()


EXPORT_CURRENCIES = ("USD", "EUR", "GBP")
EXPORT_CURRENCY_NAMES = {"USD": "US Dollars", "EUR": "EURO", "GBP": "Pound Sterling"}


def get_base_gold_rate(rates):
    """Returns (rate_per_gram, source_label), expressed at rates['gold_purity_reference'] fineness.
    Falls back to last-known rate on scrape failure."""
    source = rates.get("gold_rate_source", "live")

    if source == "manual":
        return rates["manual_gold_rate_per_gram"], "manual (set by admin)"

    if source == "gjepc":
        try:
            data = get_gjepc_rate()
            purity_ref = rates["gold_purity_reference"]
            rate = data["gold_inr_per_gram"] * (purity_ref / data["purity"])
            rates["last_known_gold_rate"] = rate
            rates["last_known_gold_rate_time"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_rates(rates)
            return rate, f"GJEPC notional ({data['effective_date']})"
        except GjepcScrapeError:
            if rates.get("last_known_gold_rate"):
                return rates["last_known_gold_rate"], f"last known ({rates.get('last_known_gold_rate_time', '?')})"
            return 0.0, "unavailable"

    try:
        rate = get_live_gold_rate()
        rates["last_known_gold_rate"] = rate
        rates["last_known_gold_rate_time"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_rates(rates)
        return rate, "live"
    except ScrapeError:
        if rates.get("last_known_gold_rate"):
            return rates["last_known_gold_rate"], f"last known ({rates.get('last_known_gold_rate_time', '?')})"
        return 0.0, "unavailable"


def render_calculator(
    rates,
    base_rate,
    status,
    website,
    key_prefix,
    diamond_rate,
    labour_rate,
    rate_display=None,
    kt_factors=None,
    weight_label="Gold weight (grams)",
    metal_label="Gold",
):
    """status: short status text, e.g. "live", "manual (set by admin)".
    website: source website name shown to the user, e.g. "ronakgold.com".
    diamond_rate / labour_rate: resolved ₹/ct and ₹/gram numbers to use (caller picks which
    admin-set rate applies -- gold's or silver's).
    rate_display: how to show the rate itself; defaults to "₹{base_rate:,.2f} / gram".
    kt_factors: dict of KT name -> percent; if None, no KT selector is shown and base_rate is
    used directly as the metal's ₹/gram rate (for silver, which has no karat purity)."""
    if status == "unavailable":
        st.error(f"{metal_label} rate is unavailable: live feed failed and no manual/last-known rate is set. Ask admin to set a manual rate.")
        return

    if rate_display is None:
        rate_display = f"₹{base_rate:,.2f} / gram"
    st.caption(f"{metal_label} rate: {rate_display} — Source: {website} ({status})")

    if kt_factors is not None and not kt_factors:
        st.warning("No karat options configured. Ask admin to add some in the Admin panel.")
        return

    if kt_factors is not None:
        col1, col2 = st.columns(2)
        with col1:
            kt = st.selectbox("Karat (KT)", list(kt_factors.keys()), key=f"{key_prefix}_kt")
        with col2:
            metal_grams = st.number_input(
                weight_label, min_value=0.0, step=0.01, format="%.3f", key=f"{key_prefix}_grams"
            )
    else:
        metal_grams = st.number_input(
            weight_label, min_value=0.0, step=0.01, format="%.3f", key=f"{key_prefix}_grams"
        )

    diamond_cts = st.number_input(
        "Diamond weight (cts)", min_value=0.0, step=0.01, format="%.3f", key=f"{key_prefix}_cts"
    )

    calculated_key = f"{key_prefix}_calculated"
    if st.button("Calculate", type="primary", key=f"{key_prefix}_calc"):
        st.session_state[calculated_key] = True

    if not st.session_state.get(calculated_key):
        return

    if kt_factors is not None:
        purity_ref = rates["gold_purity_reference"]
        metal_rate = base_rate * (kt_factors[kt] / 100.0) / purity_ref
    else:
        metal_rate = base_rate

    metal_cost = metal_grams * metal_rate
    diamond_cost = diamond_cts * diamond_rate
    labour_cost = metal_grams * labour_rate
    cost = metal_cost + diamond_cost + labour_cost

    margin_ratio = rates.get("margin_cost_ratio") or 1.0
    final_price = cost / margin_ratio

    st.write("Price")
    st.markdown(f"**₹{cost:,.2f}**")

    st.write("**Export Price (USD / EUR / GBP)**")
    st.caption("Exchange rate defaults to the last value set in Admin — edit here if today's rate is different.")
    defaults = rates.get("manual_export_rates") or {}
    cols = st.columns(len(EXPORT_CURRENCIES))
    for col, code in zip(cols, EXPORT_CURRENCIES):
        with col:
            fx_rate = st.number_input(
                f"{code} rate (₹)",
                min_value=0.0,
                value=float(defaults.get(code) or 0.0),
                step=0.01,
                key=f"{key_prefix}_fxrate_{code}",
            )
            if fx_rate > 0:
                foreign_amount = final_price / fx_rate
                st.markdown(f"**{foreign_amount:,.2f}**")
            else:
                st.caption("Enter a rate")
            st.caption(EXPORT_CURRENCY_NAMES[code])
