"""
LLM Client Configuration Module

This module handles LLM client initialization and configuration for the QuoteFlow Document Assistant.
It provides functions to configure the Gemini client, check model usage, and access
the generative model instance.

Key Functions:
- configure_gemini_client(): Initializes the Gemini API client with API key from .env
- check_model_usage(): Sends a test request to verify which model is being used
- get_generative_model(): Returns the configured generative model instance

Global State:
- GENERATIVE_MODEL: Singleton instance of the configured Gemini model
"""

import os
import traceback
from typing import Any

from google import genai as _google_genai
from dotenv import load_dotenv


def _prepare_generation_config(
    generation_config: Any = None,
    safety_settings: Any = None,
) -> Any:
    """
    Convert legacy generation/safety arguments into google.genai config format.

    We keep this adapter so older call sites using `generation_config=` and
    `safety_settings=` continue to work without changing business logic.
    """
    if generation_config is None and safety_settings is None:
        return None

    if generation_config is None:
        return {"safety_settings": safety_settings}

    if safety_settings is None:
        return generation_config

    if isinstance(generation_config, dict):
        merged = dict(generation_config)
        merged.setdefault("safety_settings", safety_settings)
        return merged

    # Handle pydantic models from google.genai.types.
    if hasattr(generation_config, "model_dump"):
        try:
            merged = generation_config.model_dump(exclude_none=True)
            merged["safety_settings"] = safety_settings
            return merged
        except Exception:
            return generation_config

    return generation_config


class _CompatGenerativeModel:
    """Small adapter that mimics old `GenerativeModel` usage on top of `google.genai`."""

    def __init__(self, api_key: str, model_name: str):
        self._api_key = api_key
        self._model_name = model_name
        self._client = _google_genai.Client(api_key=api_key)

    def generate_content(
        self,
        contents: Any,
        generation_config: Any = None,
        safety_settings: Any = None,
        **kwargs: Any,
    ):
        # New SDK expects a single `config` payload.
        config = kwargs.get("config")
        if config is None:
            config = _prepare_generation_config(generation_config, safety_settings)

        try:
            return self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=config,
            )
        except Exception:
            # If safety settings shape is incompatible, retry without them.
            if safety_settings is not None:
                fallback_config = _prepare_generation_config(generation_config, None)
                return self._client.models.generate_content(
                    model=self._model_name,
                    contents=contents,
                    config=fallback_config,
                )
            raise


class _GenAICompatNamespace:
    """
    Compatibility namespace with legacy-style methods used by this codebase/tests.

    It exposes:
    - `configure(api_key=...)`
    - `GenerativeModel(model_name)`
    - `list_models()`
    - `types`
    """

    types = _google_genai.types

    def __init__(self) -> None:
        self._api_key: str | None = None

    def configure(self, *, api_key: str) -> None:
        self._api_key = api_key

    def _get_client(self) -> _google_genai.Client:
        if not self._api_key:
            raise RuntimeError("Gemini API key was not configured.")
        return _google_genai.Client(api_key=self._api_key)

    def GenerativeModel(self, model_name: str) -> _CompatGenerativeModel:
        if not self._api_key:
            raise RuntimeError("Gemini API key was not configured.")
        return _CompatGenerativeModel(self._api_key, model_name)

    def list_models(self):
        client = self._get_client()
        return client.models.list()


# Exposed for backward compatibility with existing imports and tests.
genai = _GenAICompatNamespace()


# Global variable for the model, initialized once
GENERATIVE_MODEL = None
MODEL_CACHE: dict[str, Any] = {}
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
MODEL_NAME_ENV_VAR = "GOA_LLM_MODEL"


def get_configured_model_name() -> str:
    """
    Returns the locked Gemini model name from configuration.

    The default stays pinned to a known model ID to avoid silent behavior drift.
    """
    configured_name = str(os.environ.get(MODEL_NAME_ENV_VAR, "")).strip()
    return configured_name or DEFAULT_GEMINI_MODEL


def _create_model(model_name: str) -> Any | None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env file or environment variables.")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


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
        model_name = get_configured_model_name()
        print(f"Initializing Gemini with model: {model_name}")
        model = _create_model(model_name)
        if model is None:
            return False
        GENERATIVE_MODEL = model
        MODEL_CACHE[model_name] = model
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


def get_generative_model(model_name_override: str | None = None):
    """
    Returns the configured generative model instance.
    Initializes the client if not already configured.

    Returns:
        The configured GenerativeModel instance, or None if configuration fails.
    """
    global GENERATIVE_MODEL
    requested_model_name = str(model_name_override or "").strip()
    if not requested_model_name:
        if GENERATIVE_MODEL is None:
            if not configure_gemini_client():
                return None
        return GENERATIVE_MODEL

    if requested_model_name in MODEL_CACHE:
        return MODEL_CACHE[requested_model_name]

    if GENERATIVE_MODEL is None and not configure_gemini_client():
        return None

    load_dotenv()
    try:
        model = _create_model(requested_model_name)
    except Exception as model_error:
        print(f"Error creating model '{requested_model_name}': {model_error}")
        return None
    if model is None:
        return None

    MODEL_CACHE[requested_model_name] = model
    return model
