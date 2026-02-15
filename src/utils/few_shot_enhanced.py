"""
Enhanced Few-Shot Learning Module with Semantic Similarity

This module provides advanced few-shot learning capabilities using embeddings
and semantic similarity for better example selection.
"""

import os
import time
import gc
import warnings
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
from dotenv import load_dotenv

# Silence known LangChain warning on Python 3.14+ (runtime remains functional here).
warnings.filterwarnings(
    "ignore",
    message=r"Core Pydantic V1 functionality isn't compatible with Python 3\.14 or greater\.",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module=r"langchain_core\._api\.deprecation",
)

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_core.example_selectors.semantic_similarity import SemanticSimilarityExampleSelector

try:
    # Preferred import (langchain >= 0.2.9 deprecates community Chroma wrapper)
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover - compatibility fallback
    warnings.filterwarnings(
        "ignore",
        message=r"The class `Chroma` was deprecated in LangChain 0.2.9.*",
    )
    from langchain_community.vectorstores import Chroma

from langchain_core.example_selectors.base import BaseExampleSelector

from src.utils.db.few_shot import (
    get_few_shot_examples, save_few_shot_example, add_few_shot_feedback
)
from src.utils.few_shot_learning import determine_machine_type

# Singleton instance cache so we reuse embeddings/vector stores across requests
_MANAGER_INSTANCE: Optional["FewShotManager"] = None

load_dotenv()

EMBEDDING_MODEL_CANDIDATES = (
    "models/text-embedding-004",
    "models/embedding-001",
)


class FewShotManager:
    """Manages few-shot learning with semantic similarity"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the few-shot manager with embeddings.
        
        Args:
            api_key: Google API key for embeddings (uses env var if not provided)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.enabled = True
        self.disable_reason: Optional[str] = None
        self.embedding_model: Optional[str] = None
        self._disable_logged = False
        self._vectorstore_enabled = True
        self._vectorstore_disable_logged = False

        if not self.api_key:
            self._disable("GOOGLE_API_KEY not found in environment")
            # Cache for vector stores by field
            self._vectorstore_cache: Dict[str, Any] = {}
            self.persist_directory = os.path.join("src", "cache", "few_shot_embeddings")
            os.makedirs(self.persist_directory, exist_ok=True)
            self.embeddings = None
            return

        # Initialize embeddings with model fallback.
        self.embeddings = self._create_embeddings_with_fallback()
        if self.embeddings is None:
            self._disable(self.disable_reason or "No embedding model could be initialized")

        # Cache for vector stores by field
        self._vectorstore_cache: Dict[str, Any] = {}
        
        # Directory for persistent storage
        self.persist_directory = os.path.join("src", "cache", "few_shot_embeddings")
        os.makedirs(self.persist_directory, exist_ok=True)

    def _disable(self, reason: str) -> None:
        self.enabled = False
        self.disable_reason = reason
        if not self._disable_logged:
            print(f"[WARN] Semantic few-shot disabled: {reason}")
            self._disable_logged = True

    def _create_embeddings_with_fallback(self) -> Optional[GoogleGenerativeAIEmbeddings]:
        model_candidates: List[str] = []
        env_model = os.getenv("FEW_SHOT_EMBEDDING_MODEL")
        if env_model:
            model_candidates.append(env_model.strip())
        model_candidates.extend(self._discover_embedding_models())
        model_candidates.extend(EMBEDDING_MODEL_CANDIDATES)

        tried: set[str] = set()
        errors: list[str] = []
        for model_name in model_candidates:
            candidate = self._normalize_model_name(model_name.strip())
            if not candidate or candidate in tried:
                continue
            tried.add(candidate)
            try:
                embeddings = GoogleGenerativeAIEmbeddings(
                    model=candidate,
                    google_api_key=self.api_key,
                )
                # Force a lightweight probe so we fail fast on unsupported models.
                embeddings.embed_query("few-shot model probe")
                self.embedding_model = candidate
                return embeddings
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")

        if errors:
            self.disable_reason = (
                f"No supported embedding model found. Tried {len(tried)} model(s). "
                "Set FEW_SHOT_EMBEDDING_MODEL to a model returned by ListModels with embedContent support."
            )
            print(f"[WARN] Embedding initialization details: {'; '.join(errors[:2])}")
        else:
            self.disable_reason = "No candidate embedding models were provided"
        return None

    def _discover_embedding_models(self) -> List[str]:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            discovered: List[str] = []
            for model in genai.list_models():
                methods = getattr(model, "supported_generation_methods", None) or []
                if "embedContent" not in methods:
                    continue
                model_name = self._normalize_model_name(getattr(model, "name", ""))
                if model_name:
                    discovered.append(model_name)
            return discovered
        except Exception:
            return []

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        if not model_name:
            return ""
        if model_name.startswith("models/"):
            return model_name
        return f"models/{model_name}"
    
    def get_example_selector(
        self, 
        machine_type: str, 
        template_type: str, 
        field_name: str,
        k: int = 2
    ) -> Optional[SemanticSimilarityExampleSelector]:
        """
        Creates or retrieves a semantic similarity example selector for a specific field.
        
        Args:
            machine_type: Type of machine
            template_type: Template type
            field_name: Field name
            k: Number of examples to select
            
        Returns:
            SemanticSimilarityExampleSelector or None if no examples exist
        """
        if not self.enabled or self.embeddings is None:
            return None
        if not self._vectorstore_enabled:
            return None

        formatted_examples = self._get_formatted_examples(machine_type, template_type, field_name)
        if not formatted_examples:
            return None
        
        # Create unique key for this field
        cache_key = f"{machine_type}_{template_type}_{field_name}"
        persist_path = os.path.join(self.persist_directory, cache_key)
        
        try:
            # Try to load existing vectorstore
            if cache_key in self._vectorstore_cache:
                vectorstore = self._vectorstore_cache[cache_key]
            elif os.path.exists(persist_path):
                vectorstore = Chroma(
                    persist_directory=persist_path,
                    embedding_function=self.embeddings
                )
                self._vectorstore_cache[cache_key] = vectorstore
            else:
                # Create new vectorstore
                vectorstore = None
            
            # Create example selector
            if vectorstore is None:
                # First time creation
                example_selector = SemanticSimilarityExampleSelector.from_examples(
                    formatted_examples,
                    self.embeddings,
                    Chroma,
                    k=k,
                    input_keys=["input_context"],
                    persist_directory=persist_path
                )
            else:
                # Use existing vectorstore
                example_selector = SemanticSimilarityExampleSelector(
                    vectorstore=vectorstore,
                    k=k
                )
            
            self._vectorstore_cache[cache_key] = example_selector.vectorstore
            return example_selector
            
        except Exception as e:
            self._vectorstore_enabled = False
            if not self._vectorstore_disable_logged:
                print(f"[WARN] Vector store unavailable; using direct semantic fallback. {e}")
                self._vectorstore_disable_logged = True
            return None

    def _get_formatted_examples(
        self,
        machine_type: str,
        template_type: str,
        field_name: str,
    ) -> List[Dict[str, Any]]:
        examples = get_few_shot_examples(machine_type, template_type, field_name, limit=50)
        if not examples:
            return []

        formatted_examples: List[Dict[str, Any]] = []
        for ex in examples:
            raw_context = ex.get("input_context", "")
            raw_expected = ex.get("expected_output", "")

            input_context = "" if raw_context is None else str(raw_context)
            expected_output = "" if raw_expected is None else str(raw_expected)
            if not input_context.strip() and not expected_output.strip():
                continue

            formatted_examples.append(
                {
                    "input_context": input_context,
                    "expected_output": expected_output,
                    "confidence_score": float(ex.get("confidence_score", 1.0) or 1.0),
                    "example_id": ex.get("id"),
                }
            )
        return formatted_examples
    
    def get_few_shot_prompt_template(
        self,
        machine_type: str,
        template_type: str,
        field_name: str,
        k: int = 2,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None
    ) -> Optional[FewShotPromptTemplate]:
        """
        Creates a FewShotPromptTemplate with semantic example selection.
        
        Args:
            machine_type: Type of machine
            template_type: Template type
            field_name: Field name
            k: Number of examples to select
            prefix: Optional prefix for the prompt
            suffix: Optional suffix for the prompt
            
        Returns:
            FewShotPromptTemplate or None if no examples exist
        """
        example_selector = self.get_example_selector(
            machine_type, template_type, field_name, k
        )
        
        if example_selector is None:
            return None
        
        # Define the example template
        example_template = PromptTemplate(
            input_variables=["input_context", "expected_output"],
            template="Input: {input_context}\nExpected Output: {expected_output}"
        )
        
        # Set default prefix and suffix if not provided
        if prefix is None:
            prefix = f"Here are some examples of how to extract '{field_name}':"
        
        if suffix is None:
            suffix = "Now, based on the above examples, extract the value for the current input:\nInput: {input}\nOutput:"
        
        # Create the few-shot prompt template
        few_shot_prompt = FewShotPromptTemplate(
            example_selector=example_selector,
            example_prompt=example_template,
            prefix=prefix,
            suffix=suffix,
            input_variables=["input"]
        )
        
        return few_shot_prompt
    
    def select_best_examples(
        self,
        input_text: str,
        machine_type: str,
        template_type: str,
        field_name: str,
        k: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Selects the best examples for a given input using semantic similarity.
        
        Args:
            input_text: The input text to find similar examples for
            machine_type: Type of machine
            template_type: Template type
            field_name: Field name
            k: Number of examples to select
            
        Returns:
            List of selected examples
        """
        example_selector = self.get_example_selector(
            machine_type, template_type, field_name, k
        )
        
        if example_selector is None:
            return self._select_best_examples_direct(
                input_text=input_text,
                machine_type=machine_type,
                template_type=template_type,
                field_name=field_name,
                k=k,
            )
        
        try:
            return example_selector.select_examples({"input_context": input_text})
        except Exception as e:
            print(f"[WARN] Vector selector query failed for '{field_name}'; using direct semantic fallback. {e}")
            return self._select_best_examples_direct(
                input_text=input_text,
                machine_type=machine_type,
                template_type=template_type,
                field_name=field_name,
                k=k,
            )

    def _select_best_examples_direct(
        self,
        input_text: str,
        machine_type: str,
        template_type: str,
        field_name: str,
        k: int,
    ) -> List[Dict[str, Any]]:
        if not self.enabled or self.embeddings is None:
            return []

        formatted_examples = self._get_formatted_examples(machine_type, template_type, field_name)
        if not formatted_examples:
            return []

        try:
            input_embedding = np.array(self.embeddings.embed_query(input_text), dtype=float)
            example_texts = [example["input_context"] for example in formatted_examples]
            example_embeddings = np.array(self.embeddings.embed_documents(example_texts), dtype=float)

            input_norm = np.linalg.norm(input_embedding)
            if input_norm == 0:
                return formatted_examples[:k]

            example_norms = np.linalg.norm(example_embeddings, axis=1)
            safe_denominator = np.where(example_norms == 0, 1.0, example_norms * input_norm)
            scores = np.dot(example_embeddings, input_embedding) / safe_denominator
            ranked_indices = np.argsort(scores)[::-1][: max(k, 1)]
            return [formatted_examples[int(idx)] for idx in ranked_indices]
        except Exception as e:
            self._disable(f"Embedding similarity lookup failed: {e}")
            return []
    
    def add_example(
        self,
        machine_type: str,
        template_type: str,
        field_name: str,
        input_context: str,
        expected_output: str,
        confidence_score: float = 1.0,
        source_machine_id: Optional[int] = None
    ) -> bool:
        """
        Adds a new example to the database and vector store.
        
        Args:
            machine_type: Type of machine
            template_type: Template type
            field_name: Field name
            input_context: Input context for the example
            expected_output: Expected output value
            confidence_score: Quality score (0.0-1.0)
            source_machine_id: ID of the source machine
            
        Returns:
            True if successful
        """
        # Save to the primary SQL database
        success = save_few_shot_example(
            machine_type,
            template_type,
            field_name,
            input_context,
            expected_output,
            source_machine_id,
            confidence_score
        )
        
        if success:
            try:
                # Get the selector, which loads or creates the vectorstore
                example_selector = self.get_example_selector(
                    machine_type, template_type, field_name
                )
                
                # Add the new example directly to the active vectorstore
                if example_selector and hasattr(example_selector, 'add_example'):
                    new_example = {
                        "input_context": input_context,
                        "expected_output": expected_output,
                    }
                    example_selector.add_example(new_example)
                    print(f"Successfully added new example to live vectorstore for {field_name}.")
                else:
                    # If there's no selector or it can't add examples, invalidate the cache
                    # so it gets rebuilt on the next run. This is a safe fallback.
                    print(f"No active vectorstore for {field_name} or it cannot be updated. Invalidating cache.")
                    self.invalidate_cache(machine_type, template_type, field_name)
            
            except Exception as e:
                # If adding directly fails for any reason, fall back to the invalidation method
                print(f"Error adding example to vectorstore, using cache invalidation as fallback. Error: {e}")
                self.invalidate_cache(machine_type, template_type, field_name)

        return success
    
    def shutdown_vectorstore(self, cache_key: str):
        """
        Properly shuts down the Chroma vectorstore to release file locks.
        
        Args:
            cache_key: The key for the vectorstore to shut down.
        """
        if cache_key in self._vectorstore_cache:
            vectorstore = self._vectorstore_cache[cache_key]
            
            # Chroma's client needs to be stopped to release file locks
            if hasattr(vectorstore, "_client") and hasattr(vectorstore._client, "stop"):
                try:
                    vectorstore._client.stop()
                except Exception as e:
                    print(f"Error stopping Chroma client for {cache_key}: {e}")

            # Remove from cache and force garbage collection to release file handles
            del self._vectorstore_cache[cache_key]
            gc.collect()

    def invalidate_cache(self, machine_type: str, template_type: str, field_name: str):
        """
        Invalidates the cache for a specific field, forcing rebuild on next access.
        
        Args:
            machine_type: Type of machine
            template_type: Template type
            field_name: Field name
        """
        cache_key = f"{machine_type}_{template_type}_{field_name}"
        
        # Properly shut down the vectorstore before deleting files
        self.shutdown_vectorstore(cache_key)
        
        persist_path = os.path.join(self.persist_directory, cache_key)
        if os.path.exists(persist_path):
            import shutil
            try:
                shutil.rmtree(persist_path)
            except OSError as e:
                # If the error is a file lock error on Windows, handle it gracefully.
                if hasattr(e, 'winerror') and e.winerror == 32:
                    print(f"Cache for '{field_name}' is locked; will be rebuilt on next application start.")
                else:
                    # For other OS or different errors, re-raise the exception.
                    raise


def get_few_shot_manager(api_key: Optional[str] = None) -> "FewShotManager":
    """
    Provides a shared FewShotManager instance so embeddings/vectorstores
    can be reused across multiple prompt enhancements.
    """
    global _MANAGER_INSTANCE
    if _MANAGER_INSTANCE is None:
        _MANAGER_INSTANCE = FewShotManager(api_key=api_key)
    return _MANAGER_INSTANCE


def create_enhanced_few_shot_prompt(
    field_name: str,
    machine_type: str,
    template_type: str,
    input_context: str,
    max_examples: int = 2
) -> Tuple[str, List[Dict]]:
    """
    Creates an enhanced prompt with semantically selected few-shot examples.
    
    Args:
        field_name: Name of the field to extract
        machine_type: Type of machine
        template_type: Template type
        input_context: Input context for extraction
        max_examples: Maximum number of examples to include
        
    Returns:
        Tuple of (formatted prompt string, selected examples list)
    """
    try:
        manager = get_few_shot_manager()
        
        # Get semantically similar examples
        selected_examples = manager.select_best_examples(
            input_context,
            machine_type,
            template_type,
            field_name,
            k=max_examples
        )
        
        if not selected_examples:
            # No examples available, return basic prompt
            return f"Extract the value for '{field_name}' from the following context:\n{input_context}\n\nOutput:", []
        
        # Format examples for prompt
        examples_text = []
        for i, example in enumerate(selected_examples, 1):
            examples_text.append(f"Example {i}:")
            examples_text.append(f"Input: {example['input_context'][:500]}...")  # Truncate long contexts
            examples_text.append(f"Output: {example['expected_output']}\n")
        
        # Construct the full prompt
        prompt = f"""Extract the value for '{field_name}' based on these examples:

{chr(10).join(examples_text)}

Now extract from this input:
{input_context}

Output:"""
        
        return prompt, selected_examples
        
    except Exception as e:
        print(f"Error creating enhanced few-shot prompt: {e}")
        return f"Extract the value for '{field_name}' from the following context:\n{input_context}\n\nOutput:", []


def enhance_prompt_with_semantic_examples(
    prompt_parts: List[str],
    machine_data: Dict,
    template_placeholder_contexts: Dict[str, Any],
    common_items: List[Dict],
    full_pdf_text: str,
    max_examples_per_field: int = 2
) -> List[str]:
    """
    Enhances prompts with semantically selected few-shot examples.
    
    This is a drop-in replacement for the original enhance_prompt_with_few_shot_examples
    that uses semantic similarity instead of simple retrieval.
    
    Args:
        prompt_parts: Existing prompt parts
        machine_data: Machine data dictionary
        template_placeholder_contexts: Template field contexts
        common_items: List of common items
        full_pdf_text: Full PDF text
        max_examples_per_field: Maximum examples per field
        
    Returns:
        List of enhanced prompt parts
    """
    try:
        machine_name = machine_data.get("machine_name", "")
        machine_type = determine_machine_type(machine_name)
        template_type = "sortstar" if "sortstar" in machine_type else "default"
        
        manager = get_few_shot_manager()
        if not manager.enabled:
            return prompt_parts
        
        # Prepare input context for similarity matching
        context_parts = [f"Machine: {machine_name}"]
        if machine_data.get("main_item", {}).get("description"):
            context_parts.append(f"Main Item: {machine_data['main_item']['description'][:500]}")
        
        input_context = "\n".join(context_parts)
        
        # Get key fields (limit to avoid overwhelming the prompt)
        key_fields = list(template_placeholder_contexts.keys())[:10]
        
        few_shot_section = ["\nSEMANTICALLY SELECTED EXAMPLES (most relevant to current input):"]
        examples_added = 0
        
        for field_name in key_fields:
            # Get semantically similar examples
            selected_examples = manager.select_best_examples(
                input_context,
                machine_type,
                template_type,
                field_name,
                k=max_examples_per_field
            )
            
            if selected_examples:
                few_shot_section.append(f"\nExamples for '{field_name}':")
                for i, example in enumerate(selected_examples, 1):
                    # Truncate long contexts
                    context_preview = example['input_context'][:300]
                    if len(example['input_context']) > 300:
                        context_preview += "..."
                    
                    few_shot_section.append(f"  Example {i}:")
                    few_shot_section.append(f"    Input: {context_preview}")
                    few_shot_section.append(f"    Output: {example['expected_output']}")
                
                examples_added += 1
                
                # Limit total number of fields with examples to avoid prompt bloat
                if examples_added >= 5:
                    break
        
        if examples_added > 0:
            prompt_parts.extend(few_shot_section)
            prompt_parts.append("\nBased on the semantically similar examples above, extract field values for the current input.")
            print(f"Semantic few-shot examples injected for {examples_added} field(s).")
        else:
            print("Semantic few-shot enhancer found no matching examples; using base prompt.")
        
        return prompt_parts
        
    except Exception as e:
        # Surface the error so callers can gracefully fall back to the basic few-shot flow
        print(f"Error enhancing prompt with semantic examples: {e}")
        raise


# Convenience function for backward compatibility
def get_enhanced_few_shot_examples(
    machine_type: str,
    template_type: str,
    field_name: str,
    input_context: str,
    limit: int = 2
) -> List[Dict]:
    """
    Gets few-shot examples using semantic similarity.

    This is a drop-in replacement for the original get_few_shot_examples
    that uses semantic matching.

    Args:
        machine_type: Type of machine
        template_type: Template type
        field_name: Field name
        input_context: Input context for similarity matching
        limit: Maximum number of examples

    Returns:
        List of semantically similar examples
    """
    try:
        manager = get_few_shot_manager()
        if not manager.enabled:
            return []
        return manager.select_best_examples(
            input_context,
            machine_type,
            template_type,
            field_name,
            k=limit
        )
    except Exception as e:
        print(f"Error getting enhanced examples: {e}")
        # Fall back to basic retrieval
        return get_few_shot_examples(machine_type, template_type, field_name, limit)


def get_prioritized_few_shot_examples(
    machine_type: str,
    template_type: str,
    field_name: str,
    input_context: str,
    customer_name: Optional[str] = None,
    quote_ref: Optional[str] = None,
    limit: int = 3
) -> List[Dict]:
    """
    Gets few-shot examples with smart prioritization based on:
    1. Same customer (highest priority)
    2. Same machine type
    3. Recent high-confidence corrections (user-verified)
    4. Semantic similarity to current context

    Args:
        machine_type: Type of machine (sortstar, filling, labeling, etc.)
        template_type: Template type (default, sortstar)
        field_name: Name of the field to get examples for
        input_context: Current input context for similarity matching
        customer_name: Optional customer name for prioritization
        quote_ref: Optional quote reference for context
        limit: Maximum number of examples to return

    Returns:
        List of prioritized examples with priority metadata
    """
    try:
        manager = get_few_shot_manager()
        if not manager.enabled:
            return []

        # Get more examples than needed for prioritization
        fetch_limit = limit * 3  # Fetch 3x to allow for prioritization

        # Get semantically similar examples
        base_examples = manager.select_best_examples(
            input_context,
            machine_type,
            template_type,
            field_name,
            k=fetch_limit
        )

        if not base_examples:
            return []

        # Score and prioritize examples
        scored_examples = []

        for example in base_examples:
            score = 0.0

            # Base score from confidence
            confidence = float(example.get("confidence_score", 0.5))
            score += confidence * 0.3  # Weight: 30%

            # Boost for high confidence (user-verified examples)
            if confidence >= 0.95:
                score += 0.2  # User corrections get a boost

            # Boost for same machine type in context
            example_context = example.get("input_context", "").lower()
            if machine_type and machine_type.lower() in example_context:
                score += 0.15

            # Boost for customer match (if available in context)
            if customer_name:
                customer_lower = customer_name.lower()
                if customer_lower in example_context:
                    score += 0.25  # Highest boost for same customer

            # Boost for quote reference match
            if quote_ref:
                quote_lower = quote_ref.lower()
                if quote_lower in example_context:
                    score += 0.1

            scored_examples.append({
                **example,
                "priority_score": score
            })

        # Sort by priority score (descending)
        scored_examples.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

        # Return top examples
        return scored_examples[:limit]

    except Exception as e:
        print(f"Error getting prioritized examples for {field_name}: {e}")
        # Fall back to basic retrieval
        return get_few_shot_examples(machine_type, template_type, field_name, limit)


def enhance_prompt_with_prioritized_examples(
    prompt_parts: List[str],
    machine_data: Dict,
    template_placeholder_contexts: Dict[str, Any],
    common_items: List[Dict],
    full_pdf_text: str,
    customer_name: Optional[str] = None,
    quote_ref: Optional[str] = None,
    max_examples_per_field: int = 3
) -> List[str]:
    """
    Enhanced version of enhance_prompt_with_semantic_examples that uses
    smart prioritization based on customer and machine context.

    Args:
        prompt_parts: Existing prompt parts
        machine_data: Machine data dictionary
        template_placeholder_contexts: Template field contexts
        common_items: List of common items
        full_pdf_text: Full PDF text
        customer_name: Optional customer name for prioritization
        quote_ref: Optional quote reference
        max_examples_per_field: Maximum examples per field

    Returns:
        List of enhanced prompt parts
    """
    try:
        machine_name = machine_data.get("machine_name", "")
        machine_type = determine_machine_type(machine_name)
        template_type = "sortstar" if "sortstar" in machine_type else "default"

        # Prepare input context for similarity matching
        context_parts = [f"Machine: {machine_name}"]
        if machine_data.get("main_item", {}).get("description"):
            context_parts.append(f"Main Item: {machine_data['main_item']['description'][:500]}")

        input_context = "\n".join(context_parts)

        # Get key fields (limit to avoid overwhelming the prompt)
        key_fields = list(template_placeholder_contexts.keys())[:15]

        few_shot_section = ["\nPRIORITIZED FEW-SHOT EXAMPLES (customer and machine-specific):"]
        examples_added = 0

        for field_name in key_fields:
            # Get prioritized examples
            selected_examples = get_prioritized_few_shot_examples(
                machine_type=machine_type,
                template_type=template_type,
                field_name=field_name,
                input_context=input_context,
                customer_name=customer_name,
                quote_ref=quote_ref,
                limit=max_examples_per_field
            )

            if selected_examples:
                few_shot_section.append(f"\nExamples for '{field_name}':")
                for i, example in enumerate(selected_examples, 1):
                    # Truncate long contexts
                    context_preview = example.get('input_context', '')[:300]
                    if len(example.get('input_context', '')) > 300:
                        context_preview += "..."

                    priority = example.get('priority_score', 0)
                    confidence = example.get('confidence_score', 0.5)

                    few_shot_section.append(f"  Example {i} (priority: {priority:.2f}, confidence: {confidence:.2f}):")
                    few_shot_section.append(f"    Input: {context_preview}")
                    few_shot_section.append(f"    Output: {example.get('expected_output', '')}")

                examples_added += 1

                # Limit total number of fields with examples
                if examples_added >= 8:
                    break

        if examples_added > 0:
            prompt_parts.extend(few_shot_section)
            prompt_parts.append("\nBased on the prioritized examples above (matching your customer/machine context), extract field values.")
            print(f"Prioritized few-shot examples injected for {examples_added} field(s).")
        else:
            print("No prioritized examples found; using base prompt.")

        return prompt_parts

    except Exception as e:
        print(f"Error enhancing prompt with prioritized examples: {e}")
        # Fall back to semantic examples
        return enhance_prompt_with_semantic_examples(
            prompt_parts, machine_data, template_placeholder_contexts,
            common_items, full_pdf_text, max_examples_per_field
        )
