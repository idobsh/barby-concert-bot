from src.barby_api_scraper import BarbyApiScraper
import json


def test_api_connection():
    """Test if we can connect to the API"""
    print("🔗 Testing API connection...")

    scraper = BarbyApiScraper()
    raw_data = scraper.get_shows_raw()

    if raw_data:
        print("✅ API connection successful!")
        print(f"📊 Raw response keys: {list(raw_data.keys())}")

        if "returnShow" in raw_data:
            shows = raw_data["returnShow"].get("show", [])
            if isinstance(shows, dict):
                shows = [shows]
            print(f"🎵 Found {len(shows)} shows in response")

            # Show sample raw data
            if shows:
                print("\n📋 Sample show data:")
                sample = shows[0]
                for key, value in list(sample.items())[:8]:  # Show first 8 fields
                    print(f"   {key}: {value}")
                if len(sample) > 8:
                    print(f"   ... and {len(sample) - 8} more fields")

        return True
    else:
        print("❌ API connection failed")
        return False


def test_parsing():
    """Test parsing the API response"""
    print("\n🔧 Testing data parsing...")

    scraper = BarbyApiScraper()
    concerts = scraper.get_concerts()

    if concerts:
        print(f"✅ Parsing successful! Got {len(concerts)} concerts")

        # Show first concert in detail
        if concerts:
            concert = concerts[0]
            print("\n🎤 First concert details:")
            for key, value in concert.items():
                if key != "raw_data":  # Skip raw data for cleaner output
                    print(f"   {key}: {value}")

        return True
    else:
        print("❌ Parsing failed - no concerts returned")
        return False


def test_upcoming_filter():
    """Test filtering for upcoming concerts"""
    print("\n📅 Testing upcoming concerts filter...")

    scraper = BarbyApiScraper()
    upcoming = scraper.get_upcoming_concerts(days_ahead=60)

    if upcoming is not None:
        print(f"✅ Filter working! Found {len(upcoming)} upcoming concerts")

        for concert in upcoming[:3]:  # Show first 3
            print(f"   - {concert['artist']} on {concert['date']}")

        return True
    else:
        print("❌ Filter failed")
        return False


def main():
    """Run all tests"""
    print("🎭 Barby API Scraper Test Suite")
    print("=" * 40)

    # Run tests
    test1 = test_api_connection()
    test2 = test_parsing() if test1 else False
    test3 = test_upcoming_filter() if test2 else False

    # Results
    print("\n📊 Test Results:")
    print(f"   API Connection: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"   Data Parsing: {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"   Date Filtering: {'✅ PASS' if test3 else '❌ FAIL'}")

    if all([test1, test2, test3]):
        print("\n🎉 All tests passed! API scraper is ready.")

        # Ask if user wants to see full concert list
        choice = input("\nShow full concert list? (y/n): ").strip().lower()
        if choice == "y":
            scraper = BarbyApiScraper()
            concerts = scraper.get_concerts()
            scraper.print_concerts(concerts)
    else:
        print("\n❌ Some tests failed. Check the issues above.")


if __name__ == "__main__":
    main()
