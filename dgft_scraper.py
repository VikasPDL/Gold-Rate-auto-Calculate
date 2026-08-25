"""Live currency exchange rates (Import/Export) from DGFT's customs-notified rate list.

https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates

The page's DataTable pulls its data from one POST endpoint that returns *all*
currencies in a single non-paginated response (serverSide: false) — the "3 pages"
seen in the UI is just client-side paging over that one payload, so one request
here already covers every currency the page shows.

The POST requires a session cookie + CSRF token obtained from the page itself,
and the form payload must be sent using jQuery's bracket-notation encoding
(dataJson[formData]=<json string>), not a plain JSON body.
"""
import re

import requests

PAGE_URL = "https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates"
API_PATH = (
    "https://www.dgft.gov.in/CP/webHP?requestType=ApplicationRH&actionVal=service"
    "&screen=viewRates&screenId=9000012354&_csrf={token}"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


class DgftScrapeError(Exception):
    pass


def fetch_export_rates(timeout=20):
    """Returns a list of dicts: code, name, units, import_rate, export_rate, effective_date.

    export_rate / import_rate are INR per `units` of foreign currency
    (units is usually 1, but 100 for low-value currencies like JPY/KRW).
    """
    session = requests.Session()
    try:
        page = session.get(PAGE_URL, headers=_HEADERS, timeout=timeout)
        page.raise_for_status()
    except requests.RequestException as exc:
        raise DgftScrapeError(f"Could not reach DGFT rates page: {exc}") from exc

    match = re.search(r'name="_csrf" content="([^"]+)"', page.text)
    if not match:
        raise DgftScrapeError("Could not find CSRF token on DGFT rates page")
    token = match.group(1)

    post_headers = dict(_HEADERS)
    post_headers.update(
        {
            "Referer": PAGE_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.dgft.gov.in",
        }
    )
    form_data = {"currencyCodeInput": "", "dateFrom": "", "dateTo": ""}

    try:
        resp = session.post(
            API_PATH.format(token=token),
            headers=post_headers,
            data={"dataJson[formData]": __import__("json").dumps(form_data)},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise DgftScrapeError(f"DGFT rates request failed: {exc}") from exc

    rows = payload.get("data") if isinstance(payload, dict) else None
    if not rows:
        raise DgftScrapeError("DGFT response contained no currency rows")

    result = []
    for row in rows:
        try:
            result.append(
                {
                    "code": row["currcode"],
                    "name": row["currname"],
                    "units": row.get("fcrUnit") or 1,
                    "import_rate": row.get("importval"),
                    "export_rate": row.get("expovalue"),
                    "effective_date": row.get("effdate"),
                }
            )
        except KeyError:
            continue

    if not result:
        raise DgftScrapeError("DGFT response rows missing expected fields")

    result.sort(key=lambda r: r["code"])
    return result
