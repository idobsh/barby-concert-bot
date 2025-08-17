import logging
import redis
import json
from datetime import datetime
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
load_dotenv()
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("barby_redis_scheduler.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class RedisConcertCache:
    """Redis-based cache for concert state"""

    def __init__(self, host=None, port=6379, db=0, password=None):
        try:
            self.redis_client = redis.Redis(
                host=host or os.getenv('REDIS_HOST', 'localhost'),
                port=port,
                db=db,
                password=password,
                decode_responses=True,  # Automatically decode bytes to strings
                socket_timeout=5,
                socket_connect_timeout=5,
            )

            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Connected to Redis at {host}:{port}")

        except redis.exceptions.ConnectionError as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Redis error: {e}")
            raise

    def get_concert_key(self, concert_id: str) -> str:
        """Generate Redis key for a concert"""
        return f"barby:concert:{concert_id}"

    def get_metadata_key(self) -> str:
        """Redis key for metadata"""
        return "barby:metadata"

    def load_last_state(self) -> Tuple[Dict, Optional[str]]:
        """Load the last seen concerts from Redis"""
        try:
            # Get all concert keys
            concert_keys = self.redis_client.keys("barby:concert:*")
            concerts = {}

            if concert_keys:
                # Get all concerts in batch
                for key in concert_keys:
                    concert_data = self.redis_client.get(key)
                    if concert_data:
                        concert = json.loads(concert_data)
                        concert_id = key.split(":")[-1]  # Extract ID from key
                        concerts[concert_id] = concert

            # Get metadata (last check time)
            metadata = self.redis_client.get(self.get_metadata_key())
            last_check = None
            if metadata:
                meta_data = json.loads(metadata)
                last_check = meta_data.get("last_check")

            logger.info(f"📁 Loaded {len(concerts)} concerts from Redis cache")
            if last_check:
                logger.info(f"📅 Last check was: {last_check}")

            return concerts, last_check

        except Exception as e:
            logger.error(f"❌ Error loading from Redis: {e}")
            return {}, None

    def save_state(self, concerts: Dict):
        """Save current state to Redis"""
        try:
            timestamp = datetime.now().isoformat()
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Clear old concert data
            old_keys = self.redis_client.keys("barby:concert:*")
            if old_keys:
                pipe.delete(*old_keys)

            # Save each concert
            for concert_id, concert in concerts.items():
                # Prepare concert data for serialization
                concert_copy = concert.copy()

                # Convert datetime to string if present
                if "event_date" in concert_copy and concert_copy["event_date"]:
                    concert_copy["event_date"] = concert_copy["event_date"].isoformat()

                # Remove raw_data to save space
                concert_copy.pop("raw_data", None)

                # Save to Redis with expiration (7 days)
                key = self.get_concert_key(concert_id)
                pipe.setex(key, 604800, json.dumps(concert_copy, ensure_ascii=False))

            # Save metadata
            metadata = {
                "last_check": timestamp,
                "total_concerts": len(concerts),
                "updated_at": datetime.now().isoformat(),
            }
            pipe.setex(self.get_metadata_key(), 604800, json.dumps(metadata))

            # Execute all operations
            pipe.execute()

            logger.info(f"💾 Saved {len(concerts)} concerts to Redis cache")

        except Exception as e:
            logger.error(f"❌ Error saving to Redis: {e}")

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            # Count concert keys
            concert_keys = self.redis_client.keys("barby:concert:*")

            # Get metadata
            metadata = self.redis_client.get(self.get_metadata_key())
            meta_info = {}
            if metadata:
                meta_info = json.loads(metadata)

            # Redis info
            redis_info = self.redis_client.info("memory")

            return {
                "concerts_cached": len(concert_keys),
                "last_check": meta_info.get("last_check", "Never"),
                "cache_updated": meta_info.get("updated_at", "Never"),
                "redis_memory_used": redis_info.get("used_memory_human", "Unknown"),
                "redis_connected_clients": self.redis_client.client_list(),
            }

        except Exception as e:
            logger.error(f"❌ Error getting Redis stats: {e}")
            return {}

    def clear_cache(self):
        """Clear all cache data"""
        try:
            # Delete all barby-related keys
            keys = self.redis_client.keys("barby:*")
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"🗑️  Cleared {len(keys)} keys from Redis cache")
            else:
                logger.info("🗑️  Cache was already empty")

        except Exception as e:
            logger.error(f"❌ Error clearing Redis cache: {e}")

    def health_check(self) -> bool:
        """Check if Redis is healthy"""
        try:
            self.redis_client.ping()
            return True
        except:
            return False

    def get_subscribers_key(self) -> str:
        """Redis key for subscribers"""
        return "barby:subscribers"

    def add_subscriber(self, user_id: int, username: str = "", first_name: str = ""):
        """Add a Telegram user to subscribers"""
        try:
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "subscribed_at": datetime.now().isoformat(),
            }

            self.redis_client.hset(
                self.get_subscribers_key(), str(user_id), json.dumps(user_data)
            )
            logger.info(f"👤 Added subscriber: {first_name} (@{username})")

        except Exception as e:
            logger.error(f"❌ Error adding subscriber: {e}")

    def remove_subscriber(self, user_id: int):
        """Remove a subscriber"""
        try:
            result = self.redis_client.hdel(self.get_subscribers_key(), str(user_id))
            if result:
                logger.info(f"👤 Removed subscriber: {user_id}")
            else:
                logger.warning(f"⚠️  Subscriber {user_id} not found")
        except Exception as e:
            logger.error(f"❌ Error removing subscriber: {e}")

    def get_all_subscribers(self) -> list:
        """Get all subscribers"""
        try:
            subscribers_data = self.redis_client.hgetall(self.get_subscribers_key())
            subscribers = []

            for user_id, data in subscribers_data.items():
                subscriber = json.loads(data)
                subscribers.append(subscriber)

            return subscribers

        except Exception as e:
            logger.error(f"❌ Error getting subscribers: {e}")
            return []

    def subscriber_exists(self, user_id: int) -> bool:
        """Check if user is already subscribed"""
        return self.redis_client.hexists("barby:subscribers", str(user_id))

    def get_subscriber_count(self) -> int:
        """Get number of subscribers"""
        try:
            return self.redis_client.hlen(self.get_subscribers_key())
        except Exception as e:
            logger.error(f"❌ Error getting subscriber count: {e}")
            return 0
