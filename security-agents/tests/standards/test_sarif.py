from __future__ import annotations

import copy
import json

import jsonschema
import pytest
from standards.catalog import manifest

from security_agents.standards import sarif, smoke

pytestmark = pytest.mark.standards


@pytest.fixture(scope="module")
def log(tmp_path_factory):
    paths = smoke.run(tmp_path_factory.mktemp("sarif"))
    return json.loads(paths["sarif"].read_text(encoding="utf-8"))


def test_sarif_output_validates_against_the_pinned_oasis_schema(log):
    jsonschema.Draft4Validator(sarif.schema()).validate(log)
    assert log["version"] == "2.1.0"
    assert log["$schema"] == sarif.SCHEMA_URI


def test_pinned_schema_records_its_source_and_stage():
    entry = manifest()["files"]["sarif-2.1.0.json"]
    urls = [item["url"] for item in entry["upstream"]]
    assert sarif.SCHEMA_URI in urls
    assert entry["version"] == "2.1.0"
    assert "OASIS" in entry["license"]


def test_result_carries_cwe_rule_cvss_and_location(log):
    run = log["runs"][0]
    result = run["results"][0]
    rule = run["tool"]["driver"]["rules"][result["ruleIndex"]]
    assert result["ruleId"] == rule["id"] == "CWE-639"
    assert result["level"] == "warning"
    cvss = result["properties"]["severity"]["cvss_v31"]
    assert cvss["vector"] == "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
    assert cvss["score_kind"].startswith("CVSS v3.1 base score only")
    assert rule["properties"]["security-severity"] == "6.5"
    assert rule["properties"]["owasp_api_security_top_10"]["mapping_kind"] == "project mapping"
    region = result["locations"][0]["physicalLocation"]["region"]
    assert region["startLine"] >= 1
    assert run["properties"]["run_mode"] == "replay"


@pytest.mark.negative
@pytest.mark.parametrize(
    "mutate",
    [
        lambda log: log.update(version="2.0.0"),
        lambda log: log["runs"][0]["results"][0].update(level="critical"),
        lambda log: log["runs"][0]["tool"]["driver"].pop("name"),
        lambda log: log["runs"][0]["results"][0].pop("message"),
    ],
)
def test_schema_rejects_invalid_logs(log, mutate):
    broken = copy.deepcopy(log)
    mutate(broken)
    with pytest.raises(jsonschema.ValidationError):
        sarif.validate(broken)
