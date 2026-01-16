"""
Comprehensive unit tests for machine database operations.

Tests cover:
- save_machines_data() for storing identified machines
- load_machines_for_quote() retrieval
- find_machines_by_name() search operations
- Machine identification logic and grouping
- Price calculations for machines and add-ons
- Edge cases and validation
"""

import pytest
import json
import sqlite3
from typing import Dict, List, Any

from src.utils.db import (
    save_machines_data,
    load_machines_for_quote,
    find_machines_by_name,
    load_all_processed_machines,
    group_items_by_confirmed_machines,
    calculate_machine_price,
    save_client_info,
    save_priced_items,
    save_machine_template_data,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def standard_machine_data():
    """Create standard machine data structure."""
    return {
        "machines": [
            {
                "machine_name": "AutoFill 3000",
                "main_item": {
                    "description": "AutoFill 3000 Filling Machine",
                    "quantity": 1,
                    "item_price_numeric": 50000.00,
                },
                "add_ons": [
                    {
                        "description": "Installation Service",
                        "quantity": 1,
                        "item_price_numeric": 5000.00,
                    },
                    {
                        "description": "Training Package",
                        "quantity": 1,
                        "item_price_numeric": 2000.00,
                    },
                ],
            },
        ],
        "common_items": [
            {
                "description": "Spare Parts Kit",
                "quantity": 1,
                "item_price_numeric": 3000.00,
            },
        ],
    }


@pytest.fixture
def multi_machine_data():
    """Create data with multiple machines."""
    return {
        "machines": [
            {
                "machine_name": "Filling Machine A",
                "main_item": {
                    "description": "Filling Machine A Description",
                    "quantity": 1,
                    "item_price_numeric": 30000.00,
                },
                "add_ons": [
                    {
                        "description": "Add-on 1",
                        "quantity": 1,
                        "item_price_numeric": 2000.00,
                    },
                ],
            },
            {
                "machine_name": "Labeling Machine B",
                "main_item": {
                    "description": "Labeling Machine B Description",
                    "quantity": 1,
                    "item_price_numeric": 20000.00,
                },
                "add_ons": [
                    {
                        "description": "Add-on 2",
                        "quantity": 1,
                        "item_price_numeric": 1000.00,
                    },
                ],
            },
        ],
        "common_items": [],
    }


@pytest.fixture
def client_with_machines(temp_db_path, standard_machine_data):
    """Create a client and save machines for it."""
    client_data = {
        "quote_ref": "MACHINE-TEST-001",
        "customer_name": "Machine Test Customer",
    }
    save_client_info(client_data, str(temp_db_path))
    save_machines_data("MACHINE-TEST-001", standard_machine_data, str(temp_db_path))
    return temp_db_path, "MACHINE-TEST-001"


# ============================================================================
# SAVE MACHINES DATA TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.database
class TestSaveMachinesData:
    """Test suite for save_machines_data() function."""

    def test_save_single_machine_success(self, temp_db_path, standard_machine_data):
        """Test successful saving of a single machine."""
        # First create client
        client_data = {"quote_ref": "SAVE-MACHINE-001"}
        save_client_info(client_data, str(temp_db_path))

        # Save machines
        result = save_machines_data("SAVE-MACHINE-001", standard_machine_data, str(temp_db_path))
        assert result is True

        # Verify saved
        machines = load_machines_for_quote("SAVE-MACHINE-001", str(temp_db_path))
        assert len(machines) == 1
        assert machines[0]["machine_name"] == "AutoFill 3000"

    def test_save_multiple_machines(self, temp_db_path, multi_machine_data):
        """Test saving multiple machines for a single quote."""
        client_data = {"quote_ref": "MULTI-MACHINE-001"}
        save_client_info(client_data, str(temp_db_path))

        result = save_machines_data("MULTI-MACHINE-001", multi_machine_data, str(temp_db_path))
        assert result is True

        machines = load_machines_for_quote("MULTI-MACHINE-001", str(temp_db_path))
        assert len(machines) == 2
        machine_names = [m["machine_name"] for m in machines]
        assert "Filling Machine A" in machine_names
        assert "Labeling Machine B" in machine_names

    def test_save_machines_without_client(self, temp_db_path, standard_machine_data):
        """Test that save_machines_data creates client if it doesn't exist."""
        # Don't create client first
        result = save_machines_data("NO-CLIENT-001", standard_machine_data, str(temp_db_path))
        assert result is True

        # Verify client was created
        machines = load_machines_for_quote("NO-CLIENT-001", str(temp_db_path))
        assert len(machines) == 1

    def test_save_machines_overwrites_previous(self, temp_db_path, standard_machine_data):
        """Test that saving new machines overwrites previous data."""
        client_data = {"quote_ref": "OVERWRITE-001"}
        save_client_info(client_data, str(temp_db_path))

        # Save first set
        save_machines_data("OVERWRITE-001", standard_machine_data, str(temp_db_path))
        machines1 = load_machines_for_quote("OVERWRITE-001", str(temp_db_path))
        assert len(machines1) == 1

        # Save different machines
        new_data = {
            "machines": [
                {
                    "machine_name": "New Machine",
                    "main_item": {"description": "New"},
                    "add_ons": [],
                },
                {
                    "machine_name": "Another New",
                    "main_item": {"description": "Another"},
                    "add_ons": [],
                },
            ],
            "common_items": [],
        }
        save_machines_data("OVERWRITE-001", new_data, str(temp_db_path))

        # Should have new machines, old ones deleted
        machines2 = load_machines_for_quote("OVERWRITE-001", str(temp_db_path))
        assert len(machines2) == 2
        assert machines2[0]["machine_name"] == "New Machine"

    def test_save_machines_with_common_items(self, temp_db_path, standard_machine_data):
        """Test that common items are stored with machines."""
        client_data = {"quote_ref": "COMMON-ITEMS-001"}
        save_client_info(client_data, str(temp_db_path))

        save_machines_data("COMMON-ITEMS-001", standard_machine_data, str(temp_db_path))

        machines = load_machines_for_quote("COMMON-ITEMS-001", str(temp_db_path))
        machine_data = machines[0]["machine_data"]
        assert "common_items" in machine_data
        assert len(machine_data["common_items"]) == 1


@pytest.mark.unit
@pytest.mark.database
class TestLoadMachinesForQuote:
    """Test suite for load_machines_for_quote() function."""

    def test_load_machines_success(self, client_with_machines):
        """Test successfully loading machines for a quote."""
        temp_db_path, quote_ref = client_with_machines

        machines = load_machines_for_quote(quote_ref, str(temp_db_path))
        assert len(machines) == 1
        assert machines[0]["machine_name"] == "AutoFill 3000"

    def test_load_machines_empty_quote(self, temp_db_path):
        """Test loading machines for a quote with no machines."""
        client_data = {"quote_ref": "NO-MACHINES-001"}
        save_client_info(client_data, str(temp_db_path))

        machines = load_machines_for_quote("NO-MACHINES-001", str(temp_db_path))
        assert machines == []

    def test_load_machines_nonexistent_quote(self, temp_db_path):
        """Test loading machines for non-existent quote returns empty list."""
        machines = load_machines_for_quote("NONEXISTENT-001", str(temp_db_path))
        assert machines == []

    def test_loaded_machines_have_parsed_json(self, client_with_machines):
        """Test that loaded machines have both JSON string and parsed dict."""
        temp_db_path, quote_ref = client_with_machines

        machines = load_machines_for_quote(quote_ref, str(temp_db_path))
        assert len(machines) == 1

        machine = machines[0]
        assert "machine_data_json" in machine
        assert "machine_data" in machine
        assert isinstance(machine["machine_data"], dict)

    def test_loaded_machines_preserve_structure(self, client_with_machines):
        """Test that machine data structure is preserved on load."""
        temp_db_path, quote_ref = client_with_machines

        machines = load_machines_for_quote(quote_ref, str(temp_db_path))
        machine_data = machines[0]["machine_data"]

        assert "machine_name" in machine_data
        assert "main_item" in machine_data
        assert "add_ons" in machine_data
        assert "common_items" in machine_data


@pytest.mark.unit
@pytest.mark.database
class TestFindMachinesByName:
    """Test suite for find_machines_by_name() function."""

    def test_find_machine_exact_match(self, client_with_machines):
        """Test finding machine by exact name."""
        temp_db_path, quote_ref = client_with_machines

        results = find_machines_by_name("AutoFill 3000", str(temp_db_path))
        assert len(results) >= 1
        assert any(m["machine_name"] == "AutoFill 3000" for m in results)

    def test_find_machine_partial_match(self, client_with_machines):
        """Test finding machine by partial name match."""
        temp_db_path, quote_ref = client_with_machines

        results = find_machines_by_name("AutoFill", str(temp_db_path))
        assert len(results) >= 1
        assert any("AutoFill" in m["machine_name"] for m in results)

    def test_find_machine_case_insensitive(self, client_with_machines):
        """Test that search is case-insensitive."""
        temp_db_path, quote_ref = client_with_machines

        results_lower = find_machines_by_name("autofill", str(temp_db_path))
        results_upper = find_machines_by_name("AUTOFILL", str(temp_db_path))

        assert len(results_lower) >= 1
        assert len(results_upper) >= 1

    def test_find_machine_nonexistent(self, client_with_machines):
        """Test finding non-existent machine returns empty list."""
        temp_db_path, quote_ref = client_with_machines

        results = find_machines_by_name("NonexistentMachine", str(temp_db_path))
        assert results == []

    def test_find_machine_includes_client_info(self, client_with_machines):
        """Test that search results include related client information."""
        temp_db_path, quote_ref = client_with_machines

        results = find_machines_by_name("AutoFill", str(temp_db_path))
        assert len(results) >= 1

        machine = results[0]
        assert "client_quote_ref" in machine
        assert "customer_name" in machine

    def test_find_multiple_machines_same_name_different_quotes(self, temp_db_path):
        """Test finding same machine name across different quotes."""
        # Create two clients with same machine name
        for i in range(2):
            client_data = {"quote_ref": f"MULTI-QUOTE-{i:03d}"}
            save_client_info(client_data, str(temp_db_path))

            machine_data = {
                "machines": [
                    {
                        "machine_name": "Shared Machine Name",
                        "main_item": {"description": "Shared"},
                        "add_ons": [],
                    },
                ],
                "common_items": [],
            }
            save_machines_data(client_data["quote_ref"], machine_data, str(temp_db_path))

        results = find_machines_by_name("Shared Machine", str(temp_db_path))
        assert len(results) >= 2


@pytest.mark.unit
@pytest.mark.database
class TestLoadAllProcessedMachines:
    """Test suite for load_all_processed_machines() function."""

    def test_load_processed_machines_empty(self, temp_db_path):
        """Test loading processed machines from empty database."""
        machines = load_all_processed_machines(str(temp_db_path))
        assert machines == []

    def test_load_processed_machines_requires_template(self, client_with_machines):
        """Test that load_all_processed_machines only returns machines with templates."""
        temp_db_path, quote_ref = client_with_machines

        # Machines exist but have no templates
        machines = load_all_processed_machines(str(temp_db_path))
        assert len(machines) == 0

        # Add a template
        machine_id = load_machines_for_quote(quote_ref, str(temp_db_path))[0]["id"]
        save_machine_template_data(
            machine_id,
            "default",
            {"field1": "value1"},
            "/path/to/output.html",
            str(temp_db_path)
        )

        # Now should appear in processed machines
        machines = load_all_processed_machines(str(temp_db_path))
        assert len(machines) >= 1


# ============================================================================
# MACHINE GROUPING AND PRICE CALCULATION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.database
class TestGroupItemsByConfirmedMachines:
    """Test suite for group_items_by_confirmed_machines() function."""

    def test_group_single_machine_no_addons(self):
        """Test grouping with single machine and no add-ons."""
        items = [
            {"description": "Machine 1", "price": 10000},
            {"description": "Common Item", "price": 500},
        ]

        result = group_items_by_confirmed_machines(items, [0], [1])

        assert len(result["machines"]) == 1
        assert result["machines"][0]["machine_name"] == "Machine 1"
        assert len(result["machines"][0]["add_ons"]) == 0
        assert len(result["common_items"]) == 1

    def test_group_machine_with_addons(self):
        """Test grouping machine with add-ons."""
        items = [
            {"description": "Main Machine", "price": 50000},
            {"description": "Add-on 1", "price": 5000},
            {"description": "Add-on 2", "price": 2000},
            {"description": "Common", "price": 1000},
        ]

        result = group_items_by_confirmed_machines(items, [0], [3])

        assert len(result["machines"]) == 1
        assert result["machines"][0]["machine_name"] == "Main Machine"
        assert len(result["machines"][0]["add_ons"]) == 2
        assert len(result["common_items"]) == 1

    def test_group_multiple_machines(self):
        """Test grouping multiple machines."""
        items = [
            {"description": "Machine 1", "price": 30000},
            {"description": "Add-on 1A", "price": 2000},
            {"description": "Machine 2", "price": 20000},
            {"description": "Add-on 2A", "price": 1000},
            {"description": "Common", "price": 500},
        ]

        result = group_items_by_confirmed_machines(items, [0, 2], [4])

        assert len(result["machines"]) == 2
        assert result["machines"][0]["machine_name"] == "Machine 1"
        assert len(result["machines"][0]["add_ons"]) == 1
        assert result["machines"][1]["machine_name"] == "Machine 2"
        assert len(result["machines"][1]["add_ons"]) == 1
        assert len(result["common_items"]) == 1

    def test_group_with_multiline_description(self):
        """Test that machine name is extracted from multiline description."""
        items = [
            {
                "description": "Machine Name\nLine 2\nLine 3",
                "price": 10000,
            },
            {"description": "Common", "price": 500},
        ]

        result = group_items_by_confirmed_machines(items, [0], [1])

        # Should use first line of description
        assert result["machines"][0]["machine_name"] == "Machine Name"


@pytest.mark.unit
@pytest.mark.database
class TestCalculateMachinePrice:
    """Test suite for calculate_machine_price() function."""

    def test_calculate_price_main_item_only(self):
        """Test price calculation with only main item."""
        machine_data = {
            "main_item": {"item_price_numeric": 50000.00},
            "add_ons": [],
        }

        price = calculate_machine_price(machine_data)
        assert price == 50000.00

    def test_calculate_price_with_addons(self):
        """Test price calculation with main item and add-ons."""
        machine_data = {
            "main_item": {"item_price_numeric": 50000.00},
            "add_ons": [
                {"item_price_numeric": 5000.00},
                {"item_price_numeric": 2000.00},
                {"item_price_numeric": 1000.00},
            ],
        }

        price = calculate_machine_price(machine_data)
        assert price == 58000.00

    def test_calculate_price_no_prices(self):
        """Test price calculation with missing prices."""
        machine_data = {
            "main_item": {"item_price_numeric": None},
            "add_ons": [
                {"item_price_numeric": None},
                {"item_price_numeric": 500.00},
            ],
        }

        price = calculate_machine_price(machine_data)
        assert price == 500.00

    def test_calculate_price_empty_addons(self):
        """Test price calculation with empty add-ons list."""
        machine_data = {
            "main_item": {"item_price_numeric": 30000.00},
            "add_ons": [],
        }

        price = calculate_machine_price(machine_data)
        assert price == 30000.00

    def test_calculate_price_missing_main_item(self):
        """Test price calculation when main_item is missing."""
        machine_data = {
            "add_ons": [
                {"item_price_numeric": 1000.00},
                {"item_price_numeric": 500.00},
            ],
        }

        price = calculate_machine_price(machine_data)
        assert price == 1500.00


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

@pytest.mark.unit
@pytest.mark.database
class TestMachineEdgeCases:
    """Test suite for edge cases in machine operations."""

    def test_save_machines_with_missing_quote_ref(self, temp_db_path, standard_machine_data):
        """Test that saving machines without quote_ref fails."""
        result = save_machines_data("", standard_machine_data, str(temp_db_path))
        assert result is False

    def test_save_machines_with_no_machines_list(self, temp_db_path):
        """Test that saving without 'machines' key fails."""
        client_data = {"quote_ref": "NO-MACHINES-KEY"}
        save_client_info(client_data, str(temp_db_path))

        bad_data = {"common_items": []}  # Missing 'machines' key
        result = save_machines_data("NO-MACHINES-KEY", bad_data, str(temp_db_path))
        assert result is False

    def test_save_machines_with_empty_machines_list(self, temp_db_path):
        """Test that saving with empty machines list fails."""
        client_data = {"quote_ref": "EMPTY-MACHINES"}
        save_client_info(client_data, str(temp_db_path))

        bad_data = {"machines": [], "common_items": []}
        result = save_machines_data("EMPTY-MACHINES", bad_data, str(temp_db_path))
        assert result is False

    def test_save_machine_with_generated_name(self, temp_db_path):
        """Test that machine name is generated if missing."""
        client_data = {"quote_ref": "GEN-NAME-001"}
        save_client_info(client_data, str(temp_db_path))

        machine_data = {
            "machines": [
                {
                    # No machine_name provided
                    "main_item": {
                        "description": "Item with description",
                        "item_price_numeric": 5000.00,
                    },
                    "add_ons": [],
                },
            ],
            "common_items": [],
        }

        result = save_machines_data("GEN-NAME-001", machine_data, str(temp_db_path))
        assert result is True

        machines = load_machines_for_quote("GEN-NAME-001", str(temp_db_path))
        # Should have a generated name
        assert machines[0]["machine_name"] is not None
        assert len(machines[0]["machine_name"]) > 0

    def test_save_machine_with_special_characters_in_name(self, temp_db_path):
        """Test saving machine with special characters in name."""
        client_data = {"quote_ref": "SPECIAL-NAME"}
        save_client_info(client_data, str(temp_db_path))

        machine_data = {
            "machines": [
                {
                    "machine_name": "Model X-5000 (High-Speed) & Premium",
                    "main_item": {"description": "Test", "item_price_numeric": 5000.00},
                    "add_ons": [],
                },
            ],
            "common_items": [],
        }

        result = save_machines_data("SPECIAL-NAME", machine_data, str(temp_db_path))
        assert result is True

        machines = load_machines_for_quote("SPECIAL-NAME", str(temp_db_path))
        assert machines[0]["machine_name"] == "Model X-5000 (High-Speed) & Premium"

    def test_machine_data_json_serialization(self, client_with_machines):
        """Test that complex machine data is properly JSON serialized."""
        temp_db_path, quote_ref = client_with_machines

        machines = load_machines_for_quote(quote_ref, str(temp_db_path))
        machine_data = machines[0]["machine_data"]

        # Should be valid dict (already parsed from JSON)
        assert isinstance(machine_data, dict)

        # Should contain expected structure
        assert "machine_name" in machine_data
        assert "main_item" in machine_data
        assert "add_ons" in machine_data
        assert "common_items" in machine_data

    def test_find_machine_with_empty_name(self, temp_db_path):
        """Test finding machine with empty search string."""
        results = find_machines_by_name("", str(temp_db_path))
        # Should return empty or all machines with % wildcard
        assert isinstance(results, list)

    def test_machines_are_ordered_by_id(self, temp_db_path, multi_machine_data):
        """Test that loaded machines maintain ID order."""
        client_data = {"quote_ref": "ORDER-TEST"}
        save_client_info(client_data, str(temp_db_path))

        save_machines_data("ORDER-TEST", multi_machine_data, str(temp_db_path))

        machines = load_machines_for_quote("ORDER-TEST", str(temp_db_path))
        # Should be in order by ID
        ids = [m["id"] for m in machines]
        assert ids == sorted(ids)
