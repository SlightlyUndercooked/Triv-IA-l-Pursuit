#!/usr/bin/env python3
"""Call LM Studio on silver/prompts.parquet → silver/answers/<model>/answers.parquet."""

from __future__ import annotations

import argparse
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = ROOT / "silver" / "questions.parquet"
DEFAULT_PROMPTS = ROOT / "silver" / "prompts.parquet"
DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-nano-4b"
DEFAULT_SLUG = "nemotron"

TRAILING_PUNCT_RE = re.compile(r"[\s\.\,\;\:\!\?\"'`]+$")
ANSWER_LETTER_RE = re.compile(
    r"(?:final\s+)?(?:answer(?:\s+letter)?|option|choice|thus|therefore|so)\s*(?:is|:)?\s*([A-Da-d])\b",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    text = TRAILING_PUNCT_RE.sub("", text)
    return " ".join(text.split())


def extract_mcq_letter(raw: str) -> str:
    text = str(raw).strip()
    if not text:
        return ""
    if len(text) <= 5:
        first = text[0].upper()
        return first if first.isalpha() else ""
    matches = ANSWER_LETTER_RE.findall(text)
    if matches:
        return matches[-1].upper()
    for line in reversed(text.splitlines()):
        line = line.strip().rstrip(".")
        if len(line) == 1 and line.isalpha():
            return line.upper()
    return ""


def score_answer(
    prompt_variant: str,
    ai_answer: str,
    correct_letter: str,
    correct_answer: str,
) -> bool:
    if prompt_variant == "mcq":
        return extract_mcq_letter(ai_answer) == str(correct_letter).upper()
    return normalize_text(ai_answer) == normalize_text(correct_answer)


def list_models(base_url: str, timeout: float = 10.0) -> list[str]:
    resp = requests.get(f"{base_url.rstrip('/')}/models", timeout=timeout)
    resp.raise_for_status()
    return [m["id"] for m in resp.json().get("data", [])]


def resolve_model(base_url: str, requested: str) -> str:
    ids = list_models(base_url)
    if not ids:
        raise SystemExit(
            f"Aucun modèle chargé sur {base_url}. "
            "Lancer `lms server start` puis charger Nemotron dans LM Studio."
        )
    if requested in ids:
        return requested
    lowered = {m.lower(): m for m in ids}
    if requested.lower() in lowered:
        return lowered[requested.lower()]
    needle = requested.lower().replace("_", "-")
    for mid in ids:
        if needle in mid.lower().replace("_", "-"):
            return mid
    print(f"Modèle demandé introuvable ({requested!r}), fallback → {ids[0]!r}")
    return ids[0]


def pick_answer(message: dict) -> str:
    """Nemotron may fill reasoning_content first; prefer final content."""
    content = str(message.get("content") or "").strip()
    if content:
        return content
    reasoning = str(message.get("reasoning_content") or "").strip()
    if not reasoning:
        return ""
    matches = ANSWER_LETTER_RE.findall(reasoning)
    if matches:
        return matches[-1].upper()
    for line in reversed(reasoning.splitlines()):
        line = line.strip().rstrip(".")
        if len(line) == 1 and line.isalpha():
            return line.upper()
        if line.lower().startswith("answer"):
            return line
    return reasoning[-200:].strip()


def chat_completion(
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> tuple[str, float]:
    started = time.perf_counter()
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Limite le "thinking" Nemotron pour laisser de la place à la réponse finale
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=timeout,
    )
    elapsed = time.perf_counter() - started
    resp.raise_for_status()
    data = resp.json()
    return pick_answer(data["choices"][0]["message"]), elapsed


def chat_completion_with_retries(
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
    retries: int,
    backoff: float,
) -> tuple[str, float]:
    """Retry transient LM Studio 400/5xx / connection blips."""
    attempts = max(1, retries + 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return chat_completion(
                base_url, model, prompt, temperature, max_tokens, timeout
            )
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            wait = backoff * (2 ** (attempt - 1))
            print(f"  retry {attempt}/{retries} après {wait:.1f}s ({exc})")
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def _has_error(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "") & (series.astype(str) != "None")


def load_done_keys(out_path: Path) -> set[tuple[str, str]]:
    """Clés déjà OK (les lignes en erreur seront rejouées)."""
    if not out_path.exists():
        return set()
    existing = pd.read_parquet(out_path)
    if existing.empty:
        return set()
    ok = existing[~_has_error(existing["error"])] if "error" in existing.columns else existing
    if ok.empty:
        return set()
    return set(zip(ok["question_id"].astype(str), ok["prompt_variant"].astype(str)))


def append_records(out_path: Path, records: list[dict]) -> None:
    if not records:
        return
    chunk = pd.DataFrame.from_records(records)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        prev = pd.read_parquet(out_path)
        keys = set(zip(chunk["question_id"].astype(str), chunk["prompt_variant"].astype(str)))
        mask = prev.apply(
            lambda r: (str(r.question_id), str(r.prompt_variant)) not in keys, axis=1
        )
        out = pd.concat([prev[mask], chunk], ignore_index=True)
    else:
        out = chunk
    out.to_parquet(out_path, index=False)


def build_worklist(
    prompts: pd.DataFrame,
    questions: pd.DataFrame,
    done: set[tuple[str, str]],
    limit: int | None,
    variants: set[str] | None,
) -> pd.DataFrame:
    q = questions[
        ["question_id", "correct_answer", "correct_letter", "type", "category", "difficulty"]
    ].copy()
    work = prompts.merge(q, on="question_id", how="inner")
    if variants:
        work = work[work["prompt_variant"].isin(variants)]
    work = work[~work.apply(lambda r: (str(r.question_id), str(r.prompt_variant)) in done, axis=1)]
    work = work.reset_index(drop=True)
    if limit is not None:
        work = work.head(limit)
    return work


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompts → réponses LM Studio (silver/answers)")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="ID modèle LM Studio / alias")
    parser.add_argument("--slug", default=DEFAULT_SLUG, help="Dossier sous silver/answers/")
    parser.add_argument("--out", type=Path, default=None, help="Parquet de sortie (optionnel)")
    parser.add_argument("--limit", type=int, default=None, help="Nombre max de prompts à traiter")
    parser.add_argument("--variants", nargs="+", choices=["mcq", "open"], default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Budget tokens (Nemotron consomme du reasoning avant content)",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=3, help="Retries après erreur HTTP/API")
    parser.add_argument("--backoff", type=float, default=1.5, help="Backoff initial (s), x2 à chaque essai")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=0.0, help="Pause entre appels (s)")
    args = parser.parse_args()

    if not args.questions.exists():
        raise SystemExit(f"Questions introuvables: {args.questions}")
    if not args.prompts.exists():
        raise SystemExit(f"Prompts introuvables: {args.prompts}")

    out_path = args.out or (ROOT / "silver" / "answers" / args.slug / "answers.parquet")
    questions = pd.read_parquet(args.questions)
    prompts = pd.read_parquet(args.prompts)
    done = load_done_keys(out_path)
    variants = set(args.variants) if args.variants else None
    work = build_worklist(prompts, questions, done, args.limit, variants)

    print(f"Déjà faits: {len(done)} | À faire: {len(work)} | Sortie: {out_path}")
    if work.empty:
        print("Rien à faire.")
        return

    model_id = resolve_model(args.base_url, args.model)
    print(f"Modèle: {model_id} @ {args.base_url}")

    buffer: list[dict] = []
    errors = 0
    for i, row in enumerate(work.itertuples(index=False), start=1):
        try:
            ai_answer, response_time = chat_completion_with_retries(
                args.base_url,
                model_id,
                row.prompt_text,
                args.temperature,
                args.max_tokens,
                args.timeout,
                args.retries,
                args.backoff,
            )
            ai_correct = score_answer(
                row.prompt_variant,
                ai_answer,
                row.correct_letter,
                row.correct_answer,
            )
            err = None
        except Exception as exc:  # noqa: BLE001 — on journalise et on continue
            ai_answer, response_time, ai_correct = "", float("nan"), False
            err = str(exc)
            errors += 1
            print(f"[{i}/{len(work)}] ERREUR {row.question_id}/{row.prompt_variant}: {exc}")

        buffer.append(
            {
                "question_id": row.question_id,
                "prompt_variant": row.prompt_variant,
                "model": model_id,
                "prompt_text": row.prompt_text,
                "ai_answer": ai_answer,
                "ai_correct": bool(ai_correct) if err is None else False,
                "response_time": response_time,
                "category": row.category,
                "difficulty": row.difficulty,
                "type": row.type,
                "correct_answer": row.correct_answer,
                "correct_letter": row.correct_letter,
                "error": err,
                "generated_at": utc_now(),
            }
        )

        if err is None:
            mark = "OK" if buffer[-1]["ai_correct"] else "KO"
            print(
                f"[{i}/{len(work)}] {row.prompt_variant} {mark} "
                f"{response_time:.2f}s → {ai_answer!r}"
            )

        if len(buffer) >= args.checkpoint_every:
            append_records(out_path, buffer)
            buffer.clear()

        if args.sleep > 0:
            time.sleep(args.sleep)

    append_records(out_path, buffer)
    total = len(pd.read_parquet(out_path)) if out_path.exists() else 0
    print(f"Terminé. Lignes dans {out_path}: {total} (erreurs ce run: {errors})")


if __name__ == "__main__":
    main()
