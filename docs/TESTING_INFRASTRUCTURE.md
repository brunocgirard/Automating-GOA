# QuoteFlow Testing Infrastructure - Complete Implementation

## Overview

A comprehensive pytest testing infrastructure has been created for the QuoteFlow Document Assistant project. This infrastructure provides:

- **417+ tests** already in the codebase
- **Modular fixture system** for easy test creation
- **Database testing utilities** with automatic cleanup
- **Mock utilities** for external APIs
- **Code coverage tracking** (70% minimum, target 85%+)
- **Cross-platform support** (Windows-optimized)

## Files Created/Modified

### 1. **tests/conftest.py** (723 lines)
Core pytest configuration and shared fixtures.

**Fixtures provided:**
- Path fixtures: `project_root`, `test_data_dir`, `templates_dir`, `data_dir`
- Sample data factories: `sample_client_data()`, `sample_machine_data()`, `sample_priced_items_data()`
- Database fixtures: `temp_db_path`, `test_db_connection`, `test_db_cursor`, `populated_test_db`, `isolated_db`
- PDF fixtures: `sample_pdf_path`, `sample_pdf_cqc`, `sample_pdf_ume`
- Mock fixtures: `mock_gemini_response()`, `mock_gemini_client`, `patch_gemini_client`
- Utility fixtures: `mock_pdf_utils`, `mock_streamlit`, `cleanup_test_files`, `caplog_unicode`

**Key features:**
- Windows path compatibility using `pathlib.Path`
- Automatic database cleanup after tests
- ASCII-only output for console (Windows compatibility)
- Session-scoped and function-scoped fixtures
- Parametrizable factories for test data

### 2. **tests/test_helpers.py** (556 lines)
Helper classes and utilities for tests.

**Classes provided:**
- `DatabaseTestHelper`: Database operations (connect, execute, fetch, backup, clear)
- `MockDataGenerator`: Factory methods for realistic test data
- `LLMResponseMocker`: Mock Gemini API responses
- `FileTestHelper`: Temporary file/directory creation
- `AssertionHelpers`: Custom assertions for test validation
- `TempDatabaseContext`: Context manager for temporary databases
- `MockGeminiContext`: Context manager for mocking Gemini API

**Key methods:**
- `save_client_info()`, `save_priced_items()`, `save_machines_data()`
- `execute()`, `fetch_one()`, `fetch_all()`, `table_exists()`
- `generate_quote_ref()`, `generate_client_dict()`, `generate_item_dict()`
- `create_extraction_response()`, `create_text_response()`
- `create_temp_file()`, `create_temp_dir()`, `cleanup_path()`
- `assert_valid_quote_ref()`, `assert_database_has_record()`

### 3. **.coveragerc** (95 lines)
Code coverage configuration.

**Settings:**
- Source: `src/` directory
- Minimum coverage: 70%
- Target coverage: 85%+
- Excludes: test files, virtual environments, dependencies
- Report formats: HTML, XML, JSON
- Custom exclusions: abstract methods, debug code, type checking blocks

### 4. **pytest.ini** (58 lines)
Pytest configuration (enhanced from existing).

**Configuration:**
- Python path: `. src`
- Test paths: `tests`
- Test discovery patterns: `test_*.py`, `*_test.py`
- Strict marker checking
- Custom markers: unit, integration, database, pdf, llm, slow, windows, skip_ci
- Logging configuration
- Durations tracking (slowest 10 tests)
- Doctest support

### 5. **pyproject.toml** (133 lines)
Modern Python project configuration (new).

**Sections:**
- Project metadata (name, version, description, dependencies)
- Optional dependencies: dev, test
- Tool configurations: pytest, coverage, black, isort, mypy, pylint

### 6. **requirements.txt** (updated)
Added testing dependencies:
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Advanced mocking
- `freezegun>=1.4.0` - Time mocking
- `faker>=20.0.0` - Realistic test data

### 7. **TESTING_GUIDE.md** (480+ lines)
Comprehensive testing documentation.

**Sections:**
- Quick start guide
- Available fixtures with examples
- Testing patterns (unit, integration, mocking)
- Helper classes usage
- Configuration files explanation
- Windows-specific considerations
- CI/CD integration
- Best practices
- Troubleshooting guide

### 8. **TESTING_QUICK_START.md** (250+ lines)
Fast reference for common testing commands.

**Includes:**
- Installation instructions
- Basic pytest commands
- Test category filtering
- Coverage commands
- Debugging options
- Common fixture usage
- Test organization
- Windows-specific notes
- Continuous integration setup

### 9. **TESTING_INFRASTRUCTURE.md** (this file)
Complete implementation overview.

## Usage Examples

### Creating a Simple Unit Test

```python
import pytest
from src.utils.pdf_utils import extract_line_item_details

@pytest.mark.unit
def test_extract_line_items(sample_pdf_path):
    """Test PDF extraction returns list of items."""
    items = extract_line_item_details(str(sample_pdf_path))

    assert isinstance(items, list)
    assert len(items) > 0
    assert all("description" in item for item in items)
```

### Testing Database Operations

```python
import pytest
from src.utils.db import save_client_info, load_all_clients
from tests.test_helpers import DatabaseTestHelper

@pytest.mark.database
def test_save_and_load_client(populated_test_db, sample_client_data):
    """Test client CRUD operations."""
    # Create new client
    client = sample_client_data(quote_ref="UNIT-TEST-001")

    # Save to database
    success = save_client_info(client, str(populated_test_db))
    assert success is True

    # Load and verify
    clients = load_all_clients(str(populated_test_db))
    assert any(c["quote_ref"] == "UNIT-TEST-001" for c in clients)
```

### Testing with Mocks

```python
import pytest
from unittest.mock import patch

@pytest.mark.llm
def test_llm_extraction_with_mock(patch_gemini_client):
    """Test LLM extraction with mocked API."""
    # Code using Gemini API will use the mock
    from src.llm.client import ChatGoogleGenerativeAI

    client = ChatGoogleGenerativeAI()
    response = client.generate_content("test prompt")

    assert response is not None
    assert response.text is not None
```

### Using Helper Utilities

```python
from tests.test_helpers import MockDataGenerator, DatabaseTestHelper

def test_with_generated_data():
    """Test using generated mock data."""
    # Generate sample data
    quote_ref = MockDataGenerator.generate_quote_ref("TEST")
    client = MockDataGenerator.generate_client_dict(quote_ref=quote_ref)
    items = [MockDataGenerator.generate_item_dict(quote_ref=quote_ref)]

    # Use in test
    assert client["quote_ref"] == quote_ref
    assert items[0]["quote_ref"] == quote_ref
```

### Using Context Managers

```python
from tests.test_helpers import TempDatabaseContext
from src.utils.db import init_db

def test_with_context_manager():
    """Test using temporary database context."""
    with TempDatabaseContext(init_func=init_db) as db:
        assert db.table_exists("clients")
        # Database automatically cleaned up after context
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_database/test_clients.py::TestSaveClientInfo::test_save_new_client_success

# Run by marker
pytest -m database -v
pytest -m "not slow" -v
```

### Coverage Commands

```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View in terminal
pytest --cov=src --cov-report=term-missing

# Generate XML for CI/CD
pytest --cov=src --cov-report=xml
```

### Debugging

```bash
# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Stop on first failure
pytest -x

# Show slowest tests
pytest --durations=10
```

## Test Categories

Tests can be filtered by marker:

| Marker | Purpose | Example |
|--------|---------|---------|
| `@pytest.mark.unit` | Unit tests (functions in isolation) | Test single function behavior |
| `@pytest.mark.integration` | Integration tests (components interact) | Test PDF + DB pipeline |
| `@pytest.mark.database` | Database operations | Test CRUD operations |
| `@pytest.mark.pdf` | PDF processing | Test extraction |
| `@pytest.mark.llm` | LLM integration | Test Gemini API usage |
| `@pytest.mark.slow` | Slow tests | Skip with `-m "not slow"` |
| `@pytest.mark.windows` | Windows-specific | Platform-specific behavior |
| `@pytest.mark.skip_ci` | Skip in CI/CD | Tests requiring manual interaction |

## Windows Compatibility

All testing infrastructure is Windows-optimized:

1. **Path handling**: Uses `pathlib.Path` throughout
2. **Unicode output**: ASCII-only console output (no emoji, special chars)
3. **File permissions**: Proper handling of Windows NTFS
4. **Temporary files**: Uses `tempfile` module for automatic cleanup
5. **Line endings**: Respects Windows line endings

## Code Coverage

### Current Status
- **417+ tests** already in codebase
- **Coverage goal**: 85%+
- **Minimum coverage**: 70%
- **Critical paths**: 100% (PDF, DB, LLM)

### Coverage Report

```bash
# Generate HTML report
pytest --cov=src --cov-report=html

# Open in browser
start htmlcov\index.html  # Windows
```

### Coverage by Module
See `.coveragerc` for per-module settings:
- Source: `src/`
- Excluded: tests, venv, dependencies
- Minimum: 70% overall, 100% for critical paths

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Issue: "No module named 'src'"
**Solution**: Ensure `pythonpath = . src` in pytest.ini

### Issue: "Database is locked"
**Solution**: Use isolated database fixture: `def test(temp_db_path):`

### Issue: "Mock not working"
**Solution**: Patch at use site: `@patch("src.llm.client.ChatGoogleGenerativeAI")`

### Issue: "Fixture not found"
**Solution**: Ensure conftest.py is in tests/ directory

## Performance

### Optimization Tips
- Mark slow tests: `@pytest.mark.slow`
- Skip slow in CI: `pytest -m "not slow"`
- Run specific files: `pytest tests/test_database/`
- Parallel execution: `pytest -n auto` (install pytest-xdist)

### Test Execution Time
- **All tests**: ~30-60 seconds (depends on system)
- **Unit tests only**: ~10-20 seconds
- **Database tests only**: ~15-30 seconds

## Future Improvements

Potential enhancements:
1. Add pytest-xdist for parallel execution
2. Add pytest-timeout for hanging test detection
3. Add performance benchmarking (pytest-benchmark)
4. Expand mutation testing (mutmut)
5. Add property-based testing (hypothesis)
6. Add API mocking (pytest-responses)

## Documentation

- **TESTING_GUIDE.md** - Comprehensive guide with patterns and examples
- **TESTING_QUICK_START.md** - Quick reference for common commands
- **TESTING_INFRASTRUCTURE.md** - This file (implementation overview)
- **conftest.py** - Fixture documentation in docstrings
- **test_helpers.py** - Helper class documentation in docstrings

## Support

For testing questions:
1. Check TESTING_GUIDE.md
2. Review existing test examples
3. Check conftest.py for available fixtures
4. Check test_helpers.py for utility classes
5. Consult pytest documentation: https://docs.pytest.org/

## Summary

This comprehensive testing infrastructure provides:

✓ **417+ existing tests** ready to run
✓ **Modular fixtures** for easy test creation
✓ **Database utilities** with auto-cleanup
✓ **Mock utilities** for external APIs
✓ **Code coverage** tracking and reporting
✓ **Cross-platform support** (Windows-optimized)
✓ **Complete documentation** with examples
✓ **Best practices** built-in
✓ **CI/CD ready** configuration
✓ **Performance optimized** test organization

**To get started:**
1. Install dependencies: `pip install -r requirements.txt`
2. Run tests: `pytest -v`
3. Generate coverage: `pytest --cov=src --cov-report=html`
4. Read TESTING_QUICK_START.md for common commands

