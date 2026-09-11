# Triv'IA'l Pursuit


## Prérequis

- Python 3.10+
- [LM Studio](https://lmstudio.ai/)
- Modèle local : `nvidia/nemotron-3-nano-4b` par exempel

## Setup (après clone)

```bash

python -m venv .venv
source .venv/bin/activate 
# windows (quelle idée): .venv\Scripts\activate

pip install -r requirements.txt
```

## Bronze scrap OpenTDB

Récupérer (ou maj) `bronze/questions_raw.csv` via l’API OpenTDB  
(5s entre les requêtes, c'est assez long)

```bash
python src/scraping/scrape_opentbd.py
```

Le CSV bronze sera déjà dans le dépôt pour gagner du temps

## Silver questions et prompts

Nettoyage et normalisation des questions, puis génération des prompts communs aux différents modèles qui seront utilisés (`mcq` + `open`).

```bash
# les deux d’un coup
python src/enrichment/build_silver.py

# ou séparément
python src/enrichment/build_questions.py   # → silver/questions.parquet
python src/enrichment/build_prompts.py    # → silver/prompts.parquet
```

Templates de prompt : `silver/prompt_templates.yaml`

## Silver réponses Nemotron (LM Studio)

1. Démarrer LM Studio, puis le serveur api et charger le modèle :

```bash
lms server start
lms unload --all
lms load nvidia/nemotron-3-nano-4b -y -c 2048 --gpu max
```

2. Générer les réponses (reprise auto si interruption) :

```bash
# smoke test
python src/enrichment/build_answers.py --limit 20

# run complet (9156 prompts, 6h environ)
python src/enrichment/build_answers.py
```

Sortie : `silver/answers/nemotron/answers.parquet`  
Colonnes clés : `ai_answer`, `ai_correct`, `response_time`, `prompt_variant`, `model`.

Le parquet de réponses est **versionné** dans le dépôt (évite de refaire le run de 6h, de rien). Les commandes ci-dessus servent surtout à reproduire si besoin

Vérifier un run :

```bash
python -c "
import pandas as pd
df = pd.read_parquet('silver/answers/nemotron/answers.parquet')
print(len(df), 'lignes')
print('erreurs', df['error'].notna().sum())
print(df.groupby('prompt_variant')['ai_correct'].mean())
"
```

Relancer la même commande `build_answers.py` pour rejouer uniquement les lignes en erreur / manquantes.

## Silver réponses autre modèle

Même script : changer le modèle chargé dans LM Studio, puis passer `--model` (id LM Studio) et `--slug` (dossier sous `silver/answers/`).

```bash
lms unload --all
lms load <id-modele-lm-studio> -y -c 2048 --gpu max

python src/enrichment/build_answers.py --model <id-modele-lm-studio> --slug <nom-dossier>

# exemple
# python src/enrichment/build_answers.py --model liquid/lfm2.5-1.2b --slug lfm
```

Sortie : `silver/answers/<nom-dossier>/answers.parquet`

## Gold (dbt + DuckDB)

Transforme le silver en tables métier du benchmark (`gold/benchmark.duckdb`).  
Pourquoi dbt / DuckDB / staging vs marts : voir [`dbt/README.md`](dbt/README.md).

Prérequis silver : `questions.parquet` + au moins un `silver/answers/<slug>/answers.parquet`.

```bash
source .venv/bin/activate   # depuis la racine du repo (sinon dbt introuvable)
cd dbt

# verifier la connexion
dbt debug --profiles-dir .

# construire / reconstruire le gold depuis le silver actuel
dbt run --profiles-dir .

# tests de qualité (not_null, unicité, etc.)
dbt test --profiles-dir .

# force drop + recreate si besoin
# dbt run --profiles-dir . --full-refresh
```

Tables dans `gold/benchmark.duckdb` :
- staging : `stg_questions`, `stg_answers`
- marts : `mart_perf_by_model`, `mart_perf_by_prompt`, `mart_perf_by_category`, `mart_perf_by_difficulty`, `mart_coverage`

La base est régénérable (non versionnée). Un nouveau parquet sous `silver/answers/<slug>/` est pris en compte au prochain `dbt run`.

## Dashboard Streamlit

Visualise les marts gold (`mart_perf_*`, `mart_coverage`) via l’app dans `app/streamlit_app.py`.

Prérequis : `gold/benchmark.duckdb` déjà généré (`dbt run` ci-dessus).

```bash
source .venv/bin/activate
streamlit run app/streamlit_app.py
```

Ouvre ensuite l’URL affichée (souvent http://localhost:8501).  
Sans activer le venv : `.venv/bin/streamlit run app/streamlit_app.py`.

## Arborescence (état actuel)

```
bronze/questions_raw.csv
silver/questions.parquet
silver/prompts.parquet
silver/prompt_templates.yaml
silver/answers/nemotron/answers.parquet
dbt/
gold/benchmark.duckdb
app/streamlit_app.py
src/scraping/scrape_opentbd.py
src/enrichment/build_questions.py
src/enrichment/build_prompts.py
src/enrichment/build_silver.py
src/enrichment/build_answers.py
```
