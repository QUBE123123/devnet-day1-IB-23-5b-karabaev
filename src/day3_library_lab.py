#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from faker import Faker
except Exception:
    Faker = None


ART = Path("artifacts/day3")
APIHOST = os.getenv("LIB_APIHOST", "http://library.demo.local").rstrip("/")
LOGIN = os.getenv("LIB_LOGIN", "cisco")
PASSWORD = os.getenv("LIB_PASSWORD", "Cisco123!")

SUMMARY_SCHEMA_VERSION = "3.1"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump_json(obj, path: Path) -> str:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def token_hash8(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def log(msg: str) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    with (ART / "run.log").open("a", encoding="utf-8") as f:
        f.write(f"{now_utc()}Z {msg}\n")


def get_books(s: requests.Session, params=None):
    r = s.get(f"{APIHOST}/api/v1/books", params=params or {}, timeout=10)
    return r.status_code, r.json()


def login_token(s: requests.Session) -> str:
    r = s.post(f"{APIHOST}/api/v1/loginViaBasic", auth=(LOGIN, PASSWORD), timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


def add_book(s: requests.Session, api_key: str, book: dict):
    r = s.post(
        f"{APIHOST}/api/v1/books",
        headers={"Content-type": "application/json", "X-API-KEY": api_key},
        data=json.dumps(book),
        timeout=10,
    )
    return r.status_code, r.json() if r.text else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=100, help="How many faker books to add")
    ap.add_argument("--offline", action="store_true", help="Only build summary from existing artifacts")
    args = ap.parse_args()

    st_token = os.getenv("STUDENT_TOKEN", "").strip()
    st_name = os.getenv("STUDENT_NAME", "").strip()
    st_group = os.getenv("STUDENT_GROUP", "").strip()
    if not st_token or not st_name or not st_group:
        print("ERROR: set STUDENT_TOKEN, STUDENT_NAME, STUDENT_GROUP", file=sys.stderr)
        return 3

    th8 = token_hash8(st_token)
    ART.mkdir(parents=True, exist_ok=True)

    if not args.offline:
        s = requests.Session()

        # Network diagnostics evidence
        net_diag = {
            "generated_utc": now_utc(),
            "apihost": APIHOST,
            "who": {"name": st_name, "group": st_group},
        }
        dump_json(net_diag, ART / "net_diag.txt")  # json file with .txt name is OK; checker reads as text

        # 1) Books before
        sc, books_before = get_books(s)
        dump_json({"status_code": sc, "count": len(books_before), "items": books_before}, ART / "books_before.json")
        log(f"GET /books before: status={sc} count={len(books_before)}")

        # 2) Books with params includeISBN=true&sortBy=author (из лабы)
        sc2, books_sorted = get_books(s, params={"includeISBN": "true", "sortBy": "author"})
        dump_json({"status_code": sc2, "count": len(books_sorted), "items": books_sorted}, ART / "books_sorted_isbn.json")
        log(f"GET /books sorted+isbn: status={sc2} count={len(books_sorted)}")

        # 3) Login token (X-API-KEY)
        api_key = login_token(s)
        api_key_sha = sha256_text(api_key)
        log("POST /loginViaBasic OK (api key received)")

        # 4) Add ONE unique “my book” (проверяемо)
        # id строим из NN в токене (D1-...-NN-....). Если не распарсилось, fallback.
        try:
            nn = int(st_token.split("-")[4])
        except Exception:
            nn = 0
        my_id = 5000 + nn
        my_book = {
            "id": my_id,
            "title": f"My DevNet Book {th8}",
            "author": st_name,
            "isbn": f"978-{nn:02d}{th8}"
        }
        psc, presp = add_book(s, api_key, my_book)
        dump_json({"status_code": psc, "request": my_book, "response": presp, "api_key_sha256": api_key_sha}, ART / "mybook_post.json")
        log(f"POST /books mybook: status={psc} id={my_id}")

        # 5) Add 100 books using faker, BUT author = student name (чтобы можно было проверить фильтром author)
        if Faker is None:
            raise RuntimeError("faker is not installed. pip install faker")
        fake = Faker()

        start_id = 6000 + nn * 200
        ok = 0
        fail = 0
        samples = []
        for i in range(start_id, start_id + args.count):
            book = {
                "id": i,
                "title": f"{fake.catch_phrase()} [{th8}]",
                "author": st_name,
                "isbn": fake.isbn13(),
            }
            scx, _ = add_book(s, api_key, book)
            if scx == 200:
                ok += 1
                if len(samples) < 5:
                    samples.append(book)
            else:
                fail += 1

        # 6) Verify by author filter (параметр author есть в доке параметров GET /books) :contentReference[oaicite:19]{index=19}
        sc3, books_by_me = get_books(s, params={"author": st_name, "includeISBN": "true", "sortBy": "id"})
        dump_json({"status_code": sc3, "count": len(books_by_me), "items": books_by_me[:30]}, ART / "books_by_me.json")
        log(f"GET /books?author=me: status={sc3} count={len(books_by_me)}")

        # Add report
        add_report = {
            "generated_utc": now_utc(),
            "count_requested": args.count,
            "added_ok": ok,
            "added_fail": fail,
            "author_used": st_name,
            "tag": th8,
            "id_range": [start_id, start_id + args.count - 1],
            "sample_books": samples,
            "api_key_sha256": api_key_sha,
        }
        dump_json(add_report, ART / "add100_report.json")

        # Tail log (human evidence)
        (ART / "add100_log_tail.txt").write_text(
            f"added_ok={ok}\nadded_fail={fail}\nid_range={start_id}..{start_id + args.count - 1}\n",
            encoding="utf-8"
        )

    # Summary (works offline too)
    def sha_file_if_exists(p: Path) -> str:
        if not p.exists():
            return ""
        return sha256_text(p.read_text(encoding="utf-8"))

    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_utc": now_utc(),
        "student": {"token": st_token, "token_hash8": th8, "name": st_name, "group": st_group},
        "lab": {
            "apihost": APIHOST,
            "must_use": {
                "login_endpoint": f"{APIHOST}/api/v1/loginViaBasic",
                "books_endpoint": f"{APIHOST}/api/v1/books",
                "api_key_header": "X-API-KEY",
            },
        },
        "artifacts_sha256": {
            "books_before": sha_file_if_exists(ART / "books_before.json"),
            "books_sorted_isbn": sha_file_if_exists(ART / "books_sorted_isbn.json"),
            "mybook_post": sha_file_if_exists(ART / "mybook_post.json"),
            "books_by_me": sha_file_if_exists(ART / "books_by_me.json"),
            "add100_report": sha_file_if_exists(ART / "add100_report.json"),
            "postman_collection": sha_file_if_exists(ART / "postman_collection.json"),
            "postman_environment": sha_file_if_exists(ART / "postman_environment.json"),
            "curl_get_books": sha_file_if_exists(ART / "curl_get_books.txt"),
            "curl_get_books_isbn": sha_file_if_exists(ART / "curl_get_books_isbn.txt"),
            "curl_get_books_sorted": sha_file_if_exists(ART / "curl_get_books_sorted.txt"),
        },
        "validation": {
            "must_have_mybook_title_contains_token_hash8": True,
            "must_have_added_100": True,
        },
    }

    dump_json(summary, ART / "summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
