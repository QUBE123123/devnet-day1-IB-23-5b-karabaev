import json
import os
import subprocess
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
ART_DIR = ROOT / "artifacts" / "day1"
SUMMARY = ART_DIR / "summary.json"
SCHEMA = ROOT / "schemas" / "day1_summary.schema.json"


def test_day1_artifacts_and_schema():
    # 1) Запускаем скрипт (offline если response.json уже есть, иначе online)
    cmd = ["python", "src/day1_api_hello.py"]
    if (ART_DIR / "response.json").exists():
        cmd.append("--offline")

    env = os.environ.copy()
    assert env.get("STUDENT_TOKEN"), "STUDENT_TOKEN must be set"
    assert env.get("STUDENT_NAME"), "STUDENT_NAME must be set"
    assert env.get("STUDENT_GROUP"), "STUDENT_GROUP must be set"

    r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    assert r.returncode in (0, 2), f"Unexpected return code: {r.returncode}\n{r.stderr}"

    assert SUMMARY.exists(), "summary.json not found"
    assert SCHEMA.exists(), "schema json not found"

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    jsonschema.validate(instance=summary, schema=schema)

    # 2) Мини-проверки для предварительной оценки
    assert summary["api"]["status_code"] == 200
    assert isinstance(summary["api"]["validation_passed"], bool)
