# QuoteFlow Document Assistant - Testing Guide

This guide provides comprehensive information about the testing infrastructure for the QuoteFlow Document Assistant project.

## Overview

The testing infrastructure consists of:

1. **pytest** - Test framework
2. **pytest-cov** - Code coverage reporting
3. **pytest-mock** - Advanced mocking utilities
4. **freezegun** - Time mocking for deterministic tests
5. **faker** - Realistic test data generation
6. **conftest.py** - Shared fixtures and configuration
7. **.coveragerc** - Coverage configuration
8. **pytest.ini** - Pytest configuration

## Quick Start

### Running All Tests

```bash
# Run all tests with coverage
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_mymodule.py

# Run specific test function
pytest tests/test_mymodule.py::test_my_function

# Run tests matching a pattern
pytest -k "database" -v
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Generate terminal coverage report
pytest --cov=src --cov-report=term-missing

# Generate XML coverage report
pytest --cov=src --cov-report=xml

# View HTML report
# Open htmlcov/index.html in a browser
```

### Running Tests by Category

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only database tests
pytest -m database

# Run only PDF tests
pytest -m pdf

# Skip slow tests
pytest -m "not slow"

# Run specific marker
pytest -m "database and not slow"
```

## Test Structure

### Directory Organization

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── test_helpers.py             # Helper classes and utilities
├── test_template_utils.py      # Template utilities tests
├── pytest.log                  # Test execution log
└── htmlcov/                    # HTML coverage report (generated)
```

### Test File Naming

- Test files: `test_*.py` or `*_test.py`
- Test classes: `Test*`
- Test functions: `test_*`

## Available Fixtures

### Path Fixtures

```python
def test_with_project_root(project_root):
    """Access the project root directory."""
    assert project_root.exists()

def test_with_templates_dir(templates_dir):
    """Access the templates directory."""
    goa_template = templates_dir / "GOA_template.xlsx"
```

### Sample Data Fixtures

```python
def test_with_client_data(sample_client_data):
    """Create test client data."""
    client = sample_client_data(
        quote_ref="TEST-001",
        customer_name="My Company"
    )
    assert client["quote_ref"] == "TEST-001"

def test_with_machine_data(sample_machine_data):
    """Create test machine data."""
    machine = sample_machine_data(
        machine_name="TestMaster 3000",
        machine_type="Standard"
    )
    assert machine["machine_name"] == "TestMaster 3000"

def test_with_priced_items(sample_priced_items_data):
    """Create test priced items."""
    items = sample_priced_items_data(
        quote_ref="TEST-001",
        item_count=5
    )
    assert len(items) == 5
```

### Database Fixtures

```python
def test_with_temp_database(temp_db_path):
    """Use an isolated test database."""
    assert temp_db_path.exists()
    assert temp_db_path.suffix == ".db"

def test_with_db_connection(test_db_connection):
    """Use a database connection."""
    cursor = test_db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

def test_with_populated_db(populated_test_db):
    """Use a pre-populated test database."""
    # Database has sample client, items, and machines
    assert populated_test_db.exists()

def test_with_isolated_db(isolated_db, monkeypatch):
    """Use isolated database with DB_PATH monkeypatching."""
    # All database operations use the test database
    pass
```

### Mocking Fixtures

```python
def test_with_mock_gemini(mock_gemini_client):
    """Use mocked Gemini client."""
    response = mock_gemini_client.generate_content("test prompt")
    assert response.text is not None

def test_with_patched_gemini(patch_gemini_client):
    """Use patched Gemini client in code."""
    # All code using ChatGoogleGenerativeAI uses the mock
    pass

def test_with_mock_pdf_utils(mock_pdf_utils):
    """Use mocked PDF utilities."""
    items = mock_pdf_utils["extract_line_item_details"]()
    assert len(items) == 2

def test_with_mock_streamlit(mock_streamlit):
    """Use mocked Streamlit components."""
    mock_streamlit.success("Test message")
    mock_streamlit.success.assert_called_once()
```

### File Cleanup

```python
def test_with_cleanup(cleanup_test_files):
    """Cleanup test files automatically."""
    # Create temporary files during test
    test_file = cleanup_test_files.track(Path("temp.txt"))
    test_file.write_text("test")

    # File is automatically cleaned up after test
    assert test_file.exists()
    # After test completes, cleanup_test_files() is called
```

## Testing Patterns

### Unit Test Example

```python
import pytest
from src.utils.pdf_utils import extract_line_item_details

@pytest.mark.unit
def test_extract_line_items_returns_list():
    """Test that extraction returns a list."""
    # Arrange
    pdf_path = "tests/sample.pdf"

    # Act
    result = extract_line_item_details(pdf_path)

    # Assert
    assert isinstance(result, list)
    assert len(result) > 0
```

### Database Test Example

```python
import pytest
from src.utils.db import save_client_info, load_all_clients

@pytest.mark.database
def test_save_and_load_client(populated_test_db, sample_client_data):
    """Test saving and loading client data."""
    # Arrange
    client_data = sample_client_data(quote_ref="DB-TEST-001")

    # Act
    save_client_info(client_data, str(populated_test_db))
    loaded = load_all_clients(str(populated_test_db))

    # Assert
    assert len(loaded) > 0
    assert loaded[0]["quote_ref"] == "DB-TEST-001"
```

### Integration Test Example

```python
import pytest
from src.utils.pdf_utils import extract_line_item_details
from src.utils.db import save_priced_items

@pytest.mark.integration
def test_pdf_to_database_pipeline(sample_pdf_path, populated_test_db):
    """Test complete PDF processing pipeline."""
    # Arrange

    # Act
    items = extract_line_item_details(str(sample_pdf_path))
    save_priced_items("TEST-001", items, str(populated_test_db))

    # Assert
    # Verify items were saved to database
    pass
```

### Mock Example

```python
import pytest
from unittest.mock import patch, Mock

@pytest.mark.llm
def test_gemini_extraction_with_mock(mock_gemini_client):
    """Test LLM extraction with mocked Gemini."""
    # Arrange
    mock_response = Mock()
    mock_response.text = '{"field": "value"}'
    mock_gemini_client.generate_content.return_value = mock_response

    # Act
    response = mock_gemini_client.generate_content("test")

    # Assert
    assert response.text == '{"field": "value"}'
```

## Test Helpers

The `tests/test_helpers.py` module provides utility classes:

### DatabaseTestHelper

```python
from tests.test_helpers import DatabaseTestHelper

def test_with_database_helper(temp_db_path):
    helper = DatabaseTestHelper(temp_db_path)
    helper.connect()

    # Check if table exists
    assert helper.table_exists("clients")

    # Get row count
    count = helper.get_table_row_count("clients")

    # Fetch records
    records = helper.fetch_all("SELECT * FROM clients")

    helper.close()
```

### MockDataGenerator

```python
from tests.test_helpers import MockDataGenerator

def test_with_mock_data_generator():
    # Generate quote reference
    quote_ref = MockDataGenerator.generate_quote_ref("CUSTOM")

    # Generate complete client data
    client = MockDataGenerator.generate_client_dict(quote_ref=quote_ref)

    # Generate item data
    item = MockDataGenerator.generate_item_dict(quote_ref=quote_ref, item_num=1)

    # Generate machine data
    machine = MockDataGenerator.generate_machine_dict(machine_name="TestMaster")
```

### LLMResponseMocker

```python
from tests.test_helpers import LLMResponseMocker

def test_with_llm_response_mocker():
    # Create extraction response
    response = LLMResponseMocker.create_extraction_response(
        fields={"field1": "value1"},
        confidence=0.99
    )

    # Create text response
    text = LLMResponseMocker.create_text_response("Test response")

    # Create mock function
    mock_func = LLMResponseMocker.mock_gemini_generate_content(response)
```

### FileTestHelper

```python
from tests.test_helpers import FileTestHelper

def test_with_file_helper():
    # Create temporary file
    temp_file = FileTestHelper.create_temp_file(
        content="test content",
        suffix=".txt"
    )

    # Create temporary directory
    temp_dir = FileTestHelper.create_temp_dir()

    # Cleanup
    FileTestHelper.cleanup_path(temp_file)
```

### AssertionHelpers

```python
from tests.test_helpers import AssertionHelpers

def test_with_assertion_helpers():
    # Validate quote reference
    AssertionHelpers.assert_valid_quote_ref("TEST-001")

    # Validate client data
    client = {"quote_ref": "TEST-001", "customer_name": "Test"}
    AssertionHelpers.assert_valid_client_data(client)
```

## Context Managers

### TempDatabaseContext

```python
from tests.test_helpers import TempDatabaseContext
from src.utils.db import init_db

def test_with_temp_database_context():
    with TempDatabaseContext(init_func=init_db) as db_helper:
        # Use the database
        assert db_helper.table_exists("clients")
        # Cleanup happens automatically
```

### MockGeminiContext

```python
from tests.test_helpers import MockGeminiContext

def test_with_mock_gemini_context():
    response_json = '{"field": "value"}'
    with MockGeminiContext(response_text=response_json) as mock:
        # All code using Gemini will use the mock
        pass
```

## Configuration Files

### pytest.ini

Configures pytest behavior:
- Test discovery patterns
- Output options
- Code coverage settings
- Test markers
- Logging

To modify test configuration, edit `pytest.ini`.

### .coveragerc

Configures code coverage:
- Source directories
- Omit patterns
- Report exclusions
- Minimum coverage threshold (70%)

To adjust coverage requirements, edit `.coveragerc`.

### pyproject.toml

Modern Python project configuration:
- Package metadata
- Dependencies
- Tool configurations (pytest, black, mypy, etc.)

## Coverage Requirements

- **Minimum coverage**: 70%
- **Target coverage**: 85%+
- **Critical paths**: 100% (PDF processing, database operations, LLM integration)

### Viewing Coverage

```bash
# Terminal report showing missing lines
pytest --cov=src --cov-report=term-missing

# HTML report with interactive navigation
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

## Windows-Specific Notes

The testing infrastructure follows Windows compatibility guidelines:

1. **Path handling**: Uses `pathlib.Path` for cross-platform compatibility
2. **Unicode output**: ASCII-only output for console (no emoji or special characters)
3. **File permissions**: Proper handling of Windows file permissions
4. **Temporary files**: Uses `tempfile` module for proper cleanup

## CI/CD Integration

### Running Tests in CI

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests with coverage
pytest --cov=src --cov-report=xml

# Optional: Run specific test categories
pytest -m "not slow" --cov=src
```

### Skip Tests in CI

Use the `@pytest.mark.skip_ci` marker:

```python
@pytest.mark.skip_ci
def test_slow_external_service():
    # This test is skipped in CI environments
    pass
```

## Best Practices

### Writing Tests

1. **Use descriptive names**: `test_extract_line_items_returns_list()` instead of `test_extract()`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Test one thing**: Each test should verify a single behavior
4. **Use fixtures**: Leverage pytest fixtures for setup/teardown
5. **Mark tests appropriately**: Use `@pytest.mark.unit`, `@pytest.mark.database`, etc.

### Database Testing

1. **Use isolated databases**: Each test gets its own temporary database
2. **Use factories**: Use `sample_client_data()` and similar fixtures
3. **Verify state changes**: Assert database state before and after operations
4. **Clean up**: Let fixtures handle automatic cleanup

### Mocking

1. **Mock external APIs**: Mock Gemini API calls
2. **Use context managers**: Use mocking context managers for clean setup/teardown
3. **Verify interactions**: Check that mocks were called correctly
4. **Patch at use site**: Patch where the object is used, not where it's defined

### Performance

1. **Use marks**: Mark slow tests with `@pytest.mark.slow`
2. **Parallelize**: Run tests in parallel with `pytest-xdist` (optional)
3. **Cache test data**: Reuse test databases and data where safe

## Troubleshooting

### Tests Fail on Windows Path Issues

**Problem**: Tests fail due to path separators

**Solution**: Always use `pathlib.Path` instead of string paths:
```python
# Bad
path = "tests\data\file.txt"

# Good
path = Path("tests") / "data" / "file.txt"
```

### Database Locked Error

**Problem**: `sqlite3.OperationalError: database is locked`

**Solution**: Ensure proper connection cleanup:
```python
def test_something(test_db_connection):
    # Don't reuse closed connections
    # Don't open multiple connections to same file
    pass
```

### Mock Not Being Used

**Problem**: Code still calls real API instead of using mock

**Solution**: Patch at the use site:
```python
# Wrong
@patch("google.generativeai.ChatGoogleGenerativeAI")
def test_something(mock_client):
    pass

# Right - patch where it's used
@patch("src.llm.client.ChatGoogleGenerativeAI")
def test_something(mock_client):
    pass
```

### Coverage Not Showing Certain Files

**Problem**: Some modules not showing in coverage report

**Solution**: Check `.coveragerc` omit patterns and ensure modules are imported in tests

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)

## Getting Help

For testing-related questions:

1. Check this guide
2. Review examples in existing tests
3. Check pytest documentation
4. Review conftest.py for available fixtures
5. Check test_helpers.py for utility classes
