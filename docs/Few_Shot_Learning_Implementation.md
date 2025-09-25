# Few-Shot Learning Implementation for GOA Document Generation

## Overview

This document describes the implementation of few-shot learning in the GOA (General Order Acknowledgement) document generation application. Few-shot learning improves the accuracy of field extraction by learning from high-quality examples of previous successful extractions.

## Architecture

### 1. Database Schema

The implementation adds two new database tables:

#### `few_shot_examples` Table
- **Purpose**: Stores high-quality examples for each field type
- **Key Fields**:
  - `machine_type`: Type of machine (filling, labeling, capping, sortstar, general)
  - `template_type`: Template type (default, sortstar)
  - `field_name`: Specific field this example is for
  - `input_context`: PDF text/context used as input
  - `expected_output`: Correct field value that should be extracted
  - `confidence_score`: Quality score (0.0-1.0)
  - `usage_count`: How many times this example has been used
  - `success_count`: How many times it led to correct results

#### `few_shot_feedback` Table
- **Purpose**: Tracks user corrections and feedback to improve example quality
- **Key Fields**:
  - `feedback_type`: Type of feedback (correction, confirmation, rejection)
  - `original_prediction`: What the LLM originally predicted
  - `corrected_value`: What the user corrected it to
  - `user_context`: Additional context from user

### 2. Core Modules

#### `src/utils/few_shot_learning.py`
Main module containing:
- **Example Management**: Save, retrieve, and curate examples
- **Similarity Matching**: Find similar examples using text similarity
- **Prompt Enhancement**: Add few-shot examples to LLM prompts
- **Feedback Recording**: Track user corrections for continuous improvement

#### Enhanced `src/utils/llm_handler.py`
- **Prompt Enhancement**: Automatically includes relevant few-shot examples
- **Example Saving**: Saves successful extractions as new examples
- **Feedback Integration**: Records user corrections during chat interactions

## How It Works

### 1. Example Creation
When the LLM successfully extracts field values:
1. The system identifies meaningful field values (non-empty, non-"NO" for checkboxes)
2. Extracts relevant context from the machine data and PDF
3. Saves the example with a confidence score
4. Associates it with the machine type and template type

### 2. Prompt Enhancement
Before sending prompts to the LLM:
1. Determines the machine type from the machine name
2. Retrieves the best examples for each field (sorted by confidence and success rate)
3. Adds these examples to the prompt in a structured format
4. Limits examples per field to avoid overwhelming the prompt

### 3. Feedback Loop
When users make corrections via chat:
1. System records the original prediction and corrected value
2. Associates feedback with the relevant examples
3. Updates success counts for examples that led to correct results
4. Improves future example selection based on feedback

### 4. Example Curation
The system automatically:
- Tracks usage and success rates
- Prioritizes examples with higher success rates
- Removes or deprioritizes low-quality examples
- Updates confidence scores based on feedback

## Usage Examples

### Machine Type Detection
```python
machine_type = determine_machine_type("SortStar Bottle Unscrambler Model XL")
# Returns: "sortstar"
```

### Retrieving Examples
```python
examples = get_few_shot_examples("filling", "default", "production_speed", limit=3)
# Returns top 3 examples for production_speed field in filling machines
```

### Saving Successful Extraction
```python
save_successful_extraction_as_example(
    field_name="production_speed",
    field_value="60 units per minute",
    machine_data=machine_data,
    common_items=common_items,
    full_pdf_text=pdf_text,
    machine_type="filling",
    template_type="default"
)
```

## Benefits

### 1. Improved Accuracy
- **Context-Aware Learning**: Examples are specific to machine types and field contexts
- **Quality-Based Selection**: Only high-confidence, successful examples are used
- **Continuous Improvement**: System learns from user feedback over time

### 2. Reduced Manual Corrections
- **Better Initial Predictions**: Few-shot examples guide the LLM to make better initial guesses
- **Domain-Specific Learning**: Examples are tailored to packaging machinery terminology
- **Pattern Recognition**: System learns common patterns in machine specifications

### 3. Scalable Learning
- **Automatic Example Creation**: No manual curation required
- **Feedback Integration**: User corrections automatically improve the system
- **Quality Metrics**: Built-in tracking of example effectiveness

## Configuration

### Example Limits
- **Max Examples Per Field**: 2-3 examples to avoid prompt bloat
- **Similarity Threshold**: 0.1 minimum similarity for example matching
- **Confidence Thresholds**: 0.8+ for text fields, 0.9+ for checkbox fields

### Machine Type Categories
- **sortstar**: SortStar, Unscrambler, Bottle Unscrambler
- **labeling**: Label, Labeling, LabelStar
- **filling**: Fill, Filler, Filling
- **capping**: Cap, Capper, Capping
- **general**: Default for unknown machine types

## UI Integration

### Few-Shot Learning Management Page
Added to the main navigation, provides:
- **Example Statistics**: View usage and success rates
- **Example Search**: Find examples by field or context
- **Quality Management**: Remove low-quality examples
- **Export/Import**: Backup and restore examples

### Automatic Integration
- **Transparent Operation**: Works automatically without user intervention
- **Feedback Recording**: Captures corrections during normal usage
- **Performance Tracking**: Monitors improvement over time

## Future Enhancements

### 1. Advanced Similarity Matching
- **Semantic Embeddings**: Use sentence transformers for better similarity
- **Contextual Similarity**: Consider field context in similarity calculations
- **Machine Learning Models**: Train custom similarity models

### 2. Dynamic Example Selection
- **Adaptive Limits**: Adjust number of examples based on field complexity
- **Context-Aware Selection**: Choose examples based on current input context
- **Performance-Based Selection**: Prioritize examples that improve accuracy

### 3. Multi-Modal Learning
- **Image Examples**: Include visual examples for complex specifications
- **Structured Data**: Learn from tabular data patterns
- **Cross-Field Learning**: Learn relationships between different fields

## Monitoring and Maintenance

### Key Metrics
- **Example Quality**: Track confidence scores and success rates
- **Usage Patterns**: Monitor which examples are most helpful
- **Accuracy Improvement**: Measure reduction in manual corrections
- **System Performance**: Track prompt length and processing time

### Maintenance Tasks
- **Regular Cleanup**: Remove outdated or low-quality examples
- **Quality Review**: Periodically review example quality
- **Performance Optimization**: Optimize similarity calculations
- **Database Maintenance**: Archive old examples and feedback

## Conclusion

The few-shot learning implementation provides a robust foundation for continuous improvement in field extraction accuracy. By learning from successful examples and user feedback, the system becomes more accurate and requires less manual intervention over time.

The modular design allows for easy extension and enhancement, while the automatic operation ensures minimal impact on user workflow. The built-in quality metrics and feedback mechanisms ensure the system maintains high standards while continuously improving.
