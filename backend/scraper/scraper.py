import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from backend.scraper.parser import parse_inventory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots"


def fetch_html(url):
    """Download HTML from a permitted public webpage."""
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "AutoMatch/0.1"
            },
        )
        response.raise_for_status()
        return response.text

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed to fetch {url}: {exc}"
        ) from exc


def scrape_inventory_page(url):
    """Fetch and parse a single inventory page."""
    html = fetch_html(url)
    return parse_inventory(html)


def save_snapshot(vehicles):
    """Save parsed vehicle data to a JSON snapshot."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_path = SNAPSHOT_DIR / f"inventory_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(vehicles, file, indent=2, ensure_ascii=False)

    return output_path


def scrape_inventory_pages(urls):
    """
    Fetch multiple inventory pages and deduplicate vehicles.

    Raise an error if any page fails, so partial results
    are never treated as a complete inventory scan.
    """
    if not urls:
        raise ValueError("No inventory URLs provided")

    vehicles = []
    seen_ids = set()

    for page_number, url in enumerate(urls, start=1):
        print(f"Scraping page {page_number}/{len(urls)}: {url}")

        try:
            page_vehicles = scrape_inventory_page(url)
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(
                f"Inventory scan incomplete. "
                f"Page {page_number} failed: {exc}"
            ) from exc

        for vehicle in page_vehicles:
            vehicle_id = vehicle["source_listing_id"]

            if vehicle_id not in seen_ids:
                seen_ids.add(vehicle_id)
                vehicles.append(vehicle)

    print(f"Successfully collected {len(vehicles)} vehicles")
    return vehicles
