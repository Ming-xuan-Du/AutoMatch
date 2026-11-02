
import re

from playwright.sync_api import sync_playwright

from backend.scraper.parser import parse_inventory
from backend.scraper.scraper import save_snapshot
from backend.scraper.snapshot_validator import validate_snapshot



INVENTORY_URL = "https://cccmotors.ca/cars"

CARD_SELECTOR = 'div[id^="vehicle-"]'


def scrape_full_inventory():
    """
    Scroll through the inventory until all expected
    vehicle cards have loaded.
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page(
                viewport={"width": 1440, "height": 900}
            )

            page.goto(
                INVENTORY_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.locator(CARD_SELECTOR).first.wait_for(
                timeout=30000
            )

            # Read the vehicle count displayed by the website.
            count_text = page.get_by_text(
                re.compile(r"^\s*[\d,]+\s+Vehicles\s*$", re.I)
            ).first.inner_text()

            expected_count = int(
                re.search(r"[\d,]+", count_text)
                .group()
                .replace(",", "")
            )

            print(f"Expected vehicles: {expected_count}")

            previous_count = 0
            unchanged_rounds = 0

            for attempt in range(150):
                current_count = page.locator(
                    CARD_SELECTOR
                ).count()

                print(
                    f"Scroll {attempt + 1}: "
                    f"{current_count}/{expected_count}"
                )

                if current_count >= expected_count:
                    break

                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(1200)

                new_count = page.locator(
                    CARD_SELECTOR
                ).count()

                if new_count == previous_count:
                    unchanged_rounds += 1
                else:
                    unchanged_rounds = 0

                previous_count = new_count

                if unchanged_rounds >= 8:
                    raise RuntimeError(
                        "Inventory stopped loading before "
                        "reaching expected count"
                    )

            html = page.content()
            vehicles = parse_inventory(html)

            if len(vehicles) != expected_count:
                raise RuntimeError(
                    f"Incomplete inventory: "
                    f"expected {expected_count}, "
                    f"parsed {len(vehicles)}"
                )

            print(
                f"Successfully scraped "
                f"{len(vehicles)} vehicles"
            )

            # Validate vehicles before saving the snapshot
            validated_vehicles = validate_snapshot(
                vehicles,
                expected_count=expected_count,
            )

            
            snapshot_path = save_snapshot(
                validated_vehicles,
                expected_count=expected_count,
                validated=True,
                source_url=INVENTORY_URL,
            )

            print(f"Snapshot saved: {snapshot_path}")
            print(
                "Completeness metadata saved: "
                f"{snapshot_path.with_suffix('.meta.json')}"
            )

            return validated_vehicles


        finally:
            browser.close()


if __name__ == "__main__":
    scrape_full_inventory()
