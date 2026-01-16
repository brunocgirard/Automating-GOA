"""
Database unit tests for QuoteFlow Document Assistant.

This package contains comprehensive unit tests for all database operations
including client management, machine operations, priced items, and few-shot
learning.

Test modules:
- test_clients.py: Client CRUD and related operations
- test_machines.py: Machine identification and management
- test_items.py: Priced items handling and calculations
- test_few_shot.py: Few-shot learning examples and feedback

To run all database tests:
    pytest tests/test_database/ -v

To run specific test file:
    pytest tests/test_database/test_clients.py -v

To run specific test class:
    pytest tests/test_database/test_clients.py::TestSaveClientInfo -v

To run with coverage:
    pytest tests/test_database/ --cov=src.utils.db --cov-report=html
"""
