import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib

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



def save_snapshot(
    vehicles,
    *,
    expected_count=None,
    validated=False,
    source_url=None,
):
    """
    Save vehicle data as a JSON file.

    A completeness metadata file is created only when
    the caller has completed inventory validation.
    """

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    if validated:
        if (
            expected_count is None
            or expected_count <= 0
            or len(vehicles) != expected_count
        ):
            raise ValueError(
                "Cannot certify an incomplete inventory"
            )

        if not source_url:
            raise ValueError(
                "A certified snapshot needs a source URL"
            )

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_path = (
        SNAPSHOT_DIR / f"inventory_{timestamp}.json"
    )

    json_text = json.dumps(
        vehicles,
        indent=2,
        ensure_ascii=False,
    )

    content = json_text.encode("utf-8")

    # Save the vehicle records.
    output_path.write_bytes(content)

    # Only validated crawls receive a completion receipt.
    if validated:
        receipt = {
            "schema_version": 1,
            "crawl_id": output_path.stem,
            "source_url": source_url,
            "expected_count": expected_count,
            "vehicle_count": len(vehicles),
            "pages_expected": 1,
            "pages_seen": 1,
            "is_complete": True,
            "validation_passed": True,
            "snapshot_sha256": hashlib.sha256(
                content
            ).hexdigest(),
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        receipt_path = output_path.with_suffix(
            ".meta.json"
        )

        receipt_path.write_text(
            json.dumps(
                receipt,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

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
