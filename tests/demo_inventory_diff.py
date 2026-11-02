
from pprint import pprint

from backend.inventory.diff_engine import compare_inventories


yesterday = [
    {
        "source_listing_id": "101",
        "title": "2022 BMW 330i",
        "price_cash": 35000,
    },
    {
        "source_listing_id": "102",
        "title": "2021 Mercedes C300",
        "price_cash": 42000,
    },
    {
        "source_listing_id": "103",
        "title": "2020 Audi A4",
        "price_cash": 28000,
    },
]

today = [
    {
        "source_listing_id": "101",
        "title": "2022 BMW 330i",
        "price_cash": 32000,
    },
    {
        "source_listing_id": "103",
        "title": "2020 Audi A4",
        "price_cash": 28000,
    },
    {
        "source_listing_id": "104",
        "title": "2023 Lexus IS350",
        "price_cash": 46000,
    },
]

result = compare_inventories(yesterday, today)

print("\nINVENTORY CHANGE SUMMARY")
pprint(result["summary"])

print("\nUPDATED VEHICLES")
pprint(result["updated"])

print("\nADDED VEHICLES")
pprint(result["added"])

print("\nREMOVED VEHICLES")
pprint(result["removed"])
