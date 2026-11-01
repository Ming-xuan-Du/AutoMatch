from unittest.mock import Mock, patch

import pytest
import requests

from backend.scraper.scraper import fetch_html


def test_fetch_html_success():
    mock_response = Mock()
    mock_response.text = "<html>Vehicle inventory</html>"
    mock_response.raise_for_status.return_value = None

    with patch(
        "backend.scraper.scraper.requests.get",
        return_value=mock_response
    ) as mock_get:
        html = fetch_html("https://example.com/inventory")

    assert html == "<html>Vehicle inventory</html>"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["timeout"] == 15


def test_fetch_html_http_error():
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = (
        requests.HTTPError("404 Not Found")
    )

    with patch(
        "backend.scraper.scraper.requests.get",
        return_value=mock_response
    ):
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            fetch_html("https://example.com/missing")


def test_fetch_html_timeout():
    with patch(
        "backend.scraper.scraper.requests.get",
        side_effect=requests.Timeout("Request timed out")
    ):
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            fetch_html("https://example.com/inventory")


from backend.scraper.scraper import scrape_inventory_pages


def test_multiple_pages():
    page_1 = [
        {"source_listing_id": "100"},
        {"source_listing_id": "200"},
    ]

    page_2 = [
        {"source_listing_id": "300"},
    ]

    with patch(
        "backend.scraper.scraper.scrape_inventory_page",
        side_effect=[page_1, page_2]
    ) as mock_scrape:
        vehicles = scrape_inventory_pages([
            "https://example.com/page1",
            "https://example.com/page2",
        ])

    assert len(vehicles) == 3
    assert mock_scrape.call_count == 2


def test_duplicate_vehicles_across_pages():
    page_1 = [
        {"source_listing_id": "100"},
        {"source_listing_id": "200"},
    ]

    page_2 = [
        {"source_listing_id": "200"},
        {"source_listing_id": "300"},
    ]

    with patch(
        "backend.scraper.scraper.scrape_inventory_page",
        side_effect=[page_1, page_2]
    ):
        vehicles = scrape_inventory_pages([
            "https://example.com/page1",
            "https://example.com/page2",
        ])

    ids = [v["source_listing_id"] for v in vehicles]

    assert ids == ["100", "200", "300"]

def test_failed_page_aborts_scan():
    with patch(
        "backend.scraper.scraper.scrape_inventory_page",
        side_effect=[
            [{"source_listing_id": "100"}],
            RuntimeError("Connection timeout"),
        ]
    ):
        with pytest.raises(
            RuntimeError,
            match="Inventory scan incomplete"
        ):
            scrape_inventory_pages([
                "https://example.com/page1",
                "https://example.com/page2",
            ])


def test_empty_url_list():
    with pytest.raises(
        ValueError,
        match="No inventory URLs provided"
    ):
        scrape_inventory_pages([])
