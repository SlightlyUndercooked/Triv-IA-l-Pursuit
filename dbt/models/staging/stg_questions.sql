{{ config(materialized='table') }}

select
    question_id,
    category,
    type,
    difficulty,
    question,
    correct_answer,
    correct_letter
from read_parquet('../silver/questions.parquet')
