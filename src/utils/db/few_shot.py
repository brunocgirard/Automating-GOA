import re
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import DB_PATH, connection_context, row_to_dict, rows_to_dicts, to_text


_PLACEHOLDER_OUTPUTS = {
    "n/a",
    "na",
    "not applicable",
    "not specified",
    "not selected",
    "none selected",
    "none",
    "null",
    "nil",
    "unknown",
    "not provided",
    "not available",
    "pending",
    "tbd",
    "see quote",
    "not found",
    "not mentioned",
    "not listed",
    "not included",
    "not stated",
    "not given",
    "not defined",
    "not indicated",
    "not determined",
    "no data",
    "no information",
    "to be determined",
    "to be confirmed",
    "refer to quote",
    "see pdf",
    "see document",
    "placeholder",
    "default",
    "empty",
    "blank",
    "-",
    "--",
    "---",
    "...",
    "???",
}

_PLACEHOLDER_CONTEXTS = {
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "tbd",
}
def _is_checkbox_field(field_name: str) -> bool:
    return to_text(field_name).lower().endswith("_check")


def _normalize_checkbox_output(value: str) -> str:
    normalized = to_text(value).upper()
    if normalized in {"YES", "TRUE", "1"}:
        return "YES"
    if normalized in {"NO", "FALSE", "0"}:
        return "NO"
    return normalized


def _clamp_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, parsed))


def _is_valid_example_payload(
    machine_type: str,
    template_type: str,
    field_name: str,
    input_context: str,
    expected_output: str,
) -> bool:
    machine_type = to_text(machine_type)
    template_type = to_text(template_type)
    field_name = to_text(field_name)
    input_context = to_text(input_context)
    expected_output = to_text(expected_output)

    if not machine_type or not template_type or not field_name:
        return False
    if len(input_context) < 5 or len(expected_output) < 1:
        return False
    if input_context.lower() in _PLACEHOLDER_CONTEXTS:
        return False

    if _is_checkbox_field(field_name):
        return _normalize_checkbox_output(expected_output) in {"YES", "NO"}

    normalized_output = expected_output.lower()
    if normalized_output in _PLACEHOLDER_OUTPUTS:
        return False

    # Reject outputs that look like LLM refusal/uncertainty phrases
    _LLM_REFUSAL_PATTERNS = (
        "i cannot", "i could not", "i couldn't", "unable to",
        "not enough information", "cannot determine", "could not find",
        "no relevant", "not extractable", "insufficient",
    )
    for pattern in _LLM_REFUSAL_PATTERNS:
        if pattern in normalized_output:
            return False

    # Reject outputs that are just whitespace or punctuation
    if re.fullmatch(r'[\s\W]+', expected_output):
        return False

    return True


def _row_is_valid_example(row: sqlite3.Row | Dict[str, Any]) -> bool:
    row_dict = row_to_dict(row) or {}
    return _is_valid_example_payload(
        machine_type=str(row_dict.get("machine_type", "unknown")),
        template_type=str(row_dict.get("template_type", "unknown")),
        field_name=str(row_dict.get("field_name", "")),
        input_context=str(row_dict.get("input_context", "")),
        expected_output=str(row_dict.get("expected_output", "")),
    )


def save_few_shot_example(machine_type: str, template_type: str, field_name: str,
                          input_context: str, expected_output: str,
                          source_machine_id: Optional[int] = None,
                          confidence_score: float = 1.0, db_path: str = DB_PATH) -> bool:
    """
    Saves a high-quality example for few-shot learning.

    Args:
        machine_type: Type of machine (e.g., "filling", "labeling", "sortstar")
        template_type: Template type (e.g., "GOA", "default", "sortstar")
        field_name: The specific field this example is for
        input_context: The PDF text/context used as input
        expected_output: The correct field value
        source_machine_id: Reference to the machine that generated this example
        confidence_score: Quality score (0.0-1.0)

    Returns:
        bool: True if saved successfully
    """
    try:
        with connection_context(db_path) as conn:
            cursor = conn.cursor()

            machine_type_clean = to_text(machine_type)
            template_type_clean = to_text(template_type)
            field_name_clean = to_text(field_name)
            input_context_clean = to_text(input_context)
            expected_output_clean = to_text(expected_output)
            if _is_checkbox_field(field_name_clean):
                expected_output_clean = _normalize_checkbox_output(expected_output_clean)

            if not _is_valid_example_payload(
                machine_type=machine_type_clean,
                template_type=template_type_clean,
                field_name=field_name_clean,
                input_context=input_context_clean,
                expected_output=expected_output_clean,
            ):
                print(f"Skipping low-quality few-shot example for field '{field_name_clean}'.")
                return False

            confidence_score_clean = _clamp_confidence(confidence_score)
            created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
            INSERT INTO few_shot_examples
            (machine_type, template_type, field_name, input_context, expected_output,
             confidence_score, source_machine_id, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                machine_type_clean,
                template_type_clean,
                field_name_clean,
                input_context_clean,
                expected_output_clean,
                confidence_score_clean,
                source_machine_id,
                created_date,
            ))

            conn.commit()
        return True

    except sqlite3.Error as e:
        print(f"Error saving few-shot example: {e}")
        return False
def get_few_shot_examples(machine_type: str, template_type: str, field_name: str,
                         limit: int = 3, db_path: str = DB_PATH) -> List[Dict]:
    """
    Retrieves the best few-shot examples for a specific machine type and field.

    Args:
        machine_type: Type of machine
        template_type: Template type
        field_name: Specific field name
        limit: Maximum number of examples to return

    Returns:
        List of example dictionaries sorted by quality and success rate
    """
    try:
        if limit <= 0:
            return []

        with connection_context(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query for examples matching the criteria, ordered by quality metrics
            cursor.execute("""
            SELECT machine_type, template_type, field_name,
                   input_context, expected_output, confidence_score,
                   usage_count, success_count, id
            FROM few_shot_examples
            WHERE machine_type = ? AND template_type = ? AND field_name = ?
            ORDER BY
                confidence_score DESC,
                CASE WHEN usage_count > 0 THEN success_count * 1.0 / usage_count ELSE 0 END DESC,
                usage_count DESC
            LIMIT ?
            """, (machine_type, template_type, field_name, max(limit * 20, 100)))

            rows = [row for row in cursor.fetchall() if _row_is_valid_example(row)]
            if len(rows) > limit:
                rows = rows[:limit]

            # Update usage count for retrieved examples
            if rows:
                example_ids = [row['id'] for row in rows]
                placeholders = ','.join(['?' for _ in example_ids])
                cursor.execute(f"""
                UPDATE few_shot_examples
                SET usage_count = usage_count + 1, last_used_date = ?
                WHERE id IN ({placeholders})
                """, [datetime.now().strftime("%Y-%m-%d %H:%M:%S")] + example_ids)
                conn.commit()

            return rows_to_dicts(rows)

    except sqlite3.Error as e:
        print(f"Error retrieving few-shot examples: {e}")
        return []
def add_few_shot_feedback(example_id: int, feedback_type: str,
                         original_prediction: str = None, corrected_value: str = None,
                         user_context: str = None, db_path: str = DB_PATH) -> bool:
    """
    Records feedback on a few-shot example to improve future performance.

    Args:
        example_id: ID of the example being feedback on
        feedback_type: Type of feedback ("correction", "confirmation", "rejection")
        original_prediction: What the LLM originally predicted
        corrected_value: What the user corrected it to
        user_context: Additional context from user

    Returns:
        bool: True if feedback recorded successfully
    """
    try:
        with connection_context(db_path) as conn:
            cursor = conn.cursor()

            feedback_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
            INSERT INTO few_shot_feedback
            (example_id, feedback_type, original_prediction, corrected_value,
             feedback_date, user_context)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (example_id, feedback_type, original_prediction, corrected_value,
                  feedback_date, user_context))

            # Update success count if this was a confirmation
            if feedback_type == "confirmation":
                cursor.execute("""
                UPDATE few_shot_examples
                SET success_count = success_count + 1
                WHERE id = ?
                """, (example_id,))

            conn.commit()
        return True

    except sqlite3.Error as e:
        print(f"Error recording few-shot feedback: {e}")
        return False
def get_few_shot_statistics(db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Gets comprehensive statistics about few-shot examples for monitoring performance.

    Returns:
        Dictionary containing various statistics about the few-shot learning system
    """
    try:
        with connection_context(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            stats = {}

            # Total examples count
            cursor.execute("SELECT COUNT(*) as total FROM few_shot_examples")
            stats['total_examples'] = cursor.fetchone()['total']

            # Examples by machine type
            cursor.execute("""
            SELECT machine_type, COUNT(*) as count
            FROM few_shot_examples
            GROUP BY machine_type
            ORDER BY count DESC
            """)
            stats['by_machine_type'] = rows_to_dicts(cursor.fetchall())

            # Examples by template type
            cursor.execute("""
            SELECT template_type, COUNT(*) as count
            FROM few_shot_examples
            GROUP BY template_type
            ORDER BY count DESC
            """)
            stats['by_template_type'] = rows_to_dicts(cursor.fetchall())

            # Top fields by example count
            cursor.execute("""
            SELECT field_name, COUNT(*) as count,
                   AVG(confidence_score) as avg_confidence,
                   AVG(CASE WHEN usage_count > 0 THEN success_count * 1.0 / usage_count ELSE 0 END) as avg_success_rate
            FROM few_shot_examples
            GROUP BY field_name
            ORDER BY count DESC
            LIMIT 10
            """)
            stats['top_fields'] = rows_to_dicts(cursor.fetchall())

            # Overall success rate
            cursor.execute("""
            SELECT
                AVG(confidence_score) as avg_confidence,
                SUM(usage_count) as total_usage,
                SUM(success_count) as total_success,
                CASE WHEN SUM(usage_count) > 0 THEN SUM(success_count) * 1.0 / SUM(usage_count) ELSE 0 END as overall_success_rate
            FROM few_shot_examples
            """)
            overall_stats = row_to_dict(cursor.fetchone()) or {}
            stats['overall'] = overall_stats

            # Recent examples (last 10)
            cursor.execute("""
            SELECT field_name, expected_output, confidence_score, usage_count, success_count, created_date
            FROM few_shot_examples
            ORDER BY created_date DESC
            LIMIT 10
            """)
            stats['recent_examples'] = rows_to_dicts(cursor.fetchall())

            # Quality distribution
            cursor.execute("""
            SELECT
                CASE
                    WHEN confidence_score >= 0.9 THEN 'High (0.9+)'
                    WHEN confidence_score >= 0.7 THEN 'Medium (0.7-0.9)'
                    ELSE 'Low (<0.7)'
                END as quality_tier,
                COUNT(*) as count
            FROM few_shot_examples
            GROUP BY quality_tier
            ORDER BY confidence_score DESC
            """)
            stats['quality_distribution'] = rows_to_dicts(cursor.fetchall())

            return stats

    except sqlite3.Error as e:
        print(f"Error getting few-shot statistics: {e}")
        return {}
def get_field_examples(machine_type: str = None, template_type: str = None,
                      field_name: str = None, limit: int = 10, db_path: str = DB_PATH) -> List[Dict]:
    """
    Gets examples with optional filtering by machine type, template type, or field name.

    Args:
        machine_type: Filter by machine type
        template_type: Filter by template type
        field_name: Filter by field name
        limit: Maximum number of examples to return

    Returns:
        List of example dictionaries
    """
    try:
        with connection_context(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query with optional filters
            where_conditions = []
            params = []

            if machine_type and machine_type != "all":
                where_conditions.append("machine_type = ?")
                params.append(machine_type)

            if template_type and template_type != "all":
                where_conditions.append("template_type = ?")
                params.append(template_type)

            if field_name and field_name != "all":
                where_conditions.append("field_name = ?")
                params.append(field_name)

            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)

            query = f"""
            SELECT id, machine_type, template_type, field_name, input_context,
                   expected_output, confidence_score, usage_count, success_count,
                   created_date, last_used_date
            FROM few_shot_examples
            {where_clause}
            ORDER BY confidence_score DESC, usage_count DESC
            LIMIT ?
            """

            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            filtered_rows = [row for row in rows if _row_is_valid_example(row)]
            return rows_to_dicts(filtered_rows)

    except sqlite3.Error as e:
        print(f"Error getting field examples: {e}")
        return []
def get_all_field_names(db_path: str = DB_PATH) -> List[str]:
    """
    Gets all unique field names from the few_shot_examples table.

    Returns:
        List of unique field names
    """
    try:
        with connection_context(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT field_name FROM few_shot_examples ORDER BY field_name")
            return [row[0] for row in cursor.fetchall()]

    except sqlite3.Error as e:
        print(f"Error getting field names: {e}")
        return []
def create_sample_few_shot_data(db_path: str = DB_PATH) -> bool:
    """
    Creates sample few-shot learning data for testing and demonstration purposes.

    Returns:
        bool: True if sample data was created successfully
    """
    try:
        with connection_context(db_path) as conn:
            cursor = conn.cursor()

            # Check if sample data already exists
            cursor.execute("SELECT COUNT(*) FROM few_shot_examples")
            existing_count = cursor.fetchone()[0]

            if existing_count > 0:
                print(f"Sample data already exists ({existing_count} examples). Skipping creation.")
                return True

            # Create sample examples
            sample_examples = [
            {
                'machine_type': 'sortstar',
                'template_type': 'sortstar',
                'field_name': 'bs_984_check',
                'input_context': 'SortStar 18ft3 220VAC 3 Phases LEFT TO RIGHT configuration with bottle unscrambling capabilities',
                'expected_output': 'YES',
                'confidence_score': 0.95,
                'usage_count': 12,
                'success_count': 11,
                'created_date': '2024-01-15 10:30:00',
                'last_used_date': '2024-01-20 14:22:00'
            },
            {
                'machine_type': 'filling',
                'template_type': 'default',
                'field_name': 'production_speed',
                'input_context': 'Volumetric filling system with 60 bottles per minute production rate for pharmaceutical applications',
                'expected_output': '60 units per minute',
                'confidence_score': 0.92,
                'usage_count': 8,
                'success_count': 8,
                'created_date': '2024-01-16 09:15:00',
                'last_used_date': '2024-01-19 16:45:00'
            },
            {
                'machine_type': 'labeling',
                'template_type': 'default',
                'field_name': 'machine_model',
                'input_context': 'LabelStar Model System 1 with high-speed labeling capabilities for round containers',
                'expected_output': 'LabelStar Model System 1',
                'confidence_score': 0.88,
                'usage_count': 15,
                'success_count': 13,
                'created_date': '2024-01-14 11:20:00',
                'last_used_date': '2024-01-21 09:30:00'
            },
            {
                'machine_type': 'capping',
                'template_type': 'default',
                'field_name': 'voltage',
                'input_context': 'Capping machine specifications: 220-240V, 50Hz, 3-phase electrical supply',
                'expected_output': '220-240V',
                'confidence_score': 0.90,
                'usage_count': 6,
                'success_count': 5,
                'created_date': '2024-01-17 13:45:00',
                'last_used_date': '2024-01-20 11:15:00'
            },
            {
                'machine_type': 'filling',
                'template_type': 'default',
                'field_name': 'barcode_scanner_check',
                'input_context': 'Including barcode scanner for product verification and traceability in filling line',
                'expected_output': 'YES',
                'confidence_score': 0.85,
                'usage_count': 10,
                'success_count': 9,
                'created_date': '2024-01-18 08:30:00',
                'last_used_date': '2024-01-21 15:20:00'
            }
            ]

            # Insert sample examples
            for example in sample_examples:
                cursor.execute("""
                INSERT INTO few_shot_examples
                (machine_type, template_type, field_name, input_context, expected_output,
                 confidence_score, usage_count, success_count, created_date, last_used_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    example['machine_type'],
                    example['template_type'],
                    example['field_name'],
                    example['input_context'],
                    example['expected_output'],
                    example['confidence_score'],
                    example['usage_count'],
                    example['success_count'],
                    example['created_date'],
                    example['last_used_date']
                ))

            # Create sample feedback
            sample_feedback = [
            {
                'example_id': 1,
                'feedback_type': 'confirmation',
                'original_prediction': 'YES',
                'corrected_value': 'YES',
                'feedback_date': '2024-01-20 14:22:00',
                'user_context': 'User confirmed the prediction was correct'
            },
            {
                'example_id': 2,
                'feedback_type': 'correction',
                'original_prediction': '50 units per minute',
                'corrected_value': '60 units per minute',
                'feedback_date': '2024-01-19 16:45:00',
                'user_context': 'User corrected the production speed'
            }
            ]

            # Insert sample feedback
            for feedback in sample_feedback:
                cursor.execute("""
                INSERT INTO few_shot_feedback
                (example_id, feedback_type, original_prediction, corrected_value,
                 feedback_date, user_context)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    feedback['example_id'],
                    feedback['feedback_type'],
                    feedback['original_prediction'],
                    feedback['corrected_value'],
                    feedback['feedback_date'],
                    feedback['user_context']
                ))

            conn.commit()
        print(f"Created {len(sample_examples)} sample examples and {len(sample_feedback)} sample feedback records")
        return True

    except sqlite3.Error as e:
        print(f"Error creating sample few-shot data: {e}")
        return False
def get_similar_examples(input_text: str, machine_type: str, template_type: str,
                        limit: int = 5, db_path: str = DB_PATH) -> List[Dict]:
    """
    Finds examples similar to the input text using simple text similarity.
    This could be enhanced with more sophisticated similarity matching.

    Args:
        input_text: Text to find similar examples for
        machine_type: Type of machine
        template_type: Template type
        limit: Maximum number of examples to return

    Returns:
        List of similar example dictionaries
    """
    try:
        with connection_context(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Simple similarity based on common words
            # This could be enhanced with embeddings or more sophisticated matching
            input_words = set(input_text.lower().split())

            cursor.execute("""
            SELECT id, input_context, expected_output, field_name, confidence_score,
                   usage_count, success_count
            FROM few_shot_examples
            WHERE machine_type = ? AND template_type = ?
            """, (machine_type, template_type))

            rows = cursor.fetchall()
            examples = []

            for row in rows:
                if not _row_is_valid_example(row):
                    continue
                context_words = set(row['input_context'].lower().split())
                # Calculate simple Jaccard similarity
                intersection = len(input_words.intersection(context_words))
                union = len(input_words.union(context_words))
                similarity = intersection / union if union > 0 else 0

                if similarity > 0.1:  # Threshold for similarity
                    example_dict = row_to_dict(row) or {}
                    example_dict['similarity'] = similarity
                    examples.append(example_dict)

            # Sort by similarity and quality metrics
            examples.sort(key=lambda x: (x['similarity'], x['confidence_score'],
                                       x.get('success_count', 0)), reverse=True)

            return examples[:limit]

    except sqlite3.Error as e:
        print(f"Error finding similar examples: {e}")
        return []
