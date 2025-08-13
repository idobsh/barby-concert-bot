# Barby Concert Telegram Bot

Automated notifications for new concerts at Barby Tel Aviv.

## Architecture
- **Telegram Bot** (EC2) - Handles user commands
- **Lambda Function** - Checks for new concerts every 2 hours  
- **Redis** - Manages subscribers and state
- **EventBridge** - Triggers Lambda schedule

## Structure
```
barby-concert-bot/
├── src/                    # Core scraper logic
├── telegram_logic/         # Telegram bot handlers
├── redis_logic/           # Redis cache management
├── aws_lambda/            # Lambda function
└── tests/                 # Test files
```

## Setup
1. Copy `.env.example` to `.env`
2. Add your bot token and Redis endpoint
3. Install: `pip install -r requirements.txt`
4. Run bot: `python telegram_logic/telegram_bot.py`
5. Deploy Lambda: `cd aws_lambda && aws lambda create-function...`
