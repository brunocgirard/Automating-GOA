"""
Pytest configuration and fixtures for QuoteFlow Document Assistant tests.

This module provides shared fixtures, mocks, and utilities for all tests,
including database setup, sample data factories, and API mocks.

Windows-compatible using pathlib.Path for all file operations.
"""

import pytest
import sqlite3
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import tempfile

# Import database modules
from src.utils.db import (
    init_db,
    get_connection,
    save_client_info,
    save_priced_items,
    save_machines_data,
    DB_PATH,
)


# ============================================================================
# PATH FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def project_root():
    """Return the root directory of the project."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """Return the test data directory."""
    test_dir = project_root / "tests"
    test_dir.mkdir(exist_ok=True)
    return test_dir


@pytest.fixture(scope="session")
def templates_dir(project_root):
    """Return the templates directory."""
    return project_root / "templates"


@pytest.fixture(scope="session")
def data_dir(project_root):
    """Return the data directory."""
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


# ============================================================================
# SAMPLE PDF FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def sample_pdf_cqc(templates_dir):
    """Return path to sample CQC PDF for testing."""
    pdf_path = templates_dir / "CQC-25-2638R5-NP.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture(scope="session")
def sample_pdf_ume(templates_dir):
    """Return path to sample UME PDF for testing."""
    pdf_path = templates_dir / "UME-23-0001CN-R5-V2.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture(scope="session")
def sample_pdf_path(sample_pdf_cqc):
    """Default sample PDF fixture (CQC)."""
    return sample_pdf_cqc


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture
def temp_db_path(tmp_path):
    """
    Create an isolated test database in a temporary directory.

    Returns a Path object to a fresh database file.
    Automatically cleaned up after the test.

    Yields:
        Path: Path to the temporary test database
    """
    db_dir = tmp_path / "test_db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "test_crm.db"

    # Initialize the test database
    init_db(str(db_path))

    yield db_path

    # Cleanup happens automatically with tmp_path fixture


@pytest.fixture
def test_db_connection(temp_db_path):
    """
    Create a database connection to the test database.

    Yields:
        sqlite3.Connection: Connection to test database
    """
    conn = get_connection(str(temp_db_path))
    yield conn
    conn.close()


@pytest.fixture
def test_db_cursor(test_db_connection):
    """Create a database cursor for direct SQL operations."""
    cursor = test_db_connection.cursor()
    yield cursor
    test_db_connection.commit()


# ============================================================================
# SAMPLE DATA FACTORIES
# ============================================================================

@pytest.fixture
def sample_client_data():
    """Factory for creating sample client data."""
    def _create_client(
        quote_ref: str = "TEST-001",
        customer_name: str = "Test Customer Inc.",
        machine_model: str = "TestMaster 3000",
        sold_to_address: str = "123 Test St, Test City, TC 12345",
        ship_to_address: str = "456 Delivery Ave, Destination, DD 67890",
        telephone: str = "+1-555-0100",
        customer_contact_person: str = "John Tester",
        customer_po: str = "PO-20240115-001",
        incoterm: str = "CIF",
        company: str = "Test Company Ltd.",
        serial_number: str = "SN-2024-00001",
        ax: str = "AX-001",
        ox: str = "OX-001",
        via: str = "VIA-001",
        tax_id: str = "TAX-123456",
        hs_code: str = "843079",
        customer_number: str = "CUST-001",
        order_date: str = "2024-01-15",
    ) -> Dict[str, Any]:
        """
        Create a sample client data dictionary.

        Args:
            quote_ref: Quote reference number (unique identifier)
            customer_name: Name of the customer
            machine_model: Machine model name
            sold_to_address: Billing address
            ship_to_address: Delivery address
            telephone: Customer phone number
            customer_contact_person: Contact person name
            customer_po: Customer purchase order number
            incoterm: Incoterm code (CIF, FOB, etc.)
            company: Company name
            serial_number: Serial number of the machine
            ax: AX code
            ox: OX code
            via: VIA code
            tax_id: Tax ID
            hs_code: HS tariff code
            customer_number: Customer account number
            order_date: Order date

        Returns:
            Dict[str, Any]: Client data dictionary
        """
        return {
            "quote_ref": quote_ref,
            "customer_name": customer_name,
            "machine_model": machine_model,
            "sold_to_address": sold_to_address,
            "ship_to_address": ship_to_address,
            "telephone": telephone,
            "customer_contact_person": customer_contact_person,
            "customer_po": customer_po,
            "incoterm": incoterm,
            "company": company,
            "serial_number": serial_number,
            "ax": ax,
            "ox": ox,
            "via": via,
            "tax_id": tax_id,
            "hs_code": hs_code,
            "customer_number": customer_number,
            "order_date": order_date,
        }

    return _create_client


@pytest.fixture
def sample_machine_data():
    """Factory for creating sample machine data."""
    def _create_machine(
        machine_name: str = "TestMaster 3000",
        machine_type: str = "Standard",
        selected_items: Optional[List[Dict[str, Any]]] = None,
        add_ons: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a sample machine data dictionary.

        Args:
            machine_name: Name of the machine
            machine_type: Type of machine (Standard, SortStar, etc.)
            selected_items: List of selected line items for the machine
            add_ons: List of add-ons/optional items

        Returns:
            Dict[str, Any]: Machine data dictionary
        """
        if selected_items is None:
            selected_items = [
                {
                    "description": "Main machine unit",
                    "quantity": 1,
                    "unit_price": 50000.00,
                    "total_price": 50000.00,
                }
            ]

        if add_ons is None:
            add_ons = [
                {
                    "description": "Installation service",
                    "quantity": 1,
                    "unit_price": 5000.00,
                    "total_price": 5000.00,
                }
            ]

        return {
            "machine_name": machine_name,
            "machine_type": machine_type,
            "selected_items": selected_items,
            "add_ons": add_ons,
        }

    return _create_machine


@pytest.fixture
def sample_priced_items_data():
    """Factory for creating sample priced items."""
    def _create_items(
        quote_ref: str = "TEST-001",
        item_count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Create sample priced items for a quote.

        Args:
            quote_ref: Quote reference to associate items with
            item_count: Number of items to generate

        Returns:
            List[Dict[str, Any]]: List of item dictionaries
        """
        items = []
        base_price = 10000.00

        for i in range(item_count):
            items.append({
                "quote_ref": quote_ref,
                "item_description": f"Test Item {i + 1}",
                "item_quantity": (i + 1),
                "unit_price": base_price + (i * 1000),
                "total_price": (base_price + (i * 1000)) * (i + 1),
                "extraction_confidence": 0.95,
            })

        return items

    return _create_items


@pytest.fixture
def populated_test_db(temp_db_path, sample_client_data, sample_machine_data, sample_priced_items_data):
    """
    Create a test database pre-populated with sample data.

    Yields:
        Path: Path to populated test database
    """
    # Create client
    client_data = sample_client_data(quote_ref="POPULATED-001")
    save_client_info(client_data, str(temp_db_path))

    # Create priced items
    items = sample_priced_items_data(quote_ref="POPULATED-001", item_count=3)
    save_priced_items("POPULATED-001", items, str(temp_db_path))

    # Create machines
    machine_data = sample_machine_data(
        machine_name="TestMaster 3000",
        machine_type="Standard",
        selected_items=[items[0], items[1]],
        add_ons=[items[2]],
    )
    machines = [machine_data]
    save_machines_data("POPULATED-001", machines, str(temp_db_path))

    yield temp_db_path


# ============================================================================
# GEMINI API MOCKING FIXTURES
# ============================================================================

@pytest.fixture
def mock_gemini_response():
    """Factory for creating mock Gemini API responses."""
    def _create_response(
        content: str = "Test response from Gemini",
        status_code: int = 200,
        has_error: bool = False,
    ) -> Mock:
        """
        Create a mock Gemini API response.

        Args:
            content: Response content/text
            status_code: HTTP status code
            has_error: Whether the response indicates an error

        Returns:
            Mock: Mock response object
        """
        response = Mock()
        response.text = content
        response.content = content.encode() if isinstance(content, str) else content
        response.status_code = status_code

        if has_error:
            response.error = Mock(message="Mock error")
        else:
            response.error = None

        return response

    return _create_response


@pytest.fixture
def mock_gemini_client():
    """
    Create a mock Gemini client for testing LLM integration.

    Yields:
        Mock: Mock Gemini client with common methods
    """
    client = MagicMock()

    # Mock the generate_content method
    def mock_generate_content(prompt, **kwargs):
        response = Mock()
        response.text = json.dumps({
            "customer_name": "Mock Customer",
            "machine_model": "Mock Model",
            "production_speed": "100 units/hour",
        })
        return response

    client.generate_content = mock_generate_content

    yield client


@pytest.fixture
def patch_gemini_client(mock_gemini_client):
    """
    Patch the Gemini client for all tests using this fixture.

    Yields:
        Mock: The patched Gemini client
    """
    with patch("src.llm.client.ChatGoogleGenerativeAI") as mock_chat:
        mock_chat.return_value = mock_gemini_client
        yield mock_gemini_client


# ============================================================================
# MOCK UTILITIES AND HELPERS
# ============================================================================

@pytest.fixture
def mock_pdf_utils():
    """
    Create mock PDF utility functions.

    Yields:
        Dict: Dictionary of mocked PDF utility functions
    """
    mocks = {
        "extract_line_item_details": Mock(
            return_value=[
                {
                    "description": "Item 1",
                    "quantity": 1,
                    "unit_price": 1000.00,
                    "total_price": 1000.00,
                },
                {
                    "description": "Item 2",
                    "quantity": 2,
                    "unit_price": 500.00,
                    "total_price": 1000.00,
                },
            ]
        ),
        "identify_machines_from_items": Mock(
            return_value={
                "machines": [
                    {
                        "machine_name": "Test Machine",
                        "machine_type": "Standard",
                        "selected_items": [],
                    }
                ],
                "common_items": [],
            }
        ),
    }

    yield mocks


@pytest.fixture
def mock_streamlit():
    """
    Create mock Streamlit components for testing UI logic.

    Yields:
        Mock: Mocked Streamlit module
    """
    with patch("streamlit") as mock_st:
        mock_st.session_state = {}
        mock_st.success = Mock()
        mock_st.error = Mock()
        mock_st.warning = Mock()
        mock_st.info = Mock()
        mock_st.write = Mock()
        mock_st.button = Mock(return_value=False)
        mock_st.text_input = Mock(return_value="")
        mock_st.selectbox = Mock(return_value=None)
        mock_st.file_uploader = Mock(return_value=None)

        yield mock_st


# ============================================================================
# FILE CLEANUP FIXTURES
# ============================================================================

@pytest.fixture
def cleanup_test_files(tmp_path):
    """
    Fixture to cleanup temporary test files.

    This fixture automatically cleans up files created during tests.
    The tmp_path fixture already handles cleanup, but this provides
    a convenient way to manually trigger cleanup if needed.

    Yields:
        Callable: Function to cleanup a specific file or directory
    """
    created_paths = []

    def _cleanup(path: Optional[Path] = None):
        """
        Cleanup a specific path or all created paths.

        Args:
            path: Specific path to cleanup. If None, cleanup all created paths.
        """
        if path is None:
            # Cleanup all created paths
            for p in created_paths:
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    elif p.exists():
                        p.unlink()
                except Exception as e:
                    print(f"[WARN] Failed to cleanup {p}: {e}")
        else:
            # Cleanup specific path
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                if path in created_paths:
                    created_paths.remove(path)
            except Exception as e:
                print(f"[WARN] Failed to cleanup {path}: {e}")

    def _track_path(path: Path) -> Path:
        """Track a path for later cleanup."""
        created_paths.append(path)
        return path

    _cleanup.track = _track_path

    yield _cleanup

    # Auto-cleanup all tracked paths
    _cleanup()


# ============================================================================
# ISOLATED DATABASE CONTEXT FIXTURE
# ============================================================================

@pytest.fixture
def isolated_db(temp_db_path, monkeypatch):
    """
    Create an isolated database context for tests.

    This fixture monkeypatches the DB_PATH to point to the test database,
    ensuring that tests don't interfere with the production database.

    Yields:
        Path: Path to the isolated test database
    """
    # Monkeypatch the DB_PATH in all relevant modules
    import src.utils.db.base
    monkeypatch.setattr(src.utils.db.base, "DB_PATH", str(temp_db_path))

    yield temp_db_path


# ============================================================================
# LOGGING AND DEBUG FIXTURES
# ============================================================================

@pytest.fixture
def caplog_unicode(caplog):
    """
    Fixture for capturing logs with proper Unicode handling on Windows.

    Uses ASCII-only output for Windows compatibility.

    Yields:
        logging.LogCaptureFixture: The caplog fixture
    """
    # Force ASCII output mode
    import logging
    caplog.handler.setFormatter(
        logging.Formatter('[%(levelname)s] %(message)s')
    )

    yield caplog


# ============================================================================
# PYTEST CONFIGURATION HOOKS
# ============================================================================

def pytest_configure(config):
    """Configure pytest at startup."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "database: mark test as a database test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add unit marker to all tests by default
        if "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)


# ============================================================================
# TEMPORARY DIRECTORY CLEANUP
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_session(request):
    """
    Auto-cleanup session-scoped temporary resources.

    This fixture automatically runs after all tests and cleans up
    any remaining temporary resources.
    """
    yield

    # Cleanup code runs here after all tests
    # The tmp_path fixture handles its own cleanup automatically


# ============================================================================
# HELPER UTILITY FUNCTIONS (not fixtures)
# ============================================================================

def create_test_file(path: Path, content: str = "") -> Path:
    """
    Create a test file with optional content.

    Args:
        path: Path where to create the file
        content: File content (default: empty)

    Returns:
        Path: Path to the created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_test_database(db_path: Path) -> Path:
    """
    Create and initialize a test database.

    Args:
        db_path: Path where to create the database

    Returns:
        Path: Path to the created database
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(str(db_path))
    return db_path
