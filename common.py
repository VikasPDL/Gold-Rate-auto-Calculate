"""Shared scraping wrappers and calculator UI used by all pages of the app."""
import datetime as dt

import streamlit as st

from dgft_scraper import DgftScrapeError, fetch_export_rates
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


@st.cache_data(ttl=3600, show_spinner=False)
def get_export_rates():
    return fetch_export_rates()


def get_export_rates_with_fallback(rates):
    """Returns (fx_rows, stale). dgft.gov.in can block requests from some cloud hosts'
    networks, so fall back to the last successfully cached list instead of a hard error."""
    try:
        fx_rows = get_export_rates()
        rates["last_known_export_rates"] = fx_rows
        rates["last_known_export_rates_time"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_rates(rates)
        return fx_rows, False
    except DgftScrapeError:
        cached = rates.get("last_known_export_rates")
        if cached:
            return cached, True
        raise


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


def render_calculator(rates, base_rate, status, website, key_prefix, rate_display=None):
    """status: short status text, e.g. "live", "manual (set by admin)".
    website: source website name shown to the user, e.g. "ronakgold.com".
    rate_display: how to show the rate itself; defaults to "₹{base_rate:,.2f} / gram"."""
    if status == "unavailable":
        st.error("Gold rate is unavailable: live feed failed and no manual/last-known rate is set. Ask admin to set a manual gold rate.")
        return

    if rate_display is None:
        rate_display = f"₹{base_rate:,.2f} / gram"
    st.caption(f"Gold rate: {rate_display} — Source: {website} ({status})")

    kt_factors = rates["kt_factors"]
    if not kt_factors:
        st.warning("No karat options configured. Ask admin to add some in the Admin panel.")
        return

    col1, col2 = st.columns(2)
    with col1:
        kt = st.selectbox("Karat (KT)", list(kt_factors.keys()), key=f"{key_prefix}_kt")
    with col2:
        gold_grams = st.number_input(
            "Gold weight (grams)", min_value=0.0, step=0.01, format="%.3f", key=f"{key_prefix}_grams"
        )

    diamond_cts = st.number_input(
        "Diamond weight (cts)", min_value=0.0, step=0.01, format="%.3f", key=f"{key_prefix}_cts"
    )

    if st.button("Calculate", type="primary", key=f"{key_prefix}_calc"):
        purity_ref = rates["gold_purity_reference"]
        gold_rate_kt = base_rate * (kt_factors[kt] / 100.0) / purity_ref

        gold_cost = gold_grams * gold_rate_kt
        diamond_cost = diamond_cts * rates["diamond_rate_per_ct"]
        labour_cost = gold_grams * rates["labour_rate_per_gram"]
        cost = gold_cost + diamond_cost + labour_cost

        margin_ratio = rates.get("margin_cost_ratio") or 1.0
        final_price = cost / margin_ratio

        st.subheader("Price Breakdown")
        st.write(f"**{kt} Gold rate:** ₹{gold_rate_kt:,.2f} / gram")
        st.table(
            {
                "Item": ["Gold", "Diamond", "Labour", "Cost"],
                "Amount (₹)": [
                    f"{gold_cost:,.2f}",
                    f"{diamond_cost:,.2f}",
                    f"{labour_cost:,.2f}",
                    f"{cost:,.2f}",
                ],
            }
        )
        st.markdown(f"### Final Jewelry Price: ₹{final_price:,.2f}")

        st.subheader("Export Price (USD / EUR / GBP)")
        try:
            fx_rows, fx_stale = get_export_rates_with_fallback(rates)
        except DgftScrapeError as exc:
            st.warning(
                f"Could not fetch DGFT export rates right now, and no cached rates are available yet: {exc}"
            )
        else:
            if fx_stale:
                st.warning(
                    "Live fetch from dgft.gov.in failed (likely blocked from this server's network) — "
                    "showing the last successfully fetched rates instead. These may not be current."
                )
            eff_date = fx_rows[0]["effective_date"] if fx_rows else "?"
            priced_rows = [r for r in fx_rows if r["export_rate"] and r["code"] in EXPORT_CURRENCIES]
            priced_rows.sort(key=lambda r: EXPORT_CURRENCIES.index(r["code"]))

            cols = st.columns(len(priced_rows) or 1)
            for col, r in zip(cols, priced_rows):
                foreign_amount = final_price / r["export_rate"] * r["units"]
                unit_label = f" / {r['units']}" if r["units"] != 1 else ""
                with col:
                    st.metric(r["code"], f"{foreign_amount:,.2f}")
                    st.caption(f"{r['name']}  \nRate: ₹{r['export_rate']:,.2f}{unit_label}")

            cached_note = " (cached)" if fx_stale else ""
            st.caption(f"Currency rate source: dgft.gov.in (export rates effective {eff_date}{cached_note})")
