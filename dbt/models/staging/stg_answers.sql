{{ config(materialized='table') }}

select
    question_id,
    prompt_variant,
    model,
    prompt_text,
    ai_answer,
    cast(ai_correct as boolean) as ai_correct,
    cast(response_time as double) as response_time,
    category,
    difficulty,
    type,
    correct_answer,
    correct_letter,
    error,
    generated_at
from read_parquet(
    '../silver/answers/*/answers.parquet',
    union_by_name = true
)
where error is null
   or cast(error as varchar) in ('', 'None', 'nan')
