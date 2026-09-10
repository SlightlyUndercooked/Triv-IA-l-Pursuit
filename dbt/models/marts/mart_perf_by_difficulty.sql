{{ config(materialized='table') }}

select
    model,
    difficulty,
    count(*) as n_answers,
    round(avg(cast(ai_correct as double)) * 100, 2) as accuracy_pct,
    round(avg(response_time), 3) as avg_response_time_s
from {{ ref('stg_answers') }}
group by model, difficulty
order by model, difficulty
