"""
Enhanced Few-Shot Learning Module with Semantic Similarity

This module provides advanced few-shot learning capabilities using embeddings
and semantic similarity for better example selection.
"""

import os
import time
import gc
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_core.example_selectors.semantic_similarity import SemanticSimilarityExampleSelector

from langchain_community.vectorstores import Chroma

from langchain_core.example_selectors.base import BaseExampleSelector

from src.utils.crm_utils import (
    get_few_shot_examples, save_few_shot_example, add_few_shot_feedback
)
from src.utils.few_shot_learning import determine_machine_type

# Singleton instance cache so we reuse embeddings/vector stores across requests
_MANAGER_INSTANCE: Optional["FewShotManager"] = None


class FewShotManager:
    """Manages few-shot learning with semantic similarity"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the few-shot manager with embeddings.
        
        Args:
            api_key: Google API key for embeddings (uses env var if not provided)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        # Initialize embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=self.api_key
        )
        
        # Cache for vector stores by field
        self._vectorstore_cache: Dict[str, Chroma] = {}
        
        # Directory for persistent storage
        self.persist_directory = os.path.join("src", "cache", "few_shot_embeddings")
        os.makedirs(self.persist_directory, exist_ok=True)
    
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
        # Get examples from database
        examples = get_few_shot_examples(machine_type, template_type, field_name, limit=50)
        
        if not examples:
            return None
        
        # Format examples for LangChain
        formatted_examples = []
        for ex in examples:
            raw_context = ex.get("input_context", "")
            raw_expected = ex.get("expected_output", "")
            
            # Ensure both context and output are strings before handing to LangChain
            input_context = "" if raw_context is None else str(raw_context)
            expected_output = "" if raw_expected is None else str(raw_expected)
            
            if not input_context.strip() and not expected_output.strip():
                continue  # Skip empty examples that would add noise
            
            formatted_examples.append({
                "input_context": input_context,
                "expected_output": expected_output,
                "confidence_score": float(ex.get("confidence_score", 1.0) or 1.0),
                "example_id": ex.get("id")
            })
        
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
            print(f"Error creating example selector for {field_name}: {e}")
            return None
    
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
            return []
        
        # Select examples based on semantic similarity
        selected = example_selector.select_examples({"input_context": input_text})
        
        return selected
    
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
