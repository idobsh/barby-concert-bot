import os

# Set environment for local testing
os.environ["TELEGRAM_BOT_TOKEN"] = "dummy_token_for_testing"  # Won't use it
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"

from aws_lambda.lambda_function import lambda_handler


# Mock context
class MockContext:
    def get_remaining_time_in_millis(self):
        return 30000


# Test
if __name__ == "__main__":
    print("🧪 Testing core logic...")

    event = {"source": "local-test"}
    context = MockContext()

    try:
        result = lambda_handler(event, context)
        print("✅ Success:", result)
    except Exception as e:
        print("❌ Error:", e)
        import traceback

        traceback.print_exc()
