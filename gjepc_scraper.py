"""Daily gold rate from GJEPC's DGJEPS notional rate circular (PDF).

https://gjepc.org/gold-rates.php lists one PDF per working day
(admin/GoldRate/<id>_<Nth>_<Mon>_<Year>_Gold_Rate.pdf). The filename's numeric
id prefix is unpredictable, but the newest day's link is always first in the
page's HTML, so we re-scrape the listing page each time rather than guessing
today's URL.

The PDF is real text (not a scan), and pypdf extracts it in clean row order:
    1 GOLD
    $ 4663.7 PER T.O. (0.999)
    LONDON PM OF
    24/08/2026
    ...
    4 US DOLLAR 95.6346
    5 EURO 111.661

Gold/silver/platinum are quoted in USD per Troy Ounce; USD DOLLAR / EURO rows
are GJEPC's own INR conversion rates for this circular.
"""
import io
import re
from urllib.parse import urljoin

import pypdf
import requests

LISTING_URL = "https://gjepc.org/gold-rates.php"
TROY_OUNCE_GRAMS = 31.1034768

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


class GjepcScrapeError(Exception):
    pass


def _find_latest_pdf_url(timeout):
    try:
        resp = requests.get(LISTING_URL, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GjepcScrapeError(f"Could not reach GJEPC rates page: {exc}") from exc

    match = re.search(r'href="(admin/GoldRate/[^"]*Gold_Rate\.pdf)"', resp.text)
    if not match:
        raise GjepcScrapeError("Could not find a Gold Rate PDF link on the GJEPC page")
    return urljoin(LISTING_URL, match.group(1))


def fetch_gjepc_gold_rate(timeout=20):
    """Returns a dict with gold rate (USD/oz and derived INR/gram), USD & EUR
    conversion rates, purity, and the circular's effective date."""
    pdf_url = _find_latest_pdf_url(timeout)

    try:
        pdf_resp = requests.get(pdf_url, headers=_HEADERS, timeout=timeout)
        pdf_resp.raise_for_status()
    except requests.RequestException as exc:
        raise GjepcScrapeError(f"Could not download GJEPC PDF: {exc}") from exc

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_resp.content))
        text = reader.pages[0].extract_text()
    except Exception as exc:  # pypdf can raise several different error types
        raise GjepcScrapeError(f"Could not read GJEPC PDF: {exc}") from exc

    gold_match = re.search(
        r"GOLD\s*\$\s*([\d,]+\.?\d*)\s*PER T\.O\.\s*\(([\d.]+)\).*?(\d{2}/\d{2}/\d{4})",
        text,
        re.DOTALL,
    )
    usd_match = re.search(r"US DOLLAR\s+([\d,]+\.?\d*)", text)
    eur_match = re.search(r"EURO\s+([\d,]+\.?\d*)", text)

    if not (gold_match and usd_match):
        raise GjepcScrapeError("Could not parse gold/USD rate out of GJEPC PDF text")

    gold_usd_per_oz = float(gold_match.group(1).replace(",", ""))
    purity = float(gold_match.group(2))
    effective_date = gold_match.group(3)
    usd_inr = float(usd_match.group(1).replace(",", ""))
    eur_inr = float(eur_match.group(1).replace(",", "")) if eur_match else None

    gold_inr_per_gram = (gold_usd_per_oz / TROY_OUNCE_GRAMS) * usd_inr

    return {
        "gold_usd_per_oz": gold_usd_per_oz,
        "purity": purity,
        "gold_inr_per_gram": gold_inr_per_gram,
        "usd_inr": usd_inr,
        "eur_inr": eur_inr,
        "effective_date": effective_date,
        "pdf_url": pdf_url,
    }
