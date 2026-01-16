"""
Testing helpers and utilities for QuoteFlow Document Assistant tests.

This module provides utility functions and classes to support testing,
including database helpers, mock utilities, and test data generation.

Windows-compatible using pathlib.Path for all file operations.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil


class DatabaseTestHelper:
    """Helper class for database operations in tests."""

    def __init__(self, db_path: Path):
        """
        Initialize database helper.

        Args:
            db_path: Path to the test database file
        """
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self) -> sqlite3.Connection:
        """
        Create a database connection.

        Returns:
            sqlite3.Connection: Database connection
        """
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a SQL query.

        Args:
            sql: SQL query to execute
            params: Query parameters

        Returns:
            sqlite3.Cursor: Query cursor
        """
        if not self.conn:
            self.connect()
        return self.conn.execute(sql, params)

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Fetch a single record.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            Optional[Dict]: Single record or None
        """
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Fetch all records.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            List[Dict]: All matching records
        """
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table

        Returns:
            bool: True if table exists
        """
        cursor = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    def get_table_row_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.

        Args:
            table_name: Name of the table

        Returns:
            int: Number of rows
        """
        cursor = self.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]

    def clear_table(self, table_name: str):
        """
        Clear all data from a table.

        Args:
            table_name: Name of the table to clear
        """
        self.execute(f"DELETE FROM {table_name}")
        self.conn.commit()

    def backup(self, backup_path: Path) -> Path:
        """
        Create a backup of the database.

        Args:
            backup_path: Path where to save the backup

        Returns:
            Path: Path to the backup file
        """
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        if self.conn:
            backup_conn = sqlite3.connect(str(backup_path))
            self.conn.backup(backup_conn)
            backup_conn.close()
        else:
            shutil.copy2(self.db_path, backup_path)

        return backup_path


class MockDataGenerator:
    """Generate realistic mock data for testing."""

    @staticmethod
    def generate_quote_ref(prefix: str = "TEST") -> str:
        """
        Generate a quote reference.

        Args:
            prefix: Reference prefix

        Returns:
            str: Generated reference
        """
        import random
        import string
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"{prefix}-{suffix}"

    @staticmethod
    def generate_client_dict(
        quote_ref: Optional[str] = None,
        **overrides
    ) -> Dict[str, Any]:
        """
        Generate a complete client dictionary.

        Args:
            quote_ref: Quote reference (auto-generated if None)
            **overrides: Field overrides

        Returns:
            Dict[str, Any]: Complete client dictionary
        """
        if quote_ref is None:
            quote_ref = MockDataGenerator.generate_quote_ref()

        base_data = {
            "quote_ref": quote_ref,
            "customer_name": "Test Company Inc.",
            "machine_model": "TestMaster 3000",
            "sold_to_address": "123 Test Street, Test City, TC 12345",
            "ship_to_address": "456 Delivery Avenue, Destination, DD 67890",
            "telephone": "+1-555-0100",
            "customer_contact_person": "John Tester",
            "customer_po": f"PO-{quote_ref}",
            "incoterm": "CIF",
            "company": "Test Corporation",
            "serial_number": f"SN-{quote_ref}",
            "ax": "AX-001",
            "ox": "OX-001",
            "via": "VIA-001",
            "tax_id": "TAX-123456789",
            "hs_code": "843079",
            "customer_number": "CUST-001",
            "order_date": datetime.now().strftime("%Y-%m-%d"),
        }

        base_data.update(overrides)
        return base_data

    @staticmethod
    def generate_item_dict(
        quote_ref: Optional[str] = None,
        item_num: int = 1,
        **overrides
    ) -> Dict[str, Any]:
        """
        Generate a priced item dictionary.

        Args:
            quote_ref: Quote reference
            item_num: Item number for description
            **overrides: Field overrides

        Returns:
            Dict[str, Any]: Item dictionary
        """
        if quote_ref is None:
            quote_ref = MockDataGenerator.generate_quote_ref()

        base_price = 5000 * item_num
        quantity = item_num

        base_data = {
            "quote_ref": quote_ref,
            "item_description": f"Test Item {item_num}",
            "item_quantity": quantity,
            "unit_price": base_price,
            "total_price": base_price * quantity,
            "extraction_confidence": 0.95,
        }

        base_data.update(overrides)
        return base_data

    @staticmethod
    def generate_machine_dict(
        machine_name: Optional[str] = None,
        **overrides
    ) -> Dict[str, Any]:
        """
        Generate a machine dictionary.

        Args:
            machine_name: Name of the machine
            **overrides: Field overrides

        Returns:
            Dict[str, Any]: Machine dictionary
        """
        if machine_name is None:
            machine_name = "TestMaster 3000"

        base_data = {
            "machine_name": machine_name,
            "machine_type": "Standard",
            "selected_items": [
                {
                    "description": "Main Unit",
                    "quantity": 1,
                    "unit_price": 50000.00,
                    "total_price": 50000.00,
                }
            ],
            "add_ons": [
                {
                    "description": "Installation",
                    "quantity": 1,
                    "unit_price": 5000.00,
                    "total_price": 5000.00,
                }
            ],
        }

        base_data.update(overrides)
        return base_data


class LLMResponseMocker:
    """Mock LLM responses for testing."""

    @staticmethod
    def create_extraction_response(
        fields: Optional[Dict[str, Any]] = None,
        confidence: float = 0.95,
    ) -> str:
        """
        Create a mock LLM extraction response.

        Args:
            fields: Field values to include
            confidence: Confidence score

        Returns:
            str: JSON response string
        """
        if fields is None:
            fields = {
                "customer_name": "Test Customer",
                "machine_model": "TestMaster 3000",
                "production_speed": "100 units/hour",
                "voltage": "380V",
                "frequency": "50Hz",
            }

        response = {
            "fields": fields,
            "confidence": confidence,
            "extraction_method": "llm",
        }

        return json.dumps(response)

    @staticmethod
    def create_text_response(text: str = "Mock LLM response") -> str:
        """
        Create a simple text response.

        Args:
            text: Response text

        Returns:
            str: Response
        """
        return text

    @staticmethod
    def mock_gemini_generate_content(
        response_text: Optional[str] = None,
    ) -> Callable:
        """
        Create a mock generate_content function.

        Args:
            response_text: Response text to return

        Returns:
            Callable: Mock function
        """
        if response_text is None:
            response_text = LLMResponseMocker.create_extraction_response()

        def _mock_generate(prompt, **kwargs):
            response = Mock()
            response.text = response_text
            return response

        return _mock_generate


class FileTestHelper:
    """Helper for file operations in tests."""

    @staticmethod
    def create_temp_file(
        content: str = "",
        suffix: str = ".txt",
        dir_path: Optional[Path] = None,
    ) -> Path:
        """
        Create a temporary file.

        Args:
            content: File content
            suffix: File extension
            dir_path: Directory for the file

        Returns:
            Path: Path to created file
        """
        if dir_path:
            dir_path = Path(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True)
            temp_file = dir_path / f"test{suffix}"
        else:
            temp_dir = Path(tempfile.mkdtemp())
            temp_file = temp_dir / f"test{suffix}"

        temp_file.write_text(content)
        return temp_file

    @staticmethod
    def create_temp_dir() -> Path:
        """
        Create a temporary directory.

        Returns:
            Path: Path to created directory
        """
        return Path(tempfile.mkdtemp())

    @staticmethod
    def cleanup_path(path: Path):
        """
        Cleanup a file or directory.

        Args:
            path: Path to cleanup
        """
        path = Path(path)
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except Exception as e:
            print(f"[WARN] Failed to cleanup {path}: {e}")


class AssertionHelpers:
    """Custom assertion helpers for tests."""

    @staticmethod
    def assert_valid_quote_ref(quote_ref: str):
        """
        Assert that a quote reference is valid.

        Args:
            quote_ref: Quote reference to validate

        Raises:
            AssertionError: If quote reference is invalid
        """
        assert quote_ref, "Quote reference cannot be empty"
        assert isinstance(quote_ref, str), "Quote reference must be a string"
        assert len(quote_ref) > 0, "Quote reference must not be empty"

    @staticmethod
    def assert_valid_client_data(client_data: Dict[str, Any]):
        """
        Assert that client data is valid.

        Args:
            client_data: Client data to validate

        Raises:
            AssertionError: If client data is invalid
        """
        assert isinstance(client_data, dict), "Client data must be a dictionary"
        assert "quote_ref" in client_data, "quote_ref is required"
        AssertionHelpers.assert_valid_quote_ref(client_data["quote_ref"])

    @staticmethod
    def assert_valid_item_data(item_data: Dict[str, Any]):
        """
        Assert that item data is valid.

        Args:
            item_data: Item data to validate

        Raises:
            AssertionError: If item data is invalid
        """
        assert isinstance(item_data, dict), "Item data must be a dictionary"
        assert "quote_ref" in item_data, "quote_ref is required"
        assert "item_description" in item_data, "item_description is required"
        assert item_data["item_quantity"] > 0, "item_quantity must be positive"
        assert item_data["unit_price"] >= 0, "unit_price must be non-negative"

    @staticmethod
    def assert_database_has_record(
        db_helper: DatabaseTestHelper,
        table_name: str,
        where_clause: str = "",
        params: tuple = (),
    ) -> bool:
        """
        Assert that database has at least one matching record.

        Args:
            db_helper: Database helper instance
            table_name: Table name
            where_clause: WHERE clause (without WHERE keyword)
            params: Query parameters

        Returns:
            bool: True if record exists

        Raises:
            AssertionError: If no record found
        """
        sql = f"SELECT COUNT(*) FROM {table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"

        cursor = db_helper.execute(sql, params)
        count = cursor.fetchone()[0]

        assert count > 0, f"No records found in {table_name}"
        return True


# ============================================================================
# CONTEXT MANAGERS FOR TESTING
# ============================================================================

class TempDatabaseContext:
    """Context manager for temporary test databases."""

    def __init__(self, init_func=None):
        """
        Initialize context manager.

        Args:
            init_func: Optional function to initialize database
        """
        self.init_func = init_func
        self.db_path = None
        self.helper = None

    def __enter__(self) -> DatabaseTestHelper:
        """
        Enter context and create temporary database.

        Returns:
            DatabaseTestHelper: Database helper instance
        """
        temp_dir = Path(tempfile.mkdtemp())
        self.db_path = temp_dir / "test.db"

        if self.init_func:
            self.init_func(str(self.db_path))

        self.helper = DatabaseTestHelper(self.db_path)
        self.helper.connect()
        return self.helper

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and cleanup."""
        if self.helper:
            self.helper.close()

        if self.db_path and self.db_path.parent.exists():
            shutil.rmtree(self.db_path.parent)


class MockGeminiContext:
    """Context manager for mocking Gemini API."""

    def __init__(self, response_text: Optional[str] = None):
        """
        Initialize context manager.

        Args:
            response_text: Response text to return
        """
        self.response_text = response_text
        self.patcher = None

    def __enter__(self) -> Mock:
        """
        Enter context and setup mock.

        Returns:
            Mock: Mock Gemini client
        """
        mock_client = Mock()
        mock_client.generate_content = LLMResponseMocker.mock_gemini_generate_content(
            self.response_text
        )

        self.patcher = patch("src.llm.client.ChatGoogleGenerativeAI")
        mock_class = self.patcher.start()
        mock_class.return_value = mock_client

        return mock_client

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and stop patching."""
        if self.patcher:
            self.patcher.stop()
