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
    
    # 合法的
    valid_content = {
        "screening": ["case1", "case2"],
        "validation": ["case3", "case4"],
        "frozen": ["case5"]
    }
    s_file.write_text(yaml.dump(valid_content))
    manifest = SplitManifest.from_yaml(str(s_file))
    assert manifest.screening == ["case1", "case2"]
    
    # Screening/validation overlap is allowed (different seeds test stability)
    overlap_content = {
        "screening": ["case1", "case2"],
        "validation": ["case1", "case2", "case4"],
        "frozen": ["case5"]
    }
    s_file.write_text(yaml.dump(overlap_content))
    manifest2 = SplitManifest.from_yaml(str(s_file))
    assert manifest2.validation == ["case1", "case2", "case4"]

    # Frozen overlap is NOT allowed
    invalid_content = {
        "screening": ["case1", "case2"],
        "validation": ["case3", "case4"],
        "frozen": ["case2"]
    }
    s_file.write_text(yaml.dump(invalid_content))
    with pytest.raises(ValueError, match="overlap"):
        SplitManifest.from_yaml(str(s_file))

def test_protocol_config_defaults(tmp_path):
    p_file = tmp_path / "protocol.yaml"
    p_file.write_text(yaml.dump({"screening_n": 10}))
    
    config = ProtocolConfig.from_yaml(str(p_file))
    assert config.screening_n == 10
    assert config.validation_n == 12 # 默认值
