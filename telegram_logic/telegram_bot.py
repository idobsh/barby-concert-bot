#!/usr/bin/env python3
"""
Barby Concert Telegram Bot - Compatible with python-telegram-bot v22.3
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import os

load_dotenv()
# Import your existing scraper
from src.barby_api_scraper import BarbyApiScraper
from redis_logic.redis_concert_cache import RedisConcertCache

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

cache = RedisConcertCache(
    host=os.getenv("REDIS_HOST", "localhost"),  # Your Redis endpoint
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
)


class BarbyTelegramBot:
    """Telegram bot for Barby concert notifications"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.scraper = BarbyApiScraper()
        self.application = None

        logger.info("🤖 Barby Telegram Bot initialized")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user

        welcome_message = f"""
🎭 Welcome to Barby Concert Alerts, {user.first_name}!

I help you stay updated with concerts at Barby Tel Aviv.

🎵 <b>Available commands:</b>
/start - This welcome message
/subscribe - Get notifications for new concerts
/unsubscribe - Stop notifications  
Ready to get started? 🎶
        """

        await update.message.reply_text(welcome_message, parse_mode="HTML")
        logger.info(f"User {user.first_name} ({user.id}) started the bot")

    async def subscribe_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /subscribe command"""
        user = update.effective_user
        user_id = user.id

        # Add to Redis
        if cache.subscriber_exists(user_id):
            message = f"🔔 {user.first_name}, you're already subscribed to Barby concert alerts!"
        else:
            cache.add_subscriber(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
            )
            message = f"""
            🔔 <b>Subscription Activated!</b>

            Hi {user.first_name}, you're now subscribed to Barby concert alerts!

            <b>What happens next:</b>
            • I'll notify you when new concerts are announced
            • You'll get instant alerts for new shows
            • Each notification includes artist, date, and ticket link

            <b>Unsubscribe:</b> Use /unsubscribe anytime

            Welcome aboard! 🎵
            """
            logger.info(
                f"User {user.first_name} ({user_id}) subscribed. Total subscribers: {cache.get_subscriber_count()}"
            )

        await update.message.reply_text(message, parse_mode="HTML")

    async def unsubscribe_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /unsubscribe command"""
        user = update.effective_user
        user_id = user.id

        if cache.subscriber_exists(user_id):
            cache.remove_subscriber(user_id)
            message = f"""
        🔕 <b>Unsubscribed</b>

        {user.first_name}, you've been unsubscribed from Barby concert alerts.

        You won't receive any more notifications.

        Want to subscribe again? Just use /subscribe anytime! 👋
                    """
            logger.info(
                f"User {user.first_name} ({user_id}) unsubscribed. Total subscribers: {cache.get_subscriber_count()}"
            )
        else:
            message = f"🔕 {user.first_name}, you weren't subscribed to notifications."

        await update.message.reply_text(message, parse_mode="HTML")

    def _format_concerts_message(self, concerts, header=""):
        """Format concerts for display"""
        message = header

        for i, concert in enumerate(
            concerts[:5], 1
        ):  # Limit to 5 concerts for notifications
            # Extract data from concert object
            artist = concert.get("showName", "Unknown Artist").strip()
            title = concert.get("showTitle", "").strip()
            short_title = concert.get("showShortTitle", "").strip()
            date = concert.get("showDate", "")
            time = concert.get("showTime", "")
            price = concert.get("showPrice", "")
            show_id = concert.get("showId", "")

            # Check if sold out
            is_sold_out = concert.get("notbybarbtsellsoldout", "0") == "1"

            # Status indicators
            status = ""
            if is_sold_out:
                status = " 🔴 <b>אזל כרטיסים</b>"

            # Price formatting
            price_text = f"₪{price}" if price else "TBA"

            # Date and time
            datetime_str = f"{date} {time}" if date and time else date or "TBA"

            # Build URL
            url = (
                f"https://barby.co.il/show/{show_id}"
                if show_id
                else "https://barby.co.il"
            )

            # Format message
            message += f"🎵 <b>{artist}</b>\n"

            # Add title if different and meaningful
            display_title = title or short_title
            if (
                display_title
                and display_title != artist
                and len(display_title.strip()) > 3
            ):
                # Clean up title (remove extra whitespace and newlines)
                clean_title = " ".join(display_title.split())
                message += f"📝 <i>{clean_title}</i>\n"

            message += f"📅 {datetime_str}\n"
            message += f"💰 {price_text}"
            message += f"{status}\n"
            message += f'🎫 <a href="{url}">קניית כרטיסים</a>\n\n'

        if len(concerts) > 5:
            message += f"<i>... ועוד {len(concerts) - 5} הופעות נוספות</i>\n"

        return message

    async def notify_new_concerts(self, new_concerts):
        """Send notifications for new concerts to all subscribers"""
        if not new_concerts:
            return

        num_of_subscribers = cache.get_subscriber_count()

        if num_of_subscribers == 0:
            logger.info("📢 No subscribers to notify")
            return

        logger.info(
            f"📢 Sending notifications to {num_of_subscribers} subscribers for {len(new_concerts)} new concerts"
        )

        # Create notification message
        if len(new_concerts) == 1:
            header = "🆕 <b>הופעה חדשה בבארבי!</b>\n\n"
        else:
            header = f"🆕 <b>{len(new_concerts)} הופעות חדשות בבארבי!</b>\n\n"

        message = self._format_concerts_message(new_concerts, header)
        message += "\n🔔 אתה מקבל הודעה זו כי נרשמת להתראות הופעות בבארבי.\n"
        message += "השתמש ב-/unsubscribe כדי להפסיק התראות."

        # Send to all subscribers
        await self.notify_subscribers(message)

    async def notify_subscribers(self, message: str):
        """Send notification to all subscribers"""
        num_of_subscribers = cache.get_subscriber_count()
        if num_of_subscribers == 0:
            logger.info("📢 No subscribers to notify")
            return

        logger.info(f"📢 Sending notification to {num_of_subscribers} subscribers")

        subscribers = cache.get_all_subscribers()
        for (
            subscriber
        ) in subscribers.copy():  # Use copy to avoid modification during iteration
            user_id = subscriber["user_id"]
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
                logger.info(f"✅ Notification sent to {user_id}")
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"❌ Failed to send notification to {user_id}: {e}")
                # Remove invalid subscribers
                if (
                    "chat not found" in str(e).lower()
                    or "bot was blocked" in str(e).lower()
                ):
                    cache.remove_subscriber(user_id)
                    logger.info(f"🗑️ Removed invalid subscriber: {user_id}")

    def setup_handlers(self):
        """Setup all command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(
            CommandHandler("subscribe", self.subscribe_command)
        )
        self.application.add_handler(
            CommandHandler("unsubscribe", self.unsubscribe_command)
        )
        logger.info("✅ Bot handlers registered")

    def test_connection(self):
        """Test API connection"""
        try:
            logger.info("🔍 Testing Barby API connection...")
            concerts = self.scraper.get_concerts()
            logger.info(f"✅ API working - found {len(concerts)} concerts")
            return True
        except Exception as e:
            logger.error(f"❌ API test failed: {e}")
            return False

    async def run_async(self):
        """Run the bot asynchronously"""
        logger.info("🚀 Starting Barby Telegram Bot...")

        # Test API connection first
        if not self.test_connection():
            print("❌ Cannot connect to Barby API. Check your internet connection.")
            return

        try:
            # Create application
            self.application = Application.builder().token(self.bot_token).build()

            # Setup handlers
            self.setup_handlers()

            print("🎭 Barby Concert Telegram Bot")
            print("=" * 40)
            print("✅ Bot handlers registered")
            print("🚀 Bot is ready!")
            print("💬 Available commands:")
            print("   /start - Welcome message")
            print("   /subscribe - Get notifications")
            print("🛑 Press Ctrl+C to stop")
            print("=" * 40)

            # Start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
            )

            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received stop signal")

        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            raise
        finally:
            # Cleanup
            if self.application:
                await self.application.stop()
                await self.application.shutdown()

    def run(self):
        """Start the bot (sync wrapper)"""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"💥 Bot error: {e}")
            raise


def main():
    """Main function"""
    # Your bot token (replace with your actual token)
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    try:
        # Create and run bot
        bot = BarbyTelegramBot(BOT_TOKEN)
        bot.run()

    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user!")
    except Exception as e:
        print(f"💥 Error: {e}")
        print("\n💡 Make sure:")
        print("   1. Bot token is correct")
        print("   2. barby_api_scraper.py is in the same directory")
        print("   3. Internet connection is working")


if __name__ == "__main__":
    main()
