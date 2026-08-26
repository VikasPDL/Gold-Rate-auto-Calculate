import streamlit as st

from store import MIN_LABOUR_RATE_PER_GRAM, load_rates, save_rates

st.set_page_config(page_title="Admin", layout="centered")

st.title("Admin")

rates = load_rates()

if "admin_authed" not in st.session_state:
    st.session_state.admin_authed = False

if not st.session_state.admin_authed:
    pwd = st.text_input("Admin password", type="password")
    if st.button("Login"):
        if pwd == rates["admin_password"]:
            st.session_state.admin_authed = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

st.success("Logged in as admin")
if st.button("Log out"):
    st.session_state.admin_authed = False
    st.rerun()

st.divider()
st.subheader("Diamond Rate (locked from calculator pages)")
diamond_rate = st.number_input(
    "Diamond rate (₹ per ct)", min_value=0.0, value=float(rates["diamond_rate_per_ct"]), step=100.0
)

st.subheader("Labour Rate (locked from calculator pages)")
labour_rate = st.number_input(
    "Labour rate (₹ per gram of gold)",
    min_value=MIN_LABOUR_RATE_PER_GRAM,
    value=max(float(rates["labour_rate_per_gram"]), MIN_LABOUR_RATE_PER_GRAM),
    step=10.0,
)
st.caption(f"Cannot be set below ₹{MIN_LABOUR_RATE_PER_GRAM:,.0f} / gram.")

if st.button("Save Diamond & Labour Rates"):
    rates["diamond_rate_per_ct"] = diamond_rate
    rates["labour_rate_per_gram"] = labour_rate
    save_rates(rates)
    st.success("Saved.")

st.divider()
st.subheader("Pricing Margin")
st.caption(
    "Final Jewelry Price = Cost ÷ this ratio. E.g. 0.70 means cost is 70% of the "
    "selling price (a ~42.9% markup on cost, i.e. a 30% gross margin on the selling price)."
)
margin_ratio = st.number_input(
    "Cost as a fraction of Selling Price",
    min_value=0.01,
    max_value=1.0,
    value=float(rates.get("margin_cost_ratio", 0.7)),
    step=0.01,
    format="%.2f",
)
if st.button("Save Margin"):
    rates["margin_cost_ratio"] = margin_ratio
    save_rates(rates)
    st.success("Saved.")

st.divider()
st.subheader("Karat (KT) Factors")
st.caption("Formula used: Rate/gram(KT) = Base Gold Rate × (Factor % / 100) ÷ Purity Reference")
kt_factors = dict(rates["kt_factors"])
to_delete = None
for kt, factor in kt_factors.items():
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.text(kt)
    with c2:
        new_val = st.number_input(f"factor_{kt}", value=float(factor), step=0.01, label_visibility="collapsed")
        kt_factors[kt] = new_val
    with c3:
        if st.button("Remove", key=f"remove_{kt}"):
            to_delete = kt
if to_delete:
    del kt_factors[to_delete]
    rates["kt_factors"] = kt_factors
    save_rates(rates)
    st.rerun()

with st.form("add_kt_form", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    new_kt = c1.text_input("New KT name (e.g. 20K)")
    new_factor = c2.number_input("Factor %", min_value=0.0, step=0.01)
    add = c3.form_submit_button("Add")
    if add and new_kt:
        kt_factors[new_kt] = new_factor
        rates["kt_factors"] = kt_factors
        save_rates(rates)
        st.rerun()

purity_ref = st.number_input(
    "Gold purity reference (denominator in formula)",
    min_value=0.001,
    value=float(rates["gold_purity_reference"]),
    step=0.001,
    format="%.3f",
)

if st.button("Save KT Factors & Purity Reference"):
    rates["kt_factors"] = kt_factors
    rates["gold_purity_reference"] = purity_ref
    save_rates(rates)
    st.success("Saved.")

st.divider()
st.subheader("Gold Rate Source (used by the main Price Calculator)")
st.caption(
    f"Last known rate used: ₹{rates.get('last_known_gold_rate') or 0:,.2f} / gram "
    f"(at {rates.get('last_known_gold_rate_time') or 'never'})"
)
source_options = {
    "live": "Live scrape (ronakgold.com)",
    "gjepc": "GJEPC notional rate (daily PDF circular)",
    "manual": "Manual (set below)",
}
current_source = rates.get("gold_rate_source", "live")
selected_label = st.selectbox(
    "Source",
    list(source_options.values()),
    index=list(source_options.keys()).index(current_source),
)
selected_source = next(k for k, v in source_options.items() if v == selected_label)

manual_rate = st.number_input(
    "Manual gold rate (₹ per gram, at the Purity Reference above)",
    min_value=0.0,
    value=float(rates["manual_gold_rate_per_gram"]),
    step=10.0,
)
if st.button("Save Gold Rate Settings"):
    rates["gold_rate_source"] = selected_source
    rates["manual_gold_rate_per_gram"] = manual_rate
    save_rates(rates)
    st.success("Saved.")

st.divider()
st.subheader("Change Admin Password")
new_pwd = st.text_input("New password", type="password", key="new_pwd")
if st.button("Change Password"):
    if new_pwd:
        rates["admin_password"] = new_pwd
        save_rates(rates)
        st.success("Password changed.")
    else:
        st.error("Enter a new password first.")
