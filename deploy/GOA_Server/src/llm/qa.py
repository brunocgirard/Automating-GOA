"""
LLM Question Answering Module

This module handles question answering over PDF content using retrieval-augmented generation (RAG).
It provides functionality to answer user questions based on PDF quotes and technical documents by:
- Chunking long PDF text into manageable segments
- Scoring and selecting the most relevant chunks for the query
- Using the Gemini LLM to generate contextual answers

Key Functions:
- answer_pdf_question(): Main function that answers questions using PDF content and optional template contexts
- chunk_pdf_text(): Splits long text into overlapping chunks for better context preservation
- score_chunk_relevance(): Scores chunk relevance using keyword matching

This module uses retrieval-augmented prompting to handle long PDFs more effectively, avoiding
token limits and improving response quality by focusing on the most relevant content.
"""

from typing import List, Dict, Optional
import time
import traceback
from .client import get_generative_model


def answer_pdf_question(user_question: str,
                        selected_pdf_descriptions: List[str],
                        full_pdf_text: str,
                        template_placeholder_contexts: Optional[Dict[str, str]] = None) -> str:
    """
    Answers a user's question based on the provided PDF content (selected items and full text).
    Optionally uses template contexts if questions might refer to template field names.
    Uses retrieval-augmented prompting to handle long PDFs more effectively.

    Args:
        user_question: The question to answer
        selected_pdf_descriptions: List of selected item descriptions from the PDF
        full_pdf_text: Complete text content of the PDF
        template_placeholder_contexts: Optional dict mapping template field names to their descriptions

    Returns:
        String containing the answer to the question, or an error message if processing fails
    """
    model = get_generative_model()
    if model is None:
        return "Error: LLM client not configured. Please check API key."

    # Performance tracking
    start_time = time.time()

    # Implement retrieval-augmented prompting for long PDFs
    def chunk_pdf_text(text, chunk_size=800, overlap=150, max_chunks=50):
        """Split text into overlapping chunks for better context preservation."""
        chunks = []
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        start = 0
        while start < len(text) and len(chunks) < max_chunks:
            end = min(start + chunk_size, len(text))
            # Try to find a sensible break point (newline or period)
            if end < len(text):
                # Look for newline first
                newline_pos = text.rfind('\n', start, end)
                period_pos = text.rfind('. ', start, end)
                if newline_pos > start + chunk_size // 2:
                    end = newline_pos + 1  # Include the newline
                elif period_pos > start + chunk_size // 2:
                    end = period_pos + 2  # Include the period and space

            chunks.append(text[start:end])
            start = end - overlap  # Create overlap with previous chunk

        print(f"Created {len(chunks)} chunks from {len(text)} characters of text")
        return chunks

    def score_chunk_relevance(query, chunk):
        """
        Score chunk relevance to the query using simple keyword matching.
        A more sophisticated approach would use embeddings and semantic similarity.
        """
        query_terms = query.lower().split()
        # Remove common words
        stopwords = {'the', 'and', 'is', 'of', 'in', 'to', 'a', 'for', 'with', 'on', 'what', 'how', 'why', 'can', 'does', 'do'}
        query_terms = [term for term in query_terms if term not in stopwords and len(term) > 2]

        if not query_terms:
            return 0  # No meaningful terms to match

        score = 0
        chunk_lower = chunk.lower()

        # Score based on term frequency
        for term in query_terms:
            term_count = chunk_lower.count(term)
            score += term_count * 2  # Weight term matches

        # Score based on phrase matches (more weight)
        query_phrases = [' '.join(query_terms[i:i+2]) for i in range(len(query_terms)-1)]
        for phrase in query_phrases:
            if len(phrase.split()) > 1:  # Only count actual phrases
                phrase_count = chunk_lower.count(phrase)
                score += phrase_count * 5  # Higher weight for phrase matches

        # Normalize by chunk length to avoid bias toward longer chunks
        return score / (len(chunk) / 100) if chunk else 0

    # Process the PDF text
    if len(full_pdf_text) > 8000:
        print(f"PDF text is long ({len(full_pdf_text)} chars). Using retrieval-augmented prompting.")

        # Chunking phase
        chunk_time_start = time.time()
        chunks = chunk_pdf_text(full_pdf_text, max_chunks=40)  # Limit to 40 chunks maximum
        chunk_time = time.time() - chunk_time_start
        print(f"Chunking completed in {chunk_time:.2f} seconds")

        # Scoring phase
        scoring_time_start = time.time()
        scored_chunks = [(chunk, score_chunk_relevance(user_question, chunk)) for chunk in chunks]
        scoring_time = time.time() - scoring_time_start
        print(f"Scoring completed in {scoring_time:.2f} seconds")

        # Sort chunks by relevance score in descending order
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Select the top relevant chunks (up to a token limit)
        top_chunks = []
        total_chars = 0
        max_chars = 8000  # Reduced token limit for better performance
        max_top_chunks = 10  # Limit the number of top chunks

        for chunk, score in scored_chunks:
            if score > 0 and total_chars + len(chunk) <= max_chars and len(top_chunks) < max_top_chunks:
                top_chunks.append(chunk)
                total_chars += len(chunk)
                print(f"Added chunk with score {score:.2f}, length {len(chunk)}")

        # Always include the beginning of the document (first chunk) for context
        if chunks and chunks[0] not in top_chunks and total_chars + len(chunks[0]) <= max_chars:
            top_chunks.insert(0, chunks[0])
            print(f"Added first chunk for context, length {len(chunks[0])}")

        # Create a context summary with metadata
        relevant_text = "\n\n==== CHUNK BREAK ====\n\n".join(top_chunks)
        context_note = f"[PDF document chunked for retrieval. Showing {len(top_chunks)} most relevant chunks out of {len(chunks)} total.]"

        print(f"Final content for LLM: {len(relevant_text)} characters")
    else:
        relevant_text = full_pdf_text
        context_note = "[Full PDF text included - document is within token limits]"
        print(f"Using full PDF text: {len(relevant_text)} characters")

    prompt_parts = [
        "You are an AI assistant designed to answer questions about a technical equipment PDF quote.",
        "Base your answers SOLELY on the information provided below from the PDF.",
        "If the information to answer the question is not present in the provided text, clearly state that you cannot find the answer in the document.",
        "Be concise and direct.",

        "\nUSER'S QUESTION:",
        user_question,

        "\nRELEVANT INFORMATION FROM PDF:",
        "\n1. SELECTED PDF ITEMS (items confirmed as selected from the PDF quote):"
    ]
    if not selected_pdf_descriptions:
        prompt_parts.append("  (No specific items were identified as selected from tables.)")
    else:
        for i, desc in enumerate(selected_pdf_descriptions):
            prompt_parts.append(f"  - PDF Item {i+1}: {desc}")

    prompt_parts.append(f"\n2. PDF TEXT CONTEXT: {context_note}")
    prompt_parts.append(relevant_text)

    # Optionally add template contexts if questions might refer to template field names
    if template_placeholder_contexts:
        prompt_parts.append("\n3. TEMPLATE FIELDS (Context for potential questions referring to template field names - Placeholder Key: Description from template):")
        placeholder_list_for_prompt = []
        for key, context in template_placeholder_contexts.items():
            # Limit the number of template fields to include to avoid token limits
            if len(placeholder_list_for_prompt) < 50:  # Only include up to 50 fields
                placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
        if not placeholder_list_for_prompt:
            prompt_parts.append("  (No template fields context provided.)")
        else:
            prompt_parts.append(f"  (Showing {len(placeholder_list_for_prompt)} template fields)")
            for item_for_prompt in placeholder_list_for_prompt:
                prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR ANSWER TO THE USER'S QUESTION:")

    prompt = "\n".join(prompt_parts)

    # print("\n----- LLM Q&A PROMPT -----") # Uncomment for debugging
    # print(prompt)
    # print("------------------------")

    try:
        print(f"RAG processing completed in {time.time() - start_time:.2f} seconds")
        print("Sending Q&A prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        llm_start_time = time.time()
        response = model.generate_content(prompt, safety_settings=safety_settings)
        print(f"LLM response received in {time.time() - llm_start_time:.2f} seconds")

        # print("\n----- LLM Q&A RAW RESPONSE -----") # Uncomment for debugging
        # print(response.text)
        # print("----------------------------")

        total_time = time.time() - start_time
        print(f"Total answer_pdf_question processing time: {total_time:.2f} seconds")

        return response.text.strip()

    except Exception as e:
        print(f"Error in answer_pdf_question: {e}")
        traceback.print_exc()
        return "Sorry, I encountered an error trying to answer your question."
