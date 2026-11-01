
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from backend.scraper.normalizer import normalize_number

from bs4 import BeautifulSoup


BASE_URL = "https://cccmotors.ca"



def parse_vehicle(html):
    """Extract vehicle information from one HTML vehicle card."""

    soup = BeautifulSoup(html, "html.parser")

    vehicle = soup.select_one('div[id^="vehicle-"]')

    if vehicle is None:
        raise ValueError("Vehicle card not found")

    # 1. Vehicle ID
    vehicle_id = vehicle.get("id").replace("vehicle-", "", 1)

    # 2. Vehicle title
    title_element = vehicle.select_one("a.inventory_a__title_2")

    title = (
        title_element.get_text(strip=True)
        if title_element
        else None
    )

    # 3. Vehicle listing URL
    listing_url = (
        urljoin(BASE_URL, title_element.get("href"))
        if title_element and title_element.get("href")
        else None
    )

    # 4. Vehicle image
    image_element = vehicle.select_one("img.inventory_img")

    image_url = (
        urljoin(BASE_URL, image_element.get("src"))
        if image_element and image_element.get("src")
        else None
    )

    # 5. Cash and finance prices
    cash_price = None
    finance_price = None

    price_rows = vehicle.select("p.inventory_p__price")

    for row in price_rows:
        spans = row.find_all("span", recursive=False)

        if len(spans) < 2:
            continue

        label = spans[0].get_text(strip=True).lower()
        price = normalize_number(spans[1].get_text(strip=True))

        if "cash price" in label:
            cash_price = price

        elif "finance price" in label:
            finance_price = price

    # 6. Extract vehicle specifications
    specifications = {}

    spec_rows = vehicle.select("div.inventory_div__cell")

    for row in spec_rows:
        paragraphs = row.find_all("p", recursive=False)

        if len(paragraphs) < 2:
            continue

        label = (
            paragraphs[0]
            .get_text(strip=True)
            .replace(":", "")
            .strip()
            .lower()
        )

        value = paragraphs[1].get_text(strip=True)

        specifications[label] = value

    # 7. Extract year from title
    year = None

    if title:
        year_match = re.match(r"^(19|20)\d{2}\b", title)

        if year_match:
            year = int(year_match.group())

    # 8. Create structured vehicle dictionary
    vehicle_data = {
        "source_listing_id": vehicle_id,
        "title": title,
        "year": year,
        "price_cash": cash_price,
        "price_finance": finance_price,
        "mileage_km": normalize_number(
            specifications.get("odometer")
        ),
        "exterior_color": specifications.get("exterior color"),
        "stock_no": specifications.get("stock #"),
        "doors": normalize_number(specifications.get("doors")),
        "body_style": specifications.get("body style"),
        "transmission": specifications.get("transmission"),
        "drivetrain": specifications.get("drivetrain"),
        "engine": specifications.get("engine"),
        "vin": specifications.get("vin"),
        "listing_url": listing_url,
        "image_url": image_url,
    }

    return vehicle_data

def parse_inventory(html):
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select('div[id^="vehicle-"]')

    if not cards:
        raise ValueError("No vehicle cards found")

    vehicles = []
    seen_ids = set()

    for card in cards:
        vehicle_data = parse_vehicle(str(card))

        vehicle_id = vehicle_data["source_listing_id"]

        if vehicle_id in seen_ids:
            continue

        seen_ids.add(vehicle_id)
        vehicles.append(vehicle_data)

    return vehicles

if __name__ == "__main__":

    project_root = Path(__file__).resolve().parents[2]

    html_path = (
        project_root
        / "data"
        / "fixtures"
        / "inventory_sample.html"
    )

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Parse multiple vehicles
    vehicles = parse_inventory(html)

    print(f"Total vehicles: {len(vehicles)}")

    for vehicle in vehicles:
        print(
            vehicle["source_listing_id"],
            vehicle["title"],
            vehicle["price_cash"]
        )
