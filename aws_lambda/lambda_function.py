import json
import asyncio
import logging
import os
from datetime import datetime

# Your existing classes
from src.barby_api_scraper import BarbyApiScraper
from redis_logic.redis_concert_cache import RedisConcertCache

# For Telegram
from telegram import Bot

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("lambda_function.log"), logging.StreamHandler()],
)


class BarbyConcertNotifier:
    def __init__(self, cache: RedisConcertCache):
        self.cache = cache
        self.bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])

    async def notify_new_concerts(self, new_concerts):
        """Send individual notifications with images for each new concert"""
        if not new_concerts:
            return

        num_of_subscribers = self.cache.get_subscriber_count()
        if num_of_subscribers == 0:
            logger.info("📢 No subscribers to notify")
            return

        logger.info(
            f"📢 Sending {len(new_concerts)} individual notifications to {num_of_subscribers} subscribers"
        )

        # Send each concert as separate message
        for concert in new_concerts:
            await self.send_concert_notification(concert)
            # Small delay between concerts to avoid rate limiting
            await asyncio.sleep(0.5)

    async def send_concert_notification(self, concert):
        """Send notification for a single concert with image"""

        # Format message for single concert
        message = self.format_single_concert_message(concert)

        # Get image URL
        image_url = self.get_concert_image_url(concert)

        # Send to all subscribers
        subscribers = self.cache.get_all_subscribers()

        for subscriber in subscribers.copy():
            user_id = subscriber["user_id"]
            try:
                if image_url:
                    # Send photo with caption
                    await self.bot.send_photo(
                        chat_id=user_id,
                        photo=image_url,
                        caption=message,
                        parse_mode="HTML",
                    )
                    logger.info(f"✅ Concert photo sent to {user_id}")
                else:
                    # No image, send text only
                    await self.bot.send_message(
                        chat_id=user_id, text=message, parse_mode="HTML"
                    )
                    logger.info(f"✅ Concert text sent to {user_id}")

                await asyncio.sleep(0.1)  # Rate limiting between users

            except Exception as e:
                logger.error(
                    f"❌ Failed to send concert notification to {user_id}: {e}"
                )

                # Handle image errors gracefully
                if "photo" in str(e).lower() and image_url:
                    try:
                        # Retry with text only if image fails
                        await self.bot.send_message(
                            chat_id=user_id, text=message, parse_mode="HTML"
                        )
                        logger.info(f"✅ Fallback text sent to {user_id}")
                    except:
                        pass

                # Remove invalid subscribers
                if (
                    "chat not found" in str(e).lower()
                    or "bot was blocked" in str(e).lower()
                ):
                    self.cache.remove_subscriber(user_id)
                    logger.info(f"🗑️ Removed invalid subscriber: {user_id}")

    def format_single_concert_message(self, concert):
        """Format message for a single concert"""
        artist = concert.get("showName", "Unknown Artist").strip()
        title = concert.get("showTitle", "").strip()
        short_title = concert.get("showShortTitle", "").strip()
        date = concert.get("showDate", "")
        time = concert.get("showTime", "")
        price = concert.get("showPrice", "")
        show_id = concert.get("showId", "")
        seat_type = concert.get("showSeatType", "")

        # Check if sold out
        is_sold_out = concert.get("notbybarbtsellsoldout", "0") == "1"
        status = " 🔴 <b>אזל כרטיסים</b>" if is_sold_out else ""

        # Price formatting
        price_text = f"₪{price}" if price else "TBA"

        # Date and time
        datetime_str = f"{date} {time}" if date and time else date or "TBA"

        # Build URL
        url = (
            f"https://barby.co.il/show/{show_id}" if show_id else "https://barby.co.il"
        )

        # Build message
        message = f"🆕 <b>הופעה חדשה בבארבי!</b>\n\n"
        message += f"🎵 <b>{artist}</b>\n"

        # Add title if different and meaningful
        display_title = title or short_title
        if display_title and display_title != artist and len(display_title.strip()) > 3:
            clean_title = " ".join(display_title.split())
            message += f"📝 <i>{clean_title}</i>\n"

        message += f"📅 {datetime_str}\n"
        message += f"💰 {price_text}"
        if seat_type:
            message += f" • {seat_type}"
        message += f"{status}\n"
        message += f'🎫 <a href="{url}">קניית כרטיסים</a>\n\n'

        message += "🔔 הודעה מבוט התראות בארבי"

        return message

    def get_concert_image_url(self, concert):
        """Get image URL for concert"""
        show_image = concert.get("showImage", "")
        if show_image:
            clean_image = show_image.strip()
            return f"https://images.barby.co.il/Logos/{clean_image}"
        return None


def lambda_handler(event, context):
    try:
        # Initialize scraper and cache
        logger.info("🔄 Initializing Barby API scraper and Redis cache")
        scraper = BarbyApiScraper()
        cache = RedisConcertCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
        )
        concert_notifier = BarbyConcertNotifier(cache=cache)
        # 2. Get current concerts
        logger.info("📅 Fetching current concerts from Barby API")
        concerts = scraper.get_concerts()
        if not concerts:
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No concerts found"}),
            }
        current_concerts = {concert["show_id"]: concert for concert in concerts}
        # Load last concerts from Redis
        logger.info("🔍 Loading last concerts from Redis")
        last_concerts, _ = cache.load_last_state()

        # Compare current concerts with last concerts
        new_concerts = []
        for concert_id, concert in current_concerts.items():
            if concert_id not in last_concerts:
                new_concerts.append(concert)

        if new_concerts:
            logger.info(f"🔔 New concerts: {len(new_concerts)}")

            # Save current concerts to Reds
            cache.save_state(current_concerts)

            # Notify via Telegram
            asyncio.run(concert_notifier.notify_new_concerts(new_concerts))
        else:
            logger.info("ℹ️ No changes detected")
        return {"statusCode": 200, "body": json.dumps("Success!")}
    except Exception as e:
        logger.error(f"❌ Error during concert check: {e}")
