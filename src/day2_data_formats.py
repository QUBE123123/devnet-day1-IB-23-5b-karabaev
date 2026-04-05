#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


ART_DIR = Path("artifacts/day2")
IN_PATH_DEFAULT = Path("artifacts/day1/response.json")

SUMMARY_SCHEMA_VERSION = "2.0"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 128), b""):
            h.update(chunk)
    return h.hexdigest()


def token_hash8(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def dump_json(obj, path: Path) -> str:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def dump_yaml(obj, path: Path) -> str:
    # важна детерминированность: sort_keys=True
    text = yaml.safe_dump(obj, allow_unicode=True, sort_keys=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return text


def dump_csv(model: dict, path: Path) -> str:
    # фиксированный порядок колонок
    cols = ["token", "token_hash8", "name", "group", "userId", "id", "title", "completed", "title_len"]
    row = {
        "token": model["student"]["token"],
        "token_hash8": model["student"]["token_hash8"],
        "name": model["student"]["name"],
        "group": model["student"]["group"],
        "userId": model["todo"]["userId"],
        "id": model["todo"]["id"],
        "title": model["todo"]["title"],
        "completed": str(model["todo"]["completed"]).lower(),  # true/false
        "title_len": model["computed"]["title_len"],
    }
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow(row)
    return path.read_text(encoding="utf-8")


def dump_xml(model: dict, path: Path) -> str:
    # фиксированный порядок элементов: student, todo, computed
    root = ET.Element("devnet_day2")

    s = ET.SubElement(root, "student")
    for k in ["token", "token_hash8", "name", "group"]:
        el = ET.SubElement(s, k)
        el.text = str(model["student"][k])

    t = ET.SubElement(root, "todo")
    for k in ["userId", "id", "title", "completed"]:
        el = ET.SubElement(t, k)
        el.text = str(model["todo"][k]).lower() if isinstance(model["todo"][k], bool) else str(model["todo"][k])

    c = ET.SubElement(root, "computed")
    el = ET.SubElement(c, "title_len")
    el.text = str(model["computed"]["title_len"])

    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        path.write_text(text + "\n", encoding="utf-8")
        text = text + "\n"
    return text


def build_model(todo: dict, token: str, name: str, group: str) -> dict:
    title = todo["title"]
    return {
        "student": {
            "token": token,
            "token_hash8": token_hash8(token),
            "name": name,
            "group": group,
        },
        "todo": {
            "userId": int(todo["userId"]),
            "id": int(todo["id"]),
            "title": str(title),
            "completed": bool(todo["completed"]),
        },
        "computed": {
            "title_len": len(title),
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(IN_PATH_DEFAULT))
    args = ap.parse_args()

    token = os.getenv("STUDENT_TOKEN", "").strip()
    name = os.getenv("STUDENT_NAME", "").strip()
    group = os.getenv("STUDENT_GROUP", "").strip()
    if not token or not name or not group:
        print("ERROR: set STUDENT_TOKEN, STUDENT_NAME, STUDENT_GROUP in environment (.env)")
        return 3

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}")
        return 2

    ART_DIR.mkdir(parents=True, exist_ok=True)

    todo = json.loads(in_path.read_text(encoding="utf-8"))
    model = build_model(todo, token, name, group)

    # outputs
    json_path = ART_DIR / "normalized.json"
    yaml_path = ART_DIR / "normalized.yaml"
    xml_path = ART_DIR / "normalized.xml"
    csv_path = ART_DIR / "normalized.csv"
    summary_path = ART_DIR / "summary.json"

    json_text = dump_json(model, json_path)
    yaml_text = dump_yaml(model, yaml_path)
    xml_text = dump_xml(model, xml_path)
    csv_text = dump_csv(model, csv_path)

    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "student": model["student"],
        "input": {
            "path": str(in_path).replace("\\", "/"),
            "sha256": sha256_file(in_path),
        },
        "outputs": {
            "normalized_json_sha256": sha256_text(json_text),
            "normalized_yaml_sha256": sha256_text(yaml_text),
            "normalized_xml_sha256": sha256_text(xml_text),
            "normalized_csv_sha256": sha256_text(csv_text),
        },
        "computed": model["computed"],
    }

    dump_json(summary, summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
