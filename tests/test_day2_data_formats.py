import json
import os
import subprocess
from pathlib import Path

import jsonschema
import yaml
import xml.etree.ElementTree as ET
import csv


ROOT = Path(__file__).resolve().parents[1]
DAY2 = ROOT / "artifacts" / "day2"
SCHEMA = ROOT / "schemas" / "day2_summary.schema.json"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_day2_generate_and_validate():
    env = os.environ.copy()
    assert env.get("STUDENT_TOKEN"), "STUDENT_TOKEN must be set"
    assert env.get("STUDENT_NAME"), "STUDENT_NAME must be set"
    assert env.get("STUDENT_GROUP"), "STUDENT_GROUP must be set"

    # Run generator
    r = subprocess.run(
        ["python", "src/day2_data_formats.py", "--input", "artifacts/day1/response.json"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True
    )
    assert r.returncode == 0, f"script failed: {r.stderr}"

    # Required outputs
    for fn in ["normalized.json", "normalized.yaml", "normalized.xml", "normalized.csv", "summary.json"]:
        assert (DAY2 / fn).exists(), f"missing {fn}"

    # Schema validation
    summary = load_json(DAY2 / "summary.json")
    schema = load_json(SCHEMA)
    jsonschema.validate(instance=summary, schema=schema)

    # Cross-format equivalence: JSON vs YAML
    model_json = load_json(DAY2 / "normalized.json")
    model_yaml = yaml.safe_load((DAY2 / "normalized.yaml").read_text(encoding="utf-8"))
    assert model_json == model_yaml

    # XML parse basic checks
    tree = ET.parse(DAY2 / "normalized.xml")
    root = tree.getroot()
    assert root.tag == "devnet_day2"
    token_hash8 = root.findtext("./student/token_hash8")
    assert token_hash8 and len(token_hash8) == 8

    # CSV header check
    with (DAY2 / "normalized.csv").open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert "token_hash8" in rows[0]
    assert rows[0]["completed"] in ("true", "false")
