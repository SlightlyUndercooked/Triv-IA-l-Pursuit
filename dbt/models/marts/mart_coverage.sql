{{ config(materialized='table') }}

-- Couverture du run : combien de questions du silver ont au moins une réponse
with totals as (
    select count(*)::bigint as n_questions_total
    from {{ ref('stg_questions') }}
)

select
    a.model,
    t.n_questions_total,
    count(distinct a.question_id) as n_questions_answered,
    count(*) as n_answers,
    round(
        100.0 * count(distinct a.question_id) / nullif(t.n_questions_total, 0),
        2
    ) as question_coverage_pct,
    round(avg(cast(a.ai_correct as double)) * 100, 2) as accuracy_pct,
    round(avg(a.response_time), 3) as avg_response_time_s
from {{ ref('stg_answers') }} a
cross join totals t
group by a.model, t.n_questions_total
order by a.model
