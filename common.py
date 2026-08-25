"""Shared scraping wrappers and calculator UI used by all pages of the app."""
import datetime as dt

import streamlit as st

from dgft_scraper import DgftScrapeError, fetch_export_rates
from gjepc_scraper import GjepcScrapeError, fetch_gjepc_gold_rate
from scraper import ScrapeError, fetch_gold_995_rate_per_gram
from store import save_rates

GOLD_SOURCE_WEBSITE = {
    "live": "ronakgold.com",
    "manual (set by admin)": "manual (admin-set)",
}


def gold_source_website(source_label):
    if source_label.startswith("GJEPC"):
        return "gjepc.org"
    if source_label.startswith("last known"):
        return f"ronakgold.com ({source_label})"
    return GOLD_SOURCE_WEBSITE.get(source_label, source_label)


@st.cache_data(ttl=20, show_spinner=False)
def get_live_gold_rate():
    return fetch_gold_995_rate_per_gram()


@st.cache_data(ttl=3600, show_spinner=False)
def get_gjepc_rate():
    return fetch_gjepc_gold_rate()


def get_gjepc_rate_with_fallback(rates):
    """Returns (data, stale). data is fetch_gjepc_gold_rate()'s dict, either fresh or the
    last successfully cached copy if the live fetch fails (e.g. gjepc.org blocking the
    server's IP, which happens on some cloud hosts even though it works from a normal
    network). Raises GjepcScrapeError only if there's no cached copy to fall back to."""
    try:
        data = get_gjepc_rate()
        rates["last_known_gjepc"] = data
        save_rates(rates)
        return data, False
    except GjepcScrapeError:
        cached = rates.get("last_known_gjepc")
        if cached:
            return cached, True
        raise


@st.cache_data(ttl=3600, show_spinner=False)
def get_export_rates():
    return fetch_export_rates()


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


def render_calculator(rates, base_rate, source, key_prefix, purity_note="", currency_mode="dgft", gjepc_fx=None):
    """currency_mode: "dgft" (all DGFT currencies), "gjepc" (USD/EUR from the GJEPC PDF only), or "none"."""
    if source == "unavailable":
        st.error("Gold rate is unavailable: live feed failed and no manual/last-known rate is set. Ask admin to set a manual gold rate.")
        return

    badge = {"live": "🟢 live", "manual (set by admin)": "🔧 manual"}.get(source, f"🟡 {source}")
    st.caption(f"Gold base rate: ₹{base_rate:,.2f} / gram{purity_note} — {badge}")

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
        total = gold_cost + diamond_cost + labour_cost

        st.subheader("Price Breakdown")
        st.write(f"**{kt} Gold rate:** ₹{gold_rate_kt:,.2f} / gram")
        st.table(
            {
                "Item": ["Gold", "Diamond", "Labour", "Total"],
                "Amount (₹)": [
                    f"{gold_cost:,.2f}",
                    f"{diamond_cost:,.2f}",
                    f"{labour_cost:,.2f}",
                    f"{total:,.2f}",
                ],
            }
        )

        st.markdown(f"### Total Jewellery Cost: ₹{total:,.2f}")

        if currency_mode == "dgft":
            with st.expander("Export price in other currencies (DGFT customs rates)", expanded=False):
                try:
                    fx_rows = get_export_rates()
                except DgftScrapeError as exc:
                    st.warning(f"Could not fetch DGFT export rates right now: {exc}")
                else:
                    eff_date = fx_rows[0]["effective_date"] if fx_rows else "?"
                    table = {"Currency": [], "Current Rate (₹)": [], "Amount": []}
                    for r in fx_rows:
                        if not r["export_rate"]:
                            continue
                        foreign_amount = total / r["export_rate"] * r["units"]
                        unit_label = f" per {r['units']}" if r["units"] != 1 else ""
                        table["Currency"].append(f"{r['code']} — {r['name']}")
                        table["Current Rate (₹)"].append(f"{r['export_rate']:,.2f}{unit_label}")
                        table["Amount"].append(f"{foreign_amount:,.2f}")
                    st.table(table)

                    website = gold_source_website(source)
                    st.caption(
                        f"Currency rate source: dgft.gov.in (export rates effective {eff_date})  \n"
                        f"Gold rate source: {website} — ₹{base_rate:,.2f} / gram"
                    )

        elif currency_mode == "gjepc" and gjepc_fx:
            st.subheader("Export Price (GJEPC notional rate)")
            table = {"Currency": [], "Current Rate (₹)": [], "Amount": []}
            table["Currency"].append("USD — US Dollar")
            table["Current Rate (₹)"].append(f"{gjepc_fx['usd_inr']:,.4f}")
            table["Amount"].append(f"{total / gjepc_fx['usd_inr']:,.2f}")
            if gjepc_fx.get("eur_inr"):
                table["Currency"].append("EUR — Euro")
                table["Current Rate (₹)"].append(f"{gjepc_fx['eur_inr']:,.4f}")
                table["Amount"].append(f"{total / gjepc_fx['eur_inr']:,.2f}")
            st.table(table)
            st.caption(f"Source: gjepc.org — DGJEPS notional circular dated {gjepc_fx['effective_date']}")
