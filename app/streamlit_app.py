"""Visualisation des marts gold — Triv'IA'l Pursuit."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_DB = REPO_ROOT / "gold" / "benchmark.duckdb"

# Palette claire : encre marine + accent aqua (pas de néon, pas de crème/terracotta)
C = {
    "ink": "#0F172A",
    "soft": "#475569",
    "line": "#E2E8F0",
    "bg": "#F1F5F9",
    "white": "#FFFFFF",
    "accent": "#0D9488",
    "accent2": "#0369A1",
    "warn": "#C2410C",
    "good": "#059669",
}

SERIES = [C["accent"], C["accent2"], "#0F766E", "#1E3A5F", "#CA8A04", "#64748B"]

DIFFICULTY_ORDER = ["easy", "medium", "hard"]
DIFFICULTY_FR = {"easy": "Facile", "medium": "Moyen", "hard": "Difficile"}
PROMPT_FR = {"mcq": "QCM", "open": "Ouverte"}

PAGES = [
    "Vue d'ensemble",
    "Prompts",
    "Catégories",
    "Difficulté",
    "Couverture",
]

st.set_page_config(
    page_title="Triv'IA'l Pursuit",
    page_icon="T",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def css() -> None:
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Sora:wght@600;700;800&display=swap');

html, body, [class*="css"], .stApp, p, label, span, div {{
  font-family: "Figtree", sans-serif !important;
}}

.stApp {{
  background:
    radial-gradient(ellipse 80% 50% at 0% 0%, #dbeafe 0%, transparent 55%),
    radial-gradient(ellipse 60% 40% at 100% 0%, #ccfbf1 0%, transparent 50%),
    {C["bg"]};
  color: {C["ink"]};
}}

#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ display: none; }}
.block-container {{
  padding-top: 1.5rem !important;
  padding-bottom: 3rem !important;
  max-width: 1180px;
}}

/* Brand strip */
.brand {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1.1rem;
  border-bottom: 2px solid {C["ink"]};
}}
.brand h1 {{
  font-family: "Sora", sans-serif !important;
  font-weight: 800 !important;
  font-size: clamp(1.6rem, 2.8vw, 2.15rem) !important;
  letter-spacing: -0.04em;
  color: {C["ink"]} !important;
  margin: 0 !important;
  line-height: 1 !important;
}}
.brand h1 em {{
  font-style: normal;
  color: {C["accent"]};
}}
.brand p {{
  margin: 0 !important;
  color: {C["soft"]} !important;
  font-size: 0.95rem !important;
  max-width: 22rem;
  text-align: right;
  line-height: 1.35;
}}

/* Metrics */
.metrics {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin: 0.25rem 0 1.35rem 0;
}}
@media (max-width: 900px) {{
  .metrics {{ grid-template-columns: 1fr 1fr; }}
  .brand {{ flex-direction: column; align-items: flex-start; }}
  .brand p {{ text-align: left; }}
}}
.metric {{
  background: {C["white"]};
  border: 1px solid {C["line"]};
  border-radius: 12px;
  padding: 1rem 1.05rem 0.95rem;
}}
.metric .lbl {{
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {C["soft"]};
  margin-bottom: 0.35rem;
}}
.metric .val {{
  font-family: "Sora", sans-serif !important;
  font-weight: 700;
  font-size: 1.65rem;
  letter-spacing: -0.03em;
  color: {C["ink"]};
  line-height: 1.1;
}}
.metric .hint {{
  margin-top: 0.3rem;
  font-size: 0.8rem;
  color: {C["soft"]};
}}
.metric.hi .val {{ color: {C["accent"]}; }}
.metric.lo .val {{ color: {C["warn"]}; }}

.panel-title {{
  font-family: "Sora", sans-serif !important;
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em;
  color: {C["ink"]} !important;
  margin: 0.4rem 0 0.1rem 0 !important;
}}
.panel-sub {{
  color: {C["soft"]} !important;
  font-size: 0.88rem !important;
  margin: 0 0 0.55rem 0 !important;
}}

/* Nav */
div[role="radiogroup"] {{
  gap: 0 !important;
  border-bottom: 1px solid {C["line"]} !important;
  margin: 0.4rem 0 1.15rem 0 !important;
}}
div[role="radiogroup"] label {{
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  padding: 0.55rem 0.95rem !important;
  color: {C["soft"]} !important;
  font-weight: 600 !important;
  margin-bottom: -1px !important;
}}
div[role="radiogroup"] label:has(input:checked) {{
  background: transparent !important;
  border-bottom-color: {C["accent"]} !important;
  color: {C["ink"]} !important;
}}
div[role="radiogroup"] label:has(input:checked) p,
div[role="radiogroup"] label:has(input:checked) span {{
  color: {C["ink"]} !important;
}}
div[role="radiogroup"] label p {{
  color: inherit !important;
}}

[data-testid="stWidgetLabel"] p {{
  color: {C["soft"]} !important;
  font-weight: 600 !important;
  font-size: 0.8rem !important;
}}

.stButton > button {{
  background: {C["ink"]} !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}}
.stButton > button:hover {{
  background: {C["accent"]} !important;
  color: #fff !important;
}}

div[data-testid="stDataFrame"] {{
  border: 1px solid {C["line"]};
  border-radius: 12px;
  overflow: hidden;
}}

[data-testid="stSidebar"] {{ display: none !important; }}
</style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_marts(mtime: float) -> dict[str, pd.DataFrame]:
    del mtime
    con = duckdb.connect(str(GOLD_DB), read_only=True)
    try:
        tables = [
            "mart_perf_by_model",
            "mart_perf_by_prompt",
            "mart_perf_by_category",
            "mart_perf_by_difficulty",
            "mart_coverage",
        ]
        return {t: con.execute(f"select * from {t}").fetchdf() for t in tables}
    finally:
        con.close()


def short(model: str) -> str:
    return model.split("/")[-1] if isinstance(model, str) else str(model)


def keep(df: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    if df.empty or not models or "model" not in df.columns:
        return df
    return df[df["model"].isin(models)].copy()


def fig_style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Figtree, sans-serif", color=C["ink"], size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=C["soft"], size=12),
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Figtree",
            font_color=C["ink"],
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=C["line"],
        tickfont=dict(color=C["soft"]),
        title_font=dict(color=C["soft"], size=12),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#E8EEF4",
        zeroline=False,
        linecolor=C["line"],
        tickfont=dict(color=C["soft"]),
        title_font=dict(color=C["soft"], size=12),
    )
    return fig


def metric(label: str, value: str, hint: str = "", tone: str = "") -> str:
    hint_html = f'<div class="hint">{hint}</div>' if hint else ""
    return (
        f'<div class="metric {tone}">'
        f'<div class="lbl">{label}</div>'
        f'<div class="val">{value}</div>'
        f"{hint_html}</div>"
    )


def metrics_row(cards: list[str]) -> None:
    st.markdown(f'<div class="metrics">{"".join(cards)}</div>', unsafe_allow_html=True)


def section(title: str, subtitle: str = "") -> None:
    sub = f'<p class="panel-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<p class="panel-title">{title}</p>{sub}',
        unsafe_allow_html=True,
    )


def pct(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{float(x):.1f}%"


def num(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{int(round(float(x))):,}".replace(",", "\u202f")


def sec(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{float(x):.2f} s"


# --- Pages -----------------------------------------------------------------


def page_overview(by_model: pd.DataFrame, coverage: pd.DataFrame, by_prompt: pd.DataFrame) -> None:
    if by_model.empty:
        st.info("Aucune donnée. Lance `dbt run --profiles-dir .` depuis `dbt/`.")
        return

    best = by_model.sort_values("accuracy_pct", ascending=False).iloc[0]
    avg_cov = float(coverage["question_coverage_pct"].mean()) if not coverage.empty else None

    metrics_row(
        [
            metric("Meilleure accuracy", pct(best["accuracy_pct"]), short(best["model"]), "hi"),
            metric("Réponses", num(by_model["n_answers"].sum()), f"{by_model['model'].nunique()} modèle(s)"),
            metric(
                "Couverture",
                pct(avg_cov),
                "questions silver",
                "lo" if avg_cov is not None and avg_cov < 50 else "",
            ),
            metric("Latence médiane", sec(best.get("median_response_time_s")), "meilleur modèle"),
        ]
    )

    left, right = st.columns(2, gap="medium")

    with left:
        section("Accuracy par modèle", "Classement global sur le gold.")
        d = by_model.copy()
        d["modèle"] = d["model"].map(short)
        d = d.sort_values("accuracy_pct")
        fig = px.bar(
            d,
            x="accuracy_pct",
            y="modèle",
            orientation="h",
            text="accuracy_pct",
            color_discrete_sequence=[C["accent"]],
            labels={"accuracy_pct": "Accuracy (%)", "modèle": ""},
        )
        fig.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
            textfont=dict(color=C["ink"], size=12),
            marker_line_width=0,
            hovertemplate="<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
        )
        fig.update_xaxes(range=[0, min(100, float(d["accuracy_pct"].max()) + 15)])
        st.plotly_chart(fig_style(fig, max(260, 80 * len(d))), width="stretch")

    with right:
        section("QCM vs ouverte", "Accuracy selon le type de prompt.")
        if by_prompt.empty:
            st.caption("Pas de données prompt.")
        else:
            p = by_prompt.copy()
            p["modèle"] = p["model"].map(short)
            p["prompt"] = p["prompt_variant"].map(lambda v: PROMPT_FR.get(v, v))
            fig = px.bar(
                p,
                x="modèle",
                y="accuracy_pct",
                color="prompt",
                barmode="group",
                color_discrete_sequence=[C["accent"], C["accent2"]],
                labels={"accuracy_pct": "Accuracy (%)", "modèle": "", "prompt": ""},
            )
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig_style(fig), width="stretch")

    table = by_model.copy()
    table["model"] = table["model"].map(short)
    table = table.rename(
        columns={
            "model": "Modèle",
            "n_answers": "Réponses",
            "accuracy_pct": "Accuracy %",
            "avg_response_time_s": "Latence moy. (s)",
            "median_response_time_s": "Latence médiane (s)",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)


def page_prompts(by_prompt: pd.DataFrame) -> None:
    if by_prompt.empty:
        st.info("Pas de données prompt.")
        return

    d = by_prompt.copy()
    d["modèle"] = d["model"].map(short)
    d["prompt"] = d["prompt_variant"].map(lambda v: PROMPT_FR.get(v, v))

    pivot = d.pivot_table(index="modèle", columns="prompt_variant", values="accuracy_pct")
    gap = None
    if {"mcq", "open"}.issubset(pivot.columns):
        gap = float((pivot["mcq"] - pivot["open"]).mean())

    metrics_row(
        [
            metric("Écart QCM − ouverte", pct(gap) if gap is not None else "—", "points de %"),
            metric(
                "Meilleur QCM",
                pct(d.loc[d["prompt_variant"] == "mcq", "accuracy_pct"].max()),
                tone="hi",
            ),
            metric(
                "Meilleure ouverte",
                pct(d.loc[d["prompt_variant"] == "open", "accuracy_pct"].max()),
            ),
            metric("Combinaisons", num(len(d)), "modèle × prompt"),
        ]
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        section("Accuracy", "Comparaison par variante de prompt.")
        fig = px.bar(
            d,
            x="modèle",
            y="accuracy_pct",
            color="prompt",
            barmode="group",
            color_discrete_sequence=[C["accent"], C["accent2"]],
            labels={"accuracy_pct": "Accuracy (%)", "modèle": "", "prompt": ""},
        )
        st.plotly_chart(fig_style(fig), width="stretch")
    with c2:
        section("Accuracy vs latence", "Taille = volume de réponses.")
        fig = px.scatter(
            d,
            x="avg_response_time_s",
            y="accuracy_pct",
            color="prompt",
            size="n_answers",
            hover_name="modèle",
            color_discrete_sequence=[C["accent"], C["accent2"]],
            labels={
                "avg_response_time_s": "Latence (s)",
                "accuracy_pct": "Accuracy (%)",
                "prompt": "",
                "n_answers": "Réponses",
            },
        )
        st.plotly_chart(fig_style(fig), width="stretch")

    show = d[["modèle", "prompt", "n_answers", "accuracy_pct", "avg_response_time_s"]].rename(
        columns={
            "modèle": "Modèle",
            "prompt": "Prompt",
            "n_answers": "Réponses",
            "accuracy_pct": "Accuracy %",
            "avg_response_time_s": "Latence moy. (s)",
        }
    )
    st.dataframe(show, width="stretch", hide_index=True)


def page_categories(by_category: pd.DataFrame) -> None:
    if by_category.empty:
        st.info("Pas de données catégorie.")
        return

    d = by_category.copy()
    d["modèle"] = d["model"].map(short)
    models = sorted(d["modèle"].unique())
    chosen = st.selectbox("Modèle", models, label_visibility="collapsed", key="cat_m")
    sub = d[d["modèle"] == chosen].sort_values("accuracy_pct")

    metrics_row(
        [
            metric("Catégories", num(len(sub))),
            metric("Meilleure", pct(sub.iloc[-1]["accuracy_pct"]), sub.iloc[-1]["category"], "hi"),
            metric("Plus faible", pct(sub.iloc[0]["accuracy_pct"]), sub.iloc[0]["category"], "lo"),
            metric("Réponses", num(sub["n_answers"].sum())),
        ]
    )

    section(f"Accuracy — {chosen}", "Du plus faible au plus fort.")
    fig = px.bar(
        sub,
        x="accuracy_pct",
        y="category",
        orientation="h",
        color="accuracy_pct",
        color_continuous_scale=["#FECACA", "#FDE68A", "#5EEAD4", "#0D9488"],
        range_color=[0, 100],
        labels={"accuracy_pct": "Accuracy (%)", "category": ""},
        hover_data={"n_answers": True, "avg_response_time_s": ":.2f"},
    )
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_style(fig, max(320, 26 * len(sub) + 60)), width="stretch")

    if d["modèle"].nunique() > 1:
        section("Comparaison multi-modèles", "Top catégories par volume.")
        top = d.groupby("category")["n_answers"].sum().nlargest(12).index
        heat = d[d["category"].isin(top)]
        fig = px.density_heatmap(
            heat,
            x="modèle",
            y="category",
            z="accuracy_pct",
            histfunc="avg",
            color_continuous_scale=["#FEE2E2", "#FDE68A", "#99F6E4", "#0D9488"],
            labels={"modèle": "", "category": "", "accuracy_pct": "Accuracy %"},
        )
        st.plotly_chart(fig_style(fig, 400), width="stretch")


def page_difficulty(by_difficulty: pd.DataFrame) -> None:
    if by_difficulty.empty:
        st.info("Pas de données difficulté.")
        return

    d = by_difficulty.copy()
    d["modèle"] = d["model"].map(short)
    d["niveau"] = d["difficulty"].map(lambda x: DIFFICULTY_FR.get(x, x))
    d["ord"] = d["difficulty"].map({k: i for i, k in enumerate(DIFFICULTY_ORDER)})
    d = d.sort_values(["modèle", "ord"])
    order = [DIFFICULTY_FR[x] for x in DIFFICULTY_ORDER]

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        section("Accuracy", "Selon le niveau de difficulté.")
        fig = px.bar(
            d,
            x="niveau",
            y="accuracy_pct",
            color="modèle",
            barmode="group",
            category_orders={"niveau": order},
            color_discrete_sequence=SERIES,
            labels={"accuracy_pct": "Accuracy (%)", "niveau": "", "modèle": ""},
        )
        st.plotly_chart(fig_style(fig), width="stretch")
    with c2:
        section("Latence", "Temps de réponse moyen.")
        fig = px.line(
            d,
            x="niveau",
            y="avg_response_time_s",
            color="modèle",
            markers=True,
            category_orders={"niveau": order},
            color_discrete_sequence=SERIES,
            labels={"avg_response_time_s": "Latence (s)", "niveau": "", "modèle": ""},
        )
        st.plotly_chart(fig_style(fig), width="stretch")

    show = d[["modèle", "niveau", "n_answers", "accuracy_pct", "avg_response_time_s"]].rename(
        columns={
            "modèle": "Modèle",
            "niveau": "Difficulté",
            "n_answers": "Réponses",
            "accuracy_pct": "Accuracy %",
            "avg_response_time_s": "Latence moy. (s)",
        }
    )
    st.dataframe(show, width="stretch", hide_index=True)


def page_coverage(coverage: pd.DataFrame) -> None:
    if coverage.empty:
        st.info("Pas de données de couverture.")
        return

    d = coverage.copy()
    d["modèle"] = d["model"].map(short)
    avg_cov = float(d["question_coverage_pct"].mean())

    metrics_row(
        [
            metric(
                "Couverture moy.",
                pct(avg_cov),
                "questions silver",
                "lo" if avg_cov < 50 else "hi",
            ),
            metric("Questions total", num(d["n_questions_total"].iloc[0])),
            metric("Répondues", num(d["n_questions_answered"].sum())),
            metric("Réponses", num(d["n_answers"].sum())),
        ]
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        section("Couverture par modèle")
        fig = go.Figure(
            go.Bar(
                x=d["modèle"],
                y=d["question_coverage_pct"],
                marker_color=C["accent"],
                text=d["question_coverage_pct"].map(lambda v: f"{v:.1f}%"),
                textposition="outside",
                textfont=dict(color=C["ink"]),
                hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
            )
        )
        fig.update_yaxes(title="Couverture (%)", range=[0, 110])
        st.plotly_chart(fig_style(fig), width="stretch")
    with c2:
        section("Couverture vs accuracy")
        fig = px.scatter(
            d,
            x="question_coverage_pct",
            y="accuracy_pct",
            size="n_answers",
            color="modèle",
            color_discrete_sequence=SERIES,
            labels={
                "question_coverage_pct": "Couverture (%)",
                "accuracy_pct": "Accuracy (%)",
                "modèle": "",
                "n_answers": "Réponses",
            },
        )
        st.plotly_chart(fig_style(fig), width="stretch")

    show = d[
        [
            "modèle",
            "n_questions_total",
            "n_questions_answered",
            "n_answers",
            "question_coverage_pct",
            "accuracy_pct",
            "avg_response_time_s",
        ]
    ].rename(
        columns={
            "modèle": "Modèle",
            "n_questions_total": "Questions total",
            "n_questions_answered": "Questions répondues",
            "n_answers": "Réponses",
            "question_coverage_pct": "Couverture %",
            "accuracy_pct": "Accuracy %",
            "avg_response_time_s": "Latence moy. (s)",
        }
    )
    st.dataframe(show, width="stretch", hide_index=True)


def main() -> None:
    css()

    if not GOLD_DB.exists():
        st.error(
            f"Base introuvable : `{GOLD_DB}`.\n\n"
            "Depuis `dbt/` : `dbt run --profiles-dir .`"
        )
        st.stop()

    marts = load_marts(GOLD_DB.stat().st_mtime)
    by_model = marts["mart_perf_by_model"]
    by_prompt = marts["mart_perf_by_prompt"]
    by_category = marts["mart_perf_by_category"]
    by_difficulty = marts["mart_perf_by_difficulty"]
    coverage = marts["mart_coverage"]

    models = sorted(
        set(by_model.get("model", pd.Series(dtype=str)).dropna())
        | set(coverage.get("model", pd.Series(dtype=str)).dropna())
    )

    st.markdown(
        """
        <div class="brand">
          <h1>Triv<em>'IA'</em>l Pursuit</h1>
          <p>Benchmark gold — accuracy, latence et couverture des modèles.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f1, f2 = st.columns([3, 1], gap="medium")
    with f1:
        selected = st.multiselect(
            "Modèles",
            options=models,
            default=models,
            format_func=short,
            label_visibility="collapsed",
            placeholder="Filtrer les modèles…",
        )
    with f2:
        if st.button("Rafraîchir", width="stretch"):
            load_marts.clear()
            st.rerun()

    if not selected:
        st.warning("Choisis au moins un modèle.")
        st.stop()

    by_model = keep(by_model, selected)
    by_prompt = keep(by_prompt, selected)
    by_category = keep(by_category, selected)
    by_difficulty = keep(by_difficulty, selected)
    coverage = keep(coverage, selected)

    page = st.radio("Navigation", PAGES, horizontal=True, label_visibility="collapsed")

    if page == "Vue d'ensemble":
        page_overview(by_model, coverage, by_prompt)
    elif page == "Prompts":
        page_prompts(by_prompt)
    elif page == "Catégories":
        page_categories(by_category)
    elif page == "Difficulté":
        page_difficulty(by_difficulty)
    else:
        page_coverage(coverage)


if __name__ == "__main__":
    main()
