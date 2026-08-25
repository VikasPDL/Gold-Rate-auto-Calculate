"""Live gold rate scraper.

Ronak Gold (https://www.ronakgold.com/) publishes live gold/silver rates via a
public VOTS broadcast feed embedded in their homepage JS (LiveRateMessage.Chirayu.js).
The feed is plain tab-separated text, CORS-open, no auth required:

    https://ronakgold.noip.us:7666/VOTSBroadcastStreaming/Services/xml/GetLiveRateByTemplateID/goldcoins995mumbai

Each line: <id> <label> <ltp> <ltp2> <high> <low> <TODAY/date-flag>
We read the "1 GM" row as the base rate for 0.995 fine gold, per gram.
"""
import requests
import urllib3

GOLD_995_URL = (
    "https://ronakgold.noip.us:7666/VOTSBroadcastStreaming/"
    "Services/xml/GetLiveRateByTemplateID/goldcoins995mumbai"
)


class ScrapeError(Exception):
    pass


def fetch_gold_995_rate_per_gram(timeout=8):
    """Returns the live rate (float, rupees per gram) for 0.995 fine gold."""
    try:
        try:
            resp = requests.get(GOLD_995_URL, timeout=timeout)
        except requests.exceptions.SSLError:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = requests.get(GOLD_995_URL, timeout=timeout, verify=False)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ScrapeError(f"Could not reach gold rate feed: {exc}") from exc

    for line in resp.text.splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip() != ""]
        if len(parts) >= 3 and parts[1].upper() == "1 GM":
            try:
                return float(parts[2])
            except ValueError as exc:
                raise ScrapeError(f"Unexpected rate value: {parts[2]}") from exc

    raise ScrapeError("Could not find '1 GM' row in feed response")
