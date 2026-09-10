"""Build silver/questions.parquet from bronze/questions_raw.csv."""

from __future__ import annotations

import argparse
import hashlib
import html
import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRONZE = ROOT / "bronze" / "questions_raw.csv"
DEFAULT_SILVER = ROOT / "silver" / "questions.parquet"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_question_id(category: str, question: str, correct_answer: str) -> str:
    payload = f"{category}|{question}|{correct_answer}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def clean_text(value: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = html.unescape(str(value)).strip()
    return " ".join(text.split())


def parse_incorrect_answers(raw: str) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    parts = [clean_text(p) for p in str(raw).split("|")]
    return [p for p in parts if p]


def shuffle_answers(question_id: str, correct: str, incorrect: list[str]) -> list[str]:
    answers = [correct, *incorrect]
    rng = random.Random(question_id)
    rng.shuffle(answers)
    return answers


def correct_letter_for(shuffled_answers: list[str], correct_answer: str) -> str:
    try:
        idx = shuffled_answers.index(correct_answer)
    except ValueError:
        lowered = [a.casefold() for a in shuffled_answers]
        idx = lowered.index(correct_answer.casefold())
    return LETTERS[idx]


def build_questions(bronze_path: Path) -> pd.DataFrame:
    df = pd.read_csv(bronze_path)

    records: list[dict] = []
    for row in df.itertuples(index=False):
        category = clean_text(row.category)
        question = clean_text(row.question)
        correct = clean_text(row.correct_answer)
        incorrect = parse_incorrect_answers(row.incorrect_answers)
        qid = make_question_id(category, question, correct)
        shuffled = shuffle_answers(qid, correct, incorrect)

        records.append(
            {
                "question_id": qid,
                "category": category,
                "type": clean_text(row.type),
                "difficulty": clean_text(row.difficulty),
                "question": question,
                "correct_answer": correct,
                "incorrect_answers": incorrect,
                "all_answers_shuffled": shuffled,
                "correct_letter": correct_letter_for(shuffled, correct),
            }
        )

    out = pd.DataFrame.from_records(records)
    out = out.drop_duplicates(subset=["question_id"], keep="first").reset_index(drop=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Bronze CSV → silver/questions.parquet")
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE)
    parser.add_argument("--out", type=Path, default=DEFAULT_SILVER)
    args = parser.parse_args()

    if not args.bronze.exists():
        raise SystemExit(f"Fichier bronze introuvable: {args.bronze}")

    questions = build_questions(args.bronze)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    questions.to_parquet(args.out, index=False)
    print(f"Écrit {len(questions)} questions → {args.out}")


if __name__ == "__main__":
    main()
