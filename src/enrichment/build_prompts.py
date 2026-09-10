"""Build silver/prompts.parquet from questions + silver/prompt_templates.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = ROOT / "silver" / "questions.parquet"
DEFAULT_TEMPLATES = ROOT / "silver" / "prompt_templates.yaml"
DEFAULT_PROMPTS = ROOT / "silver" / "prompts.parquet"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def load_templates(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    required = {"mcq_multiple", "mcq_boolean", "open"}
    missing = required - set(data)
    if missing:
        raise SystemExit(f"Templates manquants dans {path}: {sorted(missing)}")
    return {k: str(v).strip() + "\n" for k, v in data.items() if k in required}


def format_options(shuffled_answers: list[str]) -> str:
    return "\n".join(f"{LETTERS[i]}. {answer}" for i, answer in enumerate(shuffled_answers))


def render_mcq(templates: dict[str, str], question: str, shuffled: list[str], qtype: str) -> str:
    key = "mcq_boolean" if qtype == "boolean" else "mcq_multiple"
    return templates[key].format(
        question=question,
        options=format_options(shuffled),
        last_letter=LETTERS[len(shuffled) - 1],
    )


def render_open(templates: dict[str, str], question: str) -> str:
    return templates["open"].format(question=question)


def build_prompts(questions: pd.DataFrame, templates: dict[str, str]) -> pd.DataFrame:
    rows: list[dict] = []

    for row in questions.itertuples(index=False):
        shuffled = list(row.all_answers_shuffled)
        rows.append(
            {
                "question_id": row.question_id,
                "prompt_variant": "mcq",
                "prompt_text": render_mcq(templates, row.question, shuffled, row.type),
            }
        )
        rows.append(
            {
                "question_id": row.question_id,
                "prompt_variant": "open",
                "prompt_text": render_open(templates, row.question),
            }
        )

    return pd.DataFrame.from_records(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Questions + templates → prompts.parquet")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_PROMPTS)
    args = parser.parse_args()

    if not args.questions.exists():
        raise SystemExit(f"Fichier questions introuvable: {args.questions}")
    if not args.templates.exists():
        raise SystemExit(f"Templates introuvables: {args.templates}")

    templates = load_templates(args.templates)
    questions = pd.read_parquet(args.questions)
    prompts = build_prompts(questions, templates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    prompts.to_parquet(args.out, index=False)
    print(f"Écrit {len(prompts)} prompts → {args.out}")


if __name__ == "__main__":
    main()
