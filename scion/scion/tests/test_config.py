import pytest
import os
import yaml
from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest

def test_problem_spec_loader(tmp_path):
    d = tmp_path / "problem"
    d.mkdir()
    p_file = d / "problem.yaml"
    content = {
        "name": "WarehouseDelivery",
        "operator_categories": ["order_level", "vehicle_level"],
        "operators_dir": "operators",
        "search_space": {
            "editable": ["operators/*.py"],
            "frozen": ["operators/base.py"],
            "import_whitelist": ["math", "random"]
        }
    }
    p_file.write_text(yaml.dump(content))

    spec = ProblemSpec.from_yaml(str(p_file))
    assert spec.name == "WarehouseDelivery"
    assert spec.search_space.import_whitelist == ["math", "random"]
    assert "order_level" in spec.operator_categories

def test_split_manifest_disjoint(tmp_path):
    s_file = tmp_path / "split.yaml"

    # Valid: frozen disjoint from all
    valid_content = {
        "version": "1.0",
        "screening": ["case1", "case2"],
        "validation": ["case3", "case4"],
        "frozen": ["case5"]
    }
    s_file.write_text(yaml.dump(valid_content))
    manifest = SplitManifest.from_yaml(str(s_file))
    assert manifest.screening == ["case1", "case2"]

    # Screening/validation overlap is allowed (different seeds test stability)
    overlap_content = {
        "version": "1.0",
        "screening": ["case1", "case2"],
        "validation": ["case1", "case2", "case4"],
        "frozen": ["case5"]
    }
    s_file.write_text(yaml.dump(overlap_content))
    manifest2 = SplitManifest.from_yaml(str(s_file))
    assert manifest2.validation == ["case1", "case2", "case4"]

    # Frozen overlap is NOT allowed
    invalid_content = {
        "version": "1.0",
        "screening": ["case1", "case2"],
        "validation": ["case3", "case4"],
        "frozen": ["case2"]
    }
    s_file.write_text(yaml.dump(invalid_content))
    with pytest.raises(ValueError, match="overlap"):
        SplitManifest.from_yaml(str(s_file))

def test_protocol_config_defaults():
    """Authoritative ProtocolConfig uses nested sub-configs with sensible defaults."""
    config = ProtocolConfig()
    # Screening defaults
    assert config.screening.n_cases_modify > 0
    assert config.screening.n_cases_create > 0
    assert config.screening.n_seeds > 0
    # Validation defaults
    assert config.validation.n_cases > 0
    assert config.validation.n_seeds > 0
    # Frozen defaults
    assert config.frozen.n_cases > 0
    assert config.frozen.max_uses_per_campaign > 0
    # Backward-compat properties
    assert 0.0 < config.screening_win_rate_threshold <= 1.0
    assert 0.0 < config.validation_win_rate_threshold <= 1.0
    assert config.min_practical_delta > 0.0

def test_protocol_config_from_yaml(tmp_path):
    """ProtocolConfig.from_yaml() loads the new nested format correctly."""
    p_file = tmp_path / "protocol.yaml"
    p_file.write_text(yaml.dump({
        "version": "test",
        "screening": {
            "n_cases_modify": 4,
            "n_cases_create": 8,
            "n_seeds": 2,
            "expand_to_modify": 8,
            "expand_to_create": 12,
        },
        "validation": {"n_cases": 5, "n_seeds": 3, "expand_to": 9},
        "frozen": {"n_cases": 3, "n_seeds": 3, "max_uses_per_campaign": 2},
        "gates": {
            "screening": {"win_rate_min": 0.6},
            "validation": {"win_rate_min": 0.7},
        }
    }))

    config = ProtocolConfig.from_yaml(str(p_file))
    assert config.screening.n_cases_modify == 4
    assert config.screening.n_cases_create == 8
    assert config.validation.n_cases == 5
    assert config.frozen.n_cases == 3
    assert config.frozen.max_uses_per_campaign == 2
    assert config.screening_win_rate_threshold == pytest.approx(0.6)
    assert config.validation_win_rate_threshold == pytest.approx(0.7)
