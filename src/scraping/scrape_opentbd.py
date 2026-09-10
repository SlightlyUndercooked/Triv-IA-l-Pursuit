import csv
import json
import time
import html
import logging
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote

import requests

BASE_URL = "https://opentdb.com"
RATE_LIMIT_SECONDS = 5.1
AMOUNT_PER_REQUEST = 50
OUTPUT_PATH = Path(__file__).parent / "questions_raw.csv"
PROGRESS_PATH = Path(__file__).parent / ".scrape_progress.json"

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


def wait():
    time.sleep(RATE_LIMIT_SECONDS)


def api_get(path: str, params: dict | None = None, max_retries: int = 5) -> dict:
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(f"{BASE_URL}{path}", params=params, timeout=15)
        except requests.exceptions.RequestException as e:
            wait_time = min(5 * attempt, 30)
            logger.warning(
                "Erreur réseau sur %s (%s), tentative %d/%d, pause %ds",
                path, e, attempt, max_retries, wait_time,
            )
            time.sleep(wait_time)
            continue

        if resp.status_code == 429:
            logger.warning("Rate limit atteint (429) sur %s, pause supplémentaire de 5s", path)
            time.sleep(5)
            continue

        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"Échec après {max_retries} tentatives sur {path}")


def get_categories() -> list[dict]:
    return api_get("/api_category.php")["trivia_categories"]


def request_session_token() -> str:
    data = api_get("/api_token.php", params={"command": "request"})
    if data["response_code"] != 0:
        raise RuntimeError(f"Impossible d'obtenir un session token: {data}")
    return data["token"]


def get_category_count(category_id: int) -> int:
    data = api_get("/api_count.php", params={"category": category_id})
    return data["category_question_count"]["total_question_count"]


def fetch_questions(category_id: int, token: str, amount: int) -> tuple[int, list[dict]]:
    params = {
        "amount": amount,
        "category": category_id,
        "token": token,
        "encode": "url3986",
    }
    data = api_get("/api.php", params=params)
    return data["response_code"], data.get("results", [])


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

    expected_total = get_category_count(category_id)
    wait()
    logger.info("  Total attendu d'après l'API: %d", expected_total)

    token = request_session_token()
    wait()

    rows = []
    amount = min(AMOUNT_PER_REQUEST, expected_total)

    while len(rows) < expected_total and amount > 0:
        code, results = fetch_questions(category_id, token, amount)

        if code == 0:
            rows.extend(normalize_question(raw, category_name) for raw in results)
            logger.info("  +%d questions (total catégorie: %d/%d)", len(results), len(rows), expected_total)
            wait()
            remaining = expected_total - len(rows)
            amount = min(AMOUNT_PER_REQUEST, remaining)

        elif code == 1:
            # le compte attendu peut être légèrement désynchronisé (questions
            # ajoutées/retirées côté API entre-temps) : on retente avec une
            # taille de paquet plus petite plutôt que d'abandonner
            if amount > 1:
                amount = max(amount // 2, 1)
                logger.info("  Code 1, on retente avec amount=%d", amount)
                wait()
                continue
            logger.info("  Plus de questions disponibles pour cette catégorie")
            break

        elif code == 4:
            logger.warning(
                "  Token épuisé à %d/%d questions (attendu vs obtenu désynchronisés)",
                len(rows), expected_total,
            )
            break

        else:
            logger.error("  Code de réponse inattendu (%s), on passe à la suite", code)
            break

    if len(rows) < expected_total:
        logger.warning(
            "  Catégorie incomplète: %d/%d questions récupérées", len(rows), expected_total
        )
    else:
        logger.info("  Catégorie complète: %d questions", len(rows))

    return rows


def load_completed_ids() -> set[int]:
    if not PROGRESS_PATH.exists():
        return set()
    return set(json.loads(PROGRESS_PATH.read_text()))


def mark_completed(category_id: int, completed: set[int]):
    completed.add(category_id)
    PROGRESS_PATH.write_text(json.dumps(sorted(completed)))


def main():
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