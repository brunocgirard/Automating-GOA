"""
LLM Client Configuration Module

This module handles LLM client initialization and configuration for the QuoteFlow Document Assistant.
It provides functions to configure the Google Gemini client, check model usage, and access the
generative model instance.

Key Functions:
- configure_gemini_client(): Initializes the Gemini API client with API key from .env
- check_model_usage(): Sends a test request to verify which model is being used
- get_generative_model(): Returns the configured generative model instance

Global State:
- GENERATIVE_MODEL: Singleton instance of the configured Gemini model
"""

import os
import traceback
import google.generativeai as genai
from dotenv import load_dotenv


# Global variable for the model, initialized once
GENERATIVE_MODEL = None


def configure_gemini_client():
    """
    Loads the API key from .env and configures the Gemini client.
    Returns True if configuration is successful, False otherwise.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is not None:
        return True # Already configured

    try:
        load_dotenv() # Load environment variables from .env file
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not found in .env file or environment variables.")
            return False

        # Choose model
        model_name = 'gemini-2.5-flash-lite'
        print(f"Initializing Gemini with model: {model_name}")

        genai.configure(api_key=api_key)
        GENERATIVE_MODEL = genai.GenerativeModel(model_name)

        # Print model details to verify
        print(f"Gemini client configured successfully with model: {model_name}")

        return True
    except Exception as e:
        print(f"Error configuring Gemini client: {e}")
        GENERATIVE_MODEL = None
        return False


def check_model_usage():
    """
    Sends a minimal test request to check which model is actually being used.
    This can help verify if you're using the model you think you are.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("Error: Could not configure Gemini client to check model usage.")
            return

    try:
        # Send a minimal request to check model usage
        print("\n--- Checking Actual Model Usage ---")
        print("Sending test request to Gemini API...")

        # Get model info
        model_info = GENERATIVE_MODEL._model_name
        print(f"Model being used according to client: {model_info}")

        # Send a minimal request
        response = GENERATIVE_MODEL.generate_content("Say 'hello'")
        print(f"Response received successfully. Characters: {len(response.text)}")

        print("[OK] Verification complete. If you're still being charged for Gemini 2.5 Pro,")
        print("   check your Google Cloud Console to see all usage under your API key.")
        print("   You may need to create a new API key if you can't identify the source.")
    except Exception as e:
        print(f"Error checking model usage: {e}")
        traceback.print_exc()


def get_generative_model():
    """
    Returns the configured generative model instance.
    Initializes the client if not already configured.

    Returns:
        The configured GenerativeModel instance, or None if configuration fails.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            return None
    return GENERATIVE_MODEL
