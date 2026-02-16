from src.utils.machine_type import determine_machine_type, is_sortstar_machine


def test_sortstar_brand_detection() -> None:
    assert determine_machine_type("Bottle Unscrambler Model SortStar XL") == "sortstar"
    assert is_sortstar_machine("Bottle Unscrambler Model SortStar XL") is True


def test_unscrambler_without_competing_family_routes_to_sortstar() -> None:
    assert determine_machine_type("Bottle Unscrambler Model BX-200") == "sortstar"


def test_unscrambler_with_competing_primary_family_does_not_misroute() -> None:
    machine_name = "Monoblock Filler System with Unscrambler Infeed"
    assert determine_machine_type(machine_name) == "filling"
    assert is_sortstar_machine(machine_name) is False


def test_labeling_and_capping_detection() -> None:
    assert determine_machine_type("LabelStar Wraparound Labeling Machine") == "labeling"
    assert determine_machine_type("Rotary Capper High-Speed Unit") == "capping"


def test_unknown_machine_defaults_to_general() -> None:
    assert determine_machine_type("") == "general"
    assert determine_machine_type("Auxiliary Conveyor Module") == "general"


def test_case_insensitive_detection() -> None:
    assert determine_machine_type("SORTSTAR XL") == "sortstar"
    assert determine_machine_type("sortstar xl") == "sortstar"
    assert determine_machine_type("SortStar XL") == "sortstar"
    assert determine_machine_type("LABELSTAR System 1") == "labeling"


def test_hyphenated_and_underscored_variants() -> None:
    assert determine_machine_type("Sort-Star 18ft") == "sortstar"
    assert determine_machine_type("Sort_Star 18ft") == "sortstar"
    assert determine_machine_type("Bottle-Unscrambler BX-200") == "sortstar"
    assert determine_machine_type("bottle_unscrambler model 5") == "sortstar"
    assert determine_machine_type("Label-Star System 2") == "labeling"


def test_robosort_and_thunderstar() -> None:
    assert determine_machine_type("RoboSort 300") == "sortstar"
    assert determine_machine_type("Robo-Sort Advanced") == "sortstar"
    assert determine_machine_type("ThunderStar 500") == "sortstar"
    assert determine_machine_type("Thunder-Star Pro") == "sortstar"


def test_none_input() -> None:
    assert determine_machine_type(None) == "general"  # type: ignore[arg-type]


def test_filling_variants() -> None:
    assert determine_machine_type("Liquid Filling Machine") == "filling"
    assert determine_machine_type("Monoblock System") == "filling"
    assert determine_machine_type("Bottling Line 200") == "filling"

