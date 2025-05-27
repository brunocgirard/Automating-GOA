"""
This script checks which Gemini model is actually being used in your application.
Run this script directly to perform a check without running the full application.
"""

from src.utils.llm_handler import check_model_usage

if __name__ == "__main__":
    print("Running Gemini model verification...")
    check_model_usage()
    print("\nVerification complete. Check the console output above to confirm which model is being used.")
    print("If you're still being charged for Gemini 2.5 Pro, examine your Google Cloud Console")
    print("to see which applications or services are using your API key.")
    print("\nRecommendations if you see unexpected charges:")
    print("1. Create a new API key in Google Cloud Console")
    print("2. Update your .env file with the new API key")
    print("3. Disable the old API key to prevent further charges") 