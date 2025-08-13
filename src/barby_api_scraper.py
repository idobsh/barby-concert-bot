import requests
import json
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BarbyApiScraper:
    def __init__(self):
        self.api_url = "https://barby.co.il/api/shows/find"
        self.base_url = "https://barby.co.il"
        self.session = requests.Session()

        # Set realistic headers
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://barby.co.il/",
                "Origin": "https://barby.co.il",
                "Connection": "keep-alive",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def get_shows_raw(self) -> Optional[Dict]:
        """Get raw JSON data from the API"""
        try:
            logger.info(f"🔗 Fetching shows from API: {self.api_url}")

            response = self.session.get(self.api_url, timeout=15)
            response.raise_for_status()

            logger.info(f"✅ API response: {response.status_code}")
            logger.info(f"📊 Response size: {len(response.content)} bytes")

            # Parse JSON
            data = response.json()

            if "returnShow" in data and "show" in data["returnShow"]:
                shows = data["returnShow"]["show"]
                logger.info(f"🎵 Found {len(shows)} shows in API response")
                return data
            else:
                logger.warning("⚠️  Unexpected API response structure")
                logger.info(f"📋 Response keys: {list(data.keys())}")
                return data

        except requests.RequestException as e:
            logger.error(f"❌ API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"📄 Response content: {response.text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return None

    def parse_show(self, show_data: Dict) -> Dict:
        """Parse a single show from the API response"""
        try:
            # Extract basic info
            show_id = show_data.get("showId", "")
            show_name = show_data.get("showName", "Unknown Artist")
            show_title = show_data.get("showTitle", "")
            show_short_title = show_data.get("showShortTitle", "")

            # Date and time
            show_date = show_data.get("showDate", "")
            show_time = show_data.get("showTime", "")

            # Ticket info
            show_price = show_data.get("showPrice", "")
            show_sold = show_data.get("showSold", 0)
            show_sold_max = show_data.get("showSoldMaxBuy", "")
            seat_type = show_data.get("showSeatType", "")

            # Check if sold out
            is_sold_out = show_data.get("notbybarbtsellsoldout", "0") == "1"

            # Create full datetime string
            datetime_str = (
                f"{show_date} {show_time}" if show_date and show_time else show_date
            )

            # Parse date for sorting/filtering
            event_date = None
            if show_date:
                try:
                    event_date = datetime.strptime(show_date, "%d/%m/%Y")
                except ValueError:
                    logger.warning(f"⚠️  Could not parse date: {show_date}")

            # Create show URL
            show_url = f"{self.base_url}/show/{show_id}" if show_id else self.base_url

            # Create unique ID for the show
            unique_id = hashlib.md5(
                f"{show_id}_{show_date}_{show_time}".encode("utf-8")
            ).hexdigest()

            # Determine display title
            display_title = show_title or show_short_title or show_name

            return {
                "id": unique_id,
                "show_id": show_id,
                "artist": show_name,
                "title": display_title,
                "full_title": show_title,
                "short_title": show_short_title,
                "date": show_date,
                "time": show_time,
                "datetime": datetime_str,
                "event_date": event_date,
                "price": show_price,
                "sold_tickets": int(show_sold) if str(show_sold).isdigit() else 0,
                "max_tickets": show_sold_max,
                "seat_type": seat_type,
                "is_sold_out": is_sold_out,
                "url": show_url,
                "raw_data": show_data,
            }

        except Exception as e:
            logger.error(f"❌ Error parsing show data: {e}")
            logger.error(f"📄 Show data: {show_data}")
            return None

    def get_concerts(self) -> List[Dict]:
        """Get all concerts from the API"""
        logger.info("🎵 Starting Barby API scraping...")

        # Get raw data
        raw_data = self.get_shows_raw()
        if not raw_data:
            logger.error("❌ Failed to get data from API")
            return []

        # Extract shows
        shows = []
        if "returnShow" in raw_data and "show" in raw_data["returnShow"]:
            shows_data = raw_data["returnShow"]["show"]

            # Handle both single show and array of shows
            if isinstance(shows_data, dict):
                shows_data = [shows_data]

            logger.info(f"📊 Processing {len(shows_data)} shows...")

            for show_data in shows_data:
                parsed_show = self.parse_show(show_data)
                if parsed_show:
                    shows.append(parsed_show)

        # Sort by date
        shows.sort(key=lambda x: x["event_date"] or datetime.min)

        logger.info(f"✅ Successfully parsed {len(shows)} concerts")
        return shows

    def get_upcoming_concerts(self, days_ahead: int = 365) -> List[Dict]:
        """Get only upcoming concerts within specified days"""
        all_concerts = self.get_concerts()

        if not all_concerts:
            return []

        # Filter upcoming concerts
        today = datetime.now().date()
        upcoming = []

        for concert in all_concerts:
            if concert["event_date"]:
                event_date = concert["event_date"].date()
                days_diff = (event_date - today).days

                if 0 <= days_diff <= days_ahead:
                    upcoming.append(concert)

        logger.info(
            f"🔜 Found {len(upcoming)} upcoming concerts (next {days_ahead} days)"
        )
        return upcoming

    def print_concerts(self, concerts: List[Dict], max_concerts: int = 10):
        """Print concerts in a nice format"""
        if not concerts:
            print("❌ No concerts found")
            return

        print(f"\n🎵 Found {len(concerts)} concerts:")
        print("=" * 80)

        for i, concert in enumerate(concerts[:max_concerts], 1):
            print(f"\n🎤 Concert {i}:")
            print(f"   Artist: {concert['artist']}")
            print(f"   Title: {concert['title']}")
            print(f"   Date: {concert['datetime']}")
            print(
                f"   Price: ₪{concert['price']}"
                if concert["price"]
                else "   Price: TBA"
            )
            print(f"   Seat Type: {concert['seat_type']}")
            print(f"   Sold Out: {'Yes' if concert['is_sold_out'] else 'No'}")
            print(
                f"   Tickets Sold: {concert['sold_tickets']}/{concert['max_tickets']}"
            )
            print(f"   URL: {concert['url']}")

        if len(concerts) > max_concerts:
            print(f"\n... and {len(concerts) - max_concerts} more concerts")


def main():
    """Test the API scraper"""
    scraper = BarbyApiScraper()

    print("🎭 Barby API Scraper Test")
    print("=" * 30)

    # Test 1: Get all concerts
    print("\n1️⃣ Testing: Get all concerts")
    all_concerts = scraper.get_concerts()
    scraper.print_concerts(all_concerts, max_concerts=5)

    # Test 2: Get upcoming concerts only
    print("\n2️⃣ Testing: Get upcoming concerts (next 90 days)")
    upcoming = scraper.get_upcoming_concerts(days_ahead=90)
    scraper.print_concerts(upcoming, max_concerts=3)

    # Test 3: Check for sold out shows
    sold_out = [c for c in all_concerts if c["is_sold_out"]]
    if sold_out:
        print(f"\n🔴 Found {len(sold_out)} sold out shows:")
        for show in sold_out[:3]:
            print(f"   - {show['artist']} on {show['date']}")
    else:
        print("\n🟢 No sold out shows found")

    print("\n" + "=" * 50)
    print("✅ API scraper test completed!")


if __name__ == "__main__":
    main()
