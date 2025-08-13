import os
import asyncio

from redis_logic.redis_concert_cache import RedisConcertCache

# Set your environment
from dotenv import load_dotenv
load_dotenv()
os.environ["REDIS_HOST"] = "localhost"  # Your local Redis

from aws_lambda.lambda_function import BarbyConcertNotifier

# Paste a REAL concert object from Barby API here:
real_concert = {
    "showId": "5286",
    "showDate": "20/08/2025",
    "showTime": "20:30",
    "showSold": 1105,
    "showSoldMaxBuy": "1000",
    "showNum2SoldOut": "510",
    "showPrice": "185",
    "showTierPriceType": "1",
    "showName": "מושיק עפיה",
    "showImage": "מושיק.jpg",
    "showTitle": "שובר שתיקה- הופעה מלאה בליווי 8 נגנים",
    "showSeatType": "מופע עמידה",
    "showType": "1",
    "showShortTitle": "שובר שתיקה- הופעה מלאה בליווי 8 נגנים",
    "showShortLogo": "",
    "showM_logo2Active": "0",
    "showM_showHome": "1",
    "notbybarbtsellsoldout": "0",
}

cache = RedisConcertCache(
    host=("localhost"),  # Your Redis endpoint
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
)


async def test_notification():
    print("🧪 Testing real notification...")

    # Create notifier
    notifier = BarbyConcertNotifier(cache=cache)

    # Check if you're subscribed
    subscriber_count = notifier.cache.get_subscriber_count()
    print(f"👥 Subscribers: {subscriber_count}")

    if subscriber_count == 0:
        print("❌ No subscribers! Make sure you subscribed via /subscribe first")
        return

    # Test with the real concert
    await notifier.notify_new_concerts([real_concert])
    print("✅ Test notification sent!")


if __name__ == "__main__":
    asyncio.run(test_notification())
