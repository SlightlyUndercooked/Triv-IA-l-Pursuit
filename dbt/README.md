# Documentation dbt

---

## Qu'est-ce que dbt jammy ?

dbt (*data build tool*) transforme des données déjà collectées en tables d'analyse avec du sql versionné

On écrit les modèles .sql, dbt les exécute dans le bon ordre et matérialise des vues et tables dans une base

dbt ne scrape pas et n'appelle pas les LLM, il commence quand les parquets silver existent

---

## Pourquoi dbt ?

Le sujet demande du médaillon + une couche gold en DuckDB via dbt

Python reste sur le scrap et les appels LLM, le sql gère les kpi
`dbt run` et on reconstruit le gold sans tout recalculer à la main. Si on ajoute un 2eme modèle on ajoute juste un parquet answers, pas une nouvelle pipeline. Streamlit pourra lire des tables gold propres plutôt que des dataframe pandas recalculé à chaque fois

---

## Pourquoi DuckDB ?

Demandé par le sujet, et pour notre volume (quelques milliers de questions * 2 prompts * N modèles) un fichier local suffit largement. Pas besoin d'une db postrges

DuckDB lit le parquet, donc le lien silver -> gold est simple.  
Le fichier `gold/benchmark.duckdb` est généré : on le reconstruit quand on veut, la source de vérité c'est le silver + les .sql dbt.

---

## Gold dans le médaillon

```
Bronze -> brut (scrap OpenTDB)
Silver -> propre + réponses ia (parquet)
Gold -> indicateurs du benchmark
```

Données à sortir :
- taux de bonnes réponses par modèle
- mcq vs open
- écarts par catégorie / difficulté
- temps de réponse moyen

---

## Staging vs marts

Deux dossiers dans `models/` :

**staging/**  
Proche du silver : nettoyage, unification des réponses de tous les modèles.  
En tables (pas en vues) pour que le fichier DuckDB reste lisible depuis n'importe où.  
Ex. `stg_questions`, `stg_answers`

**marts/**  
Les vrais kpi (performance, latence, etc), en tables pour que ce soit plus rapide à lire ensuite.

L'idée est de pas tout mélanger dans le même qsl

### Pourquoi le staging en tables et pas en view ?


Les vues DuckDB garderaient un `read_parquet('../silver/...')` avec un chemin relatif. Ça marche au moment du `dbt run` depuis `dbt/`, mais dès qu'on ouvre `gold/benchmark.duckdb` depuis ailleurs ( racine repo, Streamlit, script python), le chemin casse

En matérialisant le staging en tables, le silver est figé dans le `.duckdb` à chaque `dbt run`. Le fichier gold reste lisible de n'importe où. Le trade-off : il faut relancer dbt après un nouveau silver ce qu'on fait déjà de toute façon

---

## Partie commune ?

Nous partons sur un seul gold partagé au lieu d'un gold par modèle. Les réponses de chaque ia sont déjà séparées dans `silver/answers/<slug>/`, dbt les rassemble et on s'appuie sur la colonne `model` pour comparer.

Si on souhaite ajouter les résultats d'un nouveau modèle (parquet), `dbt run` l'ajoute au benchmark. S'il faut des analyses plus précises sur un modèle en particulier, il est possible de filtrer après.

---

## Ce qu'il y a dans le projet

Staging : `stg_questions`, `stg_answers` (lit tous les `silver/answers/*/answers.parquet`)  
Marts : perf par modèle / prompt / catégorie / difficulté + `mart_coverage` (part du silver déjà répondu)  
Tests : `dbt test` (not_null, unicité, etc.)  

Important : lancer dbt **depuis le dossier `dbt/`** (chemins relatifs vers le silver).  
Les commandes sont dans le README à la racine.
