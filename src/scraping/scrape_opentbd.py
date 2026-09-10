"""Scrape OpenTDB → bronze/questions_raw.csv."""

from __future__ import annotations

import csv
import html
import json
import logging
import os
import time
import urllib3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import requests

ROOT = Path(__file__).resolve().parents[2]
BRONZE_DIR = ROOT / "bronze"
OUTPUT_PATH = BRONZE_DIR / "questions_raw.csv"
PROGRESS_PATH = BRONZE_DIR / ".scrape_progress.json"

BASE_URL = "https://opentdb.com"
RATE_LIMIT_SECONDS = 5.1
AMOUNT_PER_REQUEST = 50

CSV_FIELDS = [
    "category",
    "type",
    "difficulty",
    "question",
    "correct_answer",
    "incorrect_answers",
    "scraped_at",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

session = requests.Session()
if os.environ.get("SCRAPE_INSECURE", "").lower() in {"1", "true", "yes"}:
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logger.warning("SCRAPE_INSECURE actif: vérification SSL désactivée")


def wait() -> None:
    time.sleep(RATE_LIMIT_SECONDS)


def get_categories() -> list[dict]:
    resp = session.get(f"{BASE_URL}/api_category.php", timeout=10)
    resp.raise_for_status()
    return resp.json()["trivia_categories"]


def request_session_token() -> str:
    resp = session.get(
        f"{BASE_URL}/api_token.php", params={"command": "request"}, timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    if data["response_code"] != 0:
        raise RuntimeError(f"Impossible d'obtenir un session token: {data}")
    return data["token"]


def fetch_questions(category_id: int, token: str, max_retries: int = 5) -> tuple[int, list[dict]]:
    params = {
        "amount": AMOUNT_PER_REQUEST,
        "category": category_id,
        "token": token,
        "encode": "url3986",
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(f"{BASE_URL}/api.php", params=params, timeout=15)
        except requests.exceptions.RequestException as e:
            wait_time = min(5 * attempt, 30)
            logger.warning(
                "Erreur réseau (%s), tentative %d/%d, pause %ds",
                e,
                attempt,
                max_retries,
                wait_time,
            )
            time.sleep(wait_time)
            continue

        if resp.status_code == 429:
            logger.warning("Rate limit atteint (429), pause supplémentaire de 5s")
            time.sleep(5)
            continue

        resp.raise_for_status()
        data = resp.json()
        return data["response_code"], data.get("results", [])

    raise RuntimeError(f"Échec après {max_retries} tentatives pour la catégorie {category_id}")


def decode_url3986(value: str) -> str:
    return html.unescape(unquote(value))


def normalize_question(raw: dict, category_name: str) -> dict:
    return {
        "category": category_name,
        "type": raw["type"],
        "difficulty": raw["difficulty"],
        "question": decode_url3986(raw["question"]),
        "correct_answer": decode_url3986(raw["correct_answer"]),
        "incorrect_answers": " | ".join(
            decode_url3986(a) for a in raw["incorrect_answers"]
        ),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def scrape_category(category_id: int, category_name: str) -> list[dict]:
    logger.info("Catégorie: %s (id=%s)", category_name, category_id)

    token = request_session_token()
    wait()

    rows: list[dict] = []

    while True:
        code, results = fetch_questions(category_id, token)

        if code == 0:
            rows.extend(normalize_question(raw, category_name) for raw in results)
            logger.info("  +%d questions (total catégorie: %d)", len(results), len(rows))
            wait()

        elif code == 4:
            logger.info("  Catégorie épuisée, %d questions au total", len(rows))
            break

        elif code == 1:
            logger.info("  Plus de questions disponibles pour cette catégorie")
            break

        else:
            logger.error("  Code de réponse inattendu (%s), on passe à la suite", code)
            break

    return rows


def load_completed_ids() -> set[int]:
    if not PROGRESS_PATH.exists():
        return set()
    return set(json.loads(PROGRESS_PATH.read_text()))


def mark_completed(category_id: int, completed: set[int]) -> None:
    completed.add(category_id)
    PROGRESS_PATH.write_text(json.dumps(sorted(completed)))


def main() -> None:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    categories = get_categories()
    logger.info("Nombre de catégories trouvées: %d", len(categories))

    completed = load_completed_ids()
    if completed:
        logger.info("Reprise: %d catégorie(s) déjà terminée(s), ignorées", len(completed))

    file_is_new = not OUTPUT_PATH.exists()
    grand_total = 0

    with open(OUTPUT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if file_is_new:
            writer.writeheader()

        for cat in categories:
            if cat["id"] in completed:
                continue
            rows = scrape_category(cat["id"], cat["name"])
            for row in rows:
                writer.writerow(row)
            f.flush()
            grand_total += len(rows)
            mark_completed(cat["id"], completed)

    logger.info("Terminé. %d nouvelles questions écrites dans %s", grand_total, OUTPUT_PATH)


if __name__ == "__main__":
    main()
