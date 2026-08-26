"""
DGFT Official Currency Import / Export Rate Extractor
=====================================================

Extracts ALL currency rows from the official DGFT Currency Exchange
Rates page, including rows hidden behind pagination.

Source:
https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates

Install:
    pip install playwright
    playwright install chromium

Run:
    python dgft_currency_rates.py

Optional:
    python dgft_currency_rates.py --csv dgft_rates.csv
    python dgft_currency_rates.py --json dgft_rates.json
"""

import argparse
import csv
import json
import re
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


DGFT_URL = "https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates"


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def get_table(page):
    """Find the DGFT currency table."""
    tables = page.locator("table")
    count = tables.count()

    # First try the table header.
    for i in range(count):
        table = tables.nth(i)

        if table.locator("thead").count():
            header = clean(table.locator("thead").inner_text())
            if "Import Rate" in header and "Export Rate" in header:
                return table

    # Fallback if DGFT changes the table markup.
    for i in range(count):
        table = tables.nth(i)
        text = clean(table.inner_text())
        if "Import Rate" in text and "Export Rate" in text:
            return table

    return None


def extract_current_page_rows(table):
    """Extract rows currently visible in the DGFT table."""
    records = []

    rows = table.locator("tbody tr")
    count = rows.count()

    for i in range(count):
        cells = rows.nth(i).locator("td")
        cell_count = cells.count()

        values = [
            clean(cells.nth(j).inner_text())
            for j in range(cell_count)
        ]

        # Expected DGFT columns:
        # 0 Currency Code
        # 1 Currency Name
        # 2 Effective Start Date
        # 3 Units
        # 4 Import Rate
        # 5 Export Rate
        if len(values) >= 6:
            # Ignore empty/non-data rows.
            if values[0] and values[1]:
                records.append(
                    {
                        "currency_code": values[0],
                        "currency_name": values[1],
                        "effective_start_date": values[2],
                        "units": values[3],
                        "import_rate": values[4],
                        "export_rate": values[5],
                    }
                )

    return records


def get_pagination_info(page):
    """
    Read DataTables-style pagination information such as:
    'Showing 1 to 10 of 22 entries'
    """
    body = clean(page.locator("body").inner_text())

    match = re.search(
        r"Showing\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+entries",
        body,
        re.IGNORECASE,
    )

    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        total = int(match.group(3))
        return start, end, total

    return None


def click_next_page(page):
    """
    Click the DGFT/DataTables Next button.

    Returns True if a next page was clicked.
    Returns False if the current page is the last page.
    """

    # Common DataTables selectors.
    candidates = [
        "button:has-text('Next')",
        "a:has-text('Next')",
        ".paginate_button.next",
        "li.next a",
        "li.next button",
    ]

    for selector in candidates:
        locator = page.locator(selector)

        if locator.count() == 0:
            continue

        # There can be multiple matching elements. Find the visible one.
        for i in range(locator.count()):
            button = locator.nth(i)

            try:
                if not button.is_visible():
                    continue
            except Exception:
                continue

            classes = (button.get_attribute("class") or "").lower()
            aria_disabled = (
                button.get_attribute("aria-disabled") or ""
            ).lower()

            disabled = button.is_disabled() if button.is_enabled() else True

            if (
                "disabled" in classes
                or aria_disabled == "true"
                or disabled
            ):
                return False

            # Save current pagination text so we can wait for it to change.
            before = get_pagination_info(page)

            try:
                button.click(timeout=10000)
            except Exception:
                continue

            # Wait for the table/pagination to update.
            try:
                page.wait_for_function(
                    """
                    ({before}) => {
                        const text = document.body.innerText;
                        const m = text.match(
                            /Showing\\s+(\\d+)\\s+to\\s+(\\d+)\\s+of\\s+(\\d+)\\s+entries/i
                        );
                        if (!m) return true;
                        const current = [Number(m[1]), Number(m[2]), Number(m[3])];
                        return !before ||
                               current[0] !== before[0] ||
                               current[1] !== before[1];
                    }
                    """,
                    arg={"before": before},
                    timeout=15000,
                )
            except Exception:
                page.wait_for_timeout(1000)

            return True

    return False


def extract_all_rates(page):
    """Extract all DGFT currency rows across all pagination pages."""

    page.goto(
        DGFT_URL,
        wait_until="domcontentloaded",
        timeout=120000,
    )

    # DGFT currently renders "Currency Exchange Rates" twice:
    # breadcrumb + actual heading.
    try:
        page.get_by_role(
            "heading",
            name="Currency Exchange Rates",
            exact=True,
        ).first.wait_for(
            state="visible",
            timeout=60000,
        )
    except PlaywrightTimeoutError:
        pass

    # Wait for the dynamic DGFT application/table.
    page.wait_for_timeout(5000)

    table = get_table(page)

    if table is None:
        raise RuntimeError(
            "DGFT currency table was not found. "
            "The DGFT website structure may have changed."
        )

    all_records = []
    seen = set()

    # Safety limit prevents an accidental infinite pagination loop.
    max_pages = 100

    for page_number in range(1, max_pages + 1):
        # Re-find table because DataTables can redraw the DOM.
        table = get_table(page)

        if table is None:
            raise RuntimeError(
                f"Currency table disappeared while reading page {page_number}."
            )

        current = extract_current_page_rows(table)

        for record in current:
            key = (
                record["currency_code"],
                record["currency_name"],
                record["effective_start_date"],
            )

            if key not in seen:
                seen.add(key)
                all_records.append(record)

        pagination = get_pagination_info(page)

        if pagination:
            start, end, total = pagination
            print(
                f"Page {page_number}: "
                f"showing {start} to {end} of {total} entries "
                f"(collected {len(all_records)})"
            )

            if len(all_records) >= total:
                break
        else:
            print(
                f"Page {page_number}: "
                f"collected {len(current)} rows "
                f"(total collected {len(all_records)})"
            )

        # Click Next. If there is no Next page, we're done.
        if not click_next_page(page):
            break

        page.wait_for_timeout(500)

    return all_records


def save_csv(records, filename):
    fields = [
        "currency_code",
        "currency_name",
        "effective_start_date",
        "units",
        "import_rate",
        "export_rate",
    ]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def save_json(records, filename):
    payload = {
        "source": DGFT_URL,
        "retrieved_at": datetime.now().astimezone().isoformat(),
        "total_entries": len(records),
        "records": records,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2,
        )


def print_rates(records):
    print()
    print("Official DGFT Currency Exchange Rates")
    print("=" * 120)

    print(
        f"{'CODE':<10}"
        f"{'CURRENCY':<32}"
        f"{'EFFECTIVE DATE':<18}"
        f"{'UNITS':<10}"
        f"{'IMPORT RATE':<18}"
        f"{'EXPORT RATE':<18}"
    )

    print("-" * 120)

    for r in records:
        print(
            f"{r['currency_code']:<10}"
            f"{r['currency_name'][:31]:<32}"
            f"{r['effective_start_date']:<18}"
            f"{r['units']:<10}"
            f"{r['import_rate']:<18}"
            f"{r['export_rate']:<18}"
        )

    print("=" * 120)
    print(f"Total entries extracted: {len(records)}")
    print(f"Source: {DGFT_URL}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extract ALL official DGFT currency Import/Export rates."
        )
    )

    parser.add_argument(
        "--csv",
        default="",
        help="Optional CSV output filename.",
    )

    parser.add_argument(
        "--json",
        default="",
        help="Optional JSON output filename.",
    )

    args = parser.parse_args()

    print("Opening official DGFT website...")
    print(DGFT_URL)
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            },
            locale="en-IN",
        )

        try:
            records = extract_all_rates(page)
        finally:
            browser.close()

    if not records:
        raise RuntimeError(
            "No currency records were extracted."
        )

    print_rates(records)

    if args.csv:
        save_csv(records, args.csv)
        print(f"\nCSV saved: {args.csv}")

    if args.json:
        save_json(records, args.json)
        print(f"JSON saved: {args.json}")


if __name__ == "__main__":
    main()
