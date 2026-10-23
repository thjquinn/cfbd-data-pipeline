# CFBD Data Pipeline

End-to-end college football data pipeline built with **Python, PostgreSQL, SQL, and the CollegeFootballData API**.

The project started as a way to learn the full data lifecycle from raw API ingestion through database design, analytics engineering, and machine learning.

## Current Status

The project now includes:

- CFBD game and play-by-play ingestion
- PostgreSQL relational database
- Primary / foreign keys and indexes
- Validation, upserts, and pipeline logging
- Automated pipeline orchestration
- Historical play-by-play backfill for 2021–2025
- Reusable SQL analytics views
- Leakage-safe rolling pregame features
- Model-ready game-level dataset
- Baseline machine learning experiments

### Current baseline model

**Logistic V1** is the current official baseline.

| Model | Accuracy | ROC AUC | Log Loss |
|---|---:|---:|---:|
| Logistic V1 | **0.7255** | **0.7983** | **0.5335** |
| Logistic V2 | 0.7213 | 0.7947 | 0.5370 |

Training uses **2021–2024** and testing uses **2025**.

Logistic V1 uses five pregame features:

- Home offensive PPA
- Away offensive PPA
- Home defensive PPA allowed
- Away defensive PPA allowed
- Pregame Elo difference

An expanded 17-feature version did not improve performance, so the simpler model remains the baseline.

---

## Architecture

```text
CollegeFootballData API
        ↓
Python ingestion
        ↓
Validation + transformation
        ↓
PostgreSQL
        ↓
SQL analytics views
        ↓
Rolling pregame features
        ↓
Python / ML
```

Main pipeline:

```text
run_pipeline.py
    ↓
load_games.py
    ↓
load_plays.py
```

---

## Tech Stack

- Python
- PostgreSQL
- pgAdmin
- pandas
- SQLAlchemy
- psycopg2
- scikit-learn
- CollegeFootballData API
- Git / GitHub

---

## Project Structure

```text
cfbd_pipeline/
├── notebooks/
│   └── 01_baseline_model.ipynb
├── scripts/
│   ├── load_games.py
│   ├── load_plays.py
│   └── run_pipeline.py
├── sql/
│   ├── create_tables.sql
│   ├── create_indexes.sql
│   └── create_views.sql
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Database

Core tables:

```text
teams
games
plays
pipeline_runs
pipeline_master_runs
```

Important relationships:

```text
teams.team_id
    ↑
games.homeId / games.awayId

games.id
    ↑
plays.game_id
```

The `plays` table contains historical play-by-play data for **2021–2025**.

---

## Analytics Layer

The SQL layer progressively transforms raw play data into reusable analytical datasets.

Key views include:

```text
vw_games
vw_plays
vw_team_game_metrics
vw_team_season_metrics
vw_team_season_defense_metrics
vw_team_season_profile
vw_team_pregame_offense
vw_team_pregame_defense
vw_team_pregame_metrics
vw_game_model_features_v2
```

`vw_game_model_features_v2` is the current leakage-safe modeling dataset.

Rolling team metrics only use games played **before** the current matchup.

Example:

```text
Week 1 → no current-season history
Week 2 → Week 1 only
Week 3 → Weeks 1–2
Week 4 → Weeks 1–3
```

This prevents future information from leaking into historical predictions.

---

## Running the Pipeline

Create a local `.env` file:

```text
CFBD_API_KEY=
DB_HOST=localhost
DB_PORT=5432
DB_NAME=college_football
DB_USER=postgres
DB_PASSWORD=
```

Then run:

```bash
python scripts/run_pipeline.py
```

The pipeline:

1. pulls CFBD data
2. validates and transforms records
3. inserts new rows
4. updates existing rows with PostgreSQL upserts
5. logs step-level and full-pipeline results

---

## Key Problems Solved

A few issues encountered while building the project:

### Nested API data

CFBD returned dictionaries/lists that PostgreSQL could not insert directly.

**Fix:** serialize nested values before loading.

### Duplicate team IDs

Teams can retain the same ID while conference information changes over time.

**Fix:** retain one current team record using PostgreSQL `DISTINCT ON`.

### Duplicate records

Early versions attempted to reload existing rows.

**Fix:** first added incremental inserts, then upgraded to:

```sql
ON CONFLICT (id) DO UPDATE
```

### Pipeline failures

Failures originally existed only in terminal output.

**Fix:** added persistent step-level and master pipeline logging.

### Data leakage

Full-season metrics would allow early-season games to use future information.

**Fix:** rolling SQL window functions calculate features using only prior games.

### More features did not improve the model

A 17-feature logistic regression slightly underperformed the 5-feature baseline.

**Lesson:** more variables do not necessarily add useful signal.

---

## Development Progress

```text
v0.0.x  Data engineering foundation
        API ingestion, PostgreSQL, schema design,
        indexes, upserts, logging, orchestration

v0.1.x  Analytics engineering
        SQL views, team metrics, rolling pregame features,
        model-ready dataset

v0.2.x  Modeling
        Baselines, logistic regression,
        feature experimentation
```

---

## Next Steps

Near-term priorities:

- handle Week 1 / early-season missing features with prior-season information
- test genuinely new feature families rather than more correlated efficiency metrics
- compare Random Forest and XGBoost against Logistic V1
- improve probability calibration and evaluation
- eventually expose predictions and analytics through a dashboard or app

---

## Project Goal

The goal is not simply to maximize prediction accuracy.

The project is designed to demonstrate and learn the complete workflow:

```text
API
→ ingestion
→ validation
→ relational database
→ SQL analytics
→ feature engineering
→ machine learning
→ evaluation
→ deployment
```
