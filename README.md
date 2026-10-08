# CFBD Data Pipeline

An end-to-end college football data pipeline built with Python, PostgreSQL, and the CollegeFootballData API.

The purpose of this project is to build a production-style data workflow from the ground up rather than working from pre-cleaned CSV files. The pipeline extracts college football data from an external API, validates and transforms it, stores it in a relational PostgreSQL database, maintains existing records with upserts, and orchestrates the full process through a single command.

The next phase of the project will build an analytics layer on top of the database for SQL analysis, feature engineering, machine learning, and visualization.

---

## Current Version

**v0.0.9**

The core data engineering pipeline is complete and operational.

Current capabilities include:

- CFBD API ingestion
- PostgreSQL storage
- Relational database design
- Primary and foreign keys
- Data validation
- Data transformation
- Nested JSON serialization
- Incremental loading
- PostgreSQL upserts
- Database indexing
- Query performance analysis
- Step-level pipeline logging
- Master pipeline logging
- Pipeline orchestration
- Error and failure logging

---

## Architecture

```text
CollegeFootballData API
          |
          v
    Python Extraction
          |
          v
  Validation / Cleaning
          |
          v
     Transformation
          |
          v
      PostgreSQL
       /      \
      v        v
   Games     Plays
      \        /
       \      /
        Teams
          |
          v
  Analytics Layer
     (next phase)
```

The full pipeline is orchestrated with:

```text
run_pipeline.py
      |
      v
load_games.py
      |
      v
load_plays.py
```

If an upstream pipeline step fails, downstream steps do not continue.

---

## Tech Stack

- Python
- PostgreSQL
- pgAdmin
- pandas
- SQLAlchemy
- psycopg2
- Requests
- python-dotenv
- CollegeFootballData API
- Git / GitHub

---

## Project Structure

```text
cfbd_pipeline/
|
├── scripts/
│   ├── load_games.py
│   ├── load_plays.py
│   └── run_pipeline.py
|
├── sql/
│   ├── create_tables.sql
│   └── create_indexes.sql
|
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

`.env` contains local credentials and is excluded from Git.

`.env.example` documents the environment variables required to run the project without exposing any credentials.

---

## Environment Variables

Create a `.env` file in the project root:

```text
CFBD_API_KEY=your_api_key

DB_HOST=localhost
DB_PORT=5432
DB_NAME=college_football
DB_USER=postgres
DB_PASSWORD=your_password
```

An `.env.example` file can be committed safely:

```text
CFBD_API_KEY=
DB_HOST=localhost
DB_PORT=5432
DB_NAME=college_football
DB_USER=postgres
DB_PASSWORD=
```

---

## Database Design

The project currently contains the following primary tables.

### `teams`

Stores one record for each college football team.

```text
teams
-----
team_id             PRIMARY KEY
school
classification
conference
```

Team IDs originate from CFBD and are referenced by game records.

### `games`

Stores game-level information.

Important fields include:

```text
games
-----
id                  PRIMARY KEY
season
week
seasonType
startDate
completed
conferenceGame

homeId              FOREIGN KEY -> teams.team_id
homeTeam
homeConference
homePoints

awayId              FOREIGN KEY -> teams.team_id
awayTeam
awayConference
awayPoints

attendance
venue
excitementIndex
...
```

Each game is uniquely identified by its CFBD game ID.

### `plays`

Stores play-by-play data.

```text
plays
-----
id                  PRIMARY KEY
game_id             FOREIGN KEY -> games.id

drive_id
drive_number
play_number

offense
defense
period
clock

down
distance
yardline
yards_to_goal
yards_gained

scoring
play_type
play_text
ppa
wallclock
...
```

The current 2025 play-by-play dataset contains more than 280,000 plays.

### `pipeline_runs`

Tracks individual pipeline executions.

```text
pipeline_runs
-------------
run_id
pipeline_name
run_timestamp
rows_pulled
rows_inserted
rows_updated
rows_rejected
status
error_message
```

This provides a persistent history of successful and failed ingestion runs.

### `pipeline_master_runs`

Tracks execution of the entire orchestrated pipeline.

```text
pipeline_master_runs
--------------------
run_id
start_timestamp
end_timestamp
status
completed_steps
error_message
```

This makes it possible to distinguish between the performance of individual pipeline steps and the overall workflow.

---

## Running the Pipeline

Activate the virtual environment first.

On Windows:

```bash
.venv\Scripts\activate
```

Then run:

```bash
python scripts/run_pipeline.py
```

This executes the pipeline in order:

```text
1. Load / update games
2. Load / update plays
3. Log each pipeline step
4. Log overall pipeline execution
```

The individual scripts can also still be run independently:

```bash
python scripts/load_games.py
```

```bash
python scripts/load_plays.py
```

---

## Data Loading Strategy

The project initially used full-table loading with `pandas.to_sql()`.

The pipeline has since evolved into an incremental upsert architecture.

### Initial approach

```text
API
 |
 v
Pull all data
 |
 v
Replace / append database table
```

### Current approach

```text
API
 |
 v
Pull source data
 |
 v
Validate
 |
 v
Transform
 |
 v
PostgreSQL primary key check
 |
 +------------------+
 |                  |
 v                  v
New ID          Existing ID
 |                  |
 v                  v
INSERT             UPDATE
 |                  |
 +--------+---------+
          |
          v
        LOG RUN
```

PostgreSQL's:

```sql
ON CONFLICT (id) DO UPDATE
```

is used to maintain existing records.

This is important because CFBD may update previously loaded games as new information becomes available.

Examples include:

- final scores
- completion status
- kickoff information
- postgame ratings
- win probabilities
- other game metadata

---

## Data Validation

Before data is written to PostgreSQL, required fields are checked.

For games, critical fields include:

```text
id
season
homeId
awayId
homeTeam
awayTeam
```

For plays, critical fields include:

```text
id
game_id
```

Rows missing critical identifiers are rejected rather than loaded into the database.

The number of rejected rows is recorded in `pipeline_runs`.

---

## Database Indexing

Indexes were added to improve query performance as the play-by-play table grew.

Current examples include:

```sql
CREATE INDEX idx_plays_game_id
ON plays(game_id);
```

```sql
CREATE INDEX idx_plays_offense
ON plays(offense);
```

```sql
CREATE INDEX idx_plays_defense
ON plays(defense);
```

```sql
CREATE INDEX idx_plays_play_type
ON plays(play_type);
```

```sql
CREATE INDEX idx_games_season
ON games(season);
```

```sql
CREATE INDEX idx_games_season_week
ON games(season, week);
```

Query performance was evaluated using:

```sql
EXPLAIN ANALYZE
```

This allowed inspection of PostgreSQL execution strategies such as:

```text
Sequential Scan
Index Scan
Bitmap Index Scan
```

---

# Issues Encountered and Resolved

Building the pipeline exposed several issues that required debugging and changes to the architecture.

These are documented here because they were an important part of building and understanding the system.

## 1. PostgreSQL Server Was Not Initially Running

### Issue

pgAdmin was installed locally, but attempts to connect to:

```text
localhost:5432
```

timed out.

### Cause

pgAdmin is only a graphical management interface. The PostgreSQL database server itself had not been installed.

### Resolution

PostgreSQL Server was installed separately and its Windows service was started.

pgAdmin was then able to connect using:

```text
Host: localhost
Port: 5432
Database: postgres
User: postgres
```

This clarified the difference between the PostgreSQL server and pgAdmin.

## 2. Only 2015 Games Appeared in PostgreSQL

### Issue

The API successfully pulled multiple seasons, but PostgreSQL appeared to contain only games from 2015.

### Investigation

Debugging output was added before and after the database load to determine whether the issue occurred during:

```text
API extraction
DataFrame concatenation
Database insertion
```

The combined pandas DataFrame contained all requested seasons.

### Cause

The database insert was failing before the complete dataset could be written.

This led directly to the next issue.

## 3. PostgreSQL Could Not Insert Python Dictionaries

### Issue

The database load produced:

```text
psycopg2.ProgrammingError:
can't adapt type 'dict'
```

### Cause

Some CFBD API fields contained nested Python structures such as dictionaries and lists.

These objects could not be inserted directly through the original pandas / psycopg2 workflow.

Examples included line score structures and other nested fields.

### Resolution

Nested dictionaries and lists were serialized into JSON strings before loading.

```python
def serialize_nested(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value
```

This allowed PostgreSQL to store the values safely.

Future versions may move some of these fields to native PostgreSQL `JSONB` types.

## 4. Duplicate Team IDs

### Issue

Building the `teams` table generated:

```text
duplicate key value violates unique constraint "teams_pkey"
```

### Cause

The same team ID appeared in multiple seasons with different metadata.

For example, a program's conference affiliation may change while its team ID remains constant.

Therefore `team_id` was stable, while `conference` and `classification` could change over time.

### Resolution

The teams population query uses PostgreSQL:

```sql
DISTINCT ON (team_id)
```

with seasons ordered newest-first.

This keeps one current representation of each team.

### Modeling Lesson

A future version could separate these concepts into:

```text
teams
-----
team_id
school
```

and:

```text
team_seasons
------------
team_id
season
conference
classification
```

This would preserve historical conference membership more accurately.

## 5. Nested Play Clock Objects

### Issue

Inspection of the CFBD play-by-play response showed that `clock` was a nested dictionary instead of a scalar value.

### Resolution

The clock object is serialized into JSON text before database insertion.

This avoided the same dictionary-adaptation issue encountered during the games load.

## 6. Column Rename Caused a KeyError

### Issue

The plays pipeline originally used `gameId` from the API.

The database schema was changed to use consistent snake_case naming:

```text
game_id
```

A later line still referenced:

```python
plays_df["gameId"]
```

which caused:

```text
KeyError: 'gameId'
```

### Resolution

All downstream references were updated to use:

```python
plays_df["game_id"]
```

### Lesson

Transformation order matters. Once a column is renamed, every downstream operation must reference the transformed schema.

## 7. Duplicate Primary Keys During Incremental Loading

### Issue

After incremental loading was introduced, the games pipeline correctly reported:

```text
New games: 0
```

but then still failed with a duplicate primary key error.

### Cause

The new incremental insert logic had been added, but the old full-table:

```python
games_df.to_sql(...)
```

block was still executing afterward.

Therefore the pipeline correctly skipped existing rows and then attempted to insert all rows again.

### Resolution

The old full-table insert was removed.

Only the incremental/upsert load path remains.

## 8. Incremental Inserts Could Not Update Existing Games

### Issue

The first incremental architecture worked by comparing incoming IDs to IDs already stored in PostgreSQL.

If the ID already existed, the row was skipped.

That prevented duplicates, but introduced a new problem.

A game might initially be stored as:

```text
completed = false
home_points = null
away_points = null
```

and later CFBD might return:

```text
completed = true
home_points = 31
away_points = 24
```

The existing row would never receive the update.

### Resolution

The pipeline was upgraded to use PostgreSQL upserts:

```sql
ON CONFLICT (id)
DO UPDATE
```

The database can now insert new records and update existing records.

This allows the local database to stay synchronized with changes in the source data.

## 9. Pipeline Failures Were Not Persistently Logged

### Issue

Originally, failures were only visible in the terminal.

Once the terminal session ended, there was no persistent history of what happened.

### Resolution

The `pipeline_runs` table was created.

Each execution records information including:

```text
pipeline_name
rows_pulled
rows_inserted
rows_updated
rows_rejected
status
error_message
```

Both successful and failed runs can now be audited directly from PostgreSQL.

## 10. Pipeline Steps Had to Be Run Manually

### Issue

The games and plays ingestion scripts originally required separate commands:

```bash
python scripts/load_games.py
```

followed by:

```bash
python scripts/load_plays.py
```

This required manual coordination.

### Resolution

A master orchestration script was created:

```bash
python scripts/run_pipeline.py
```

The orchestrator starts the pipeline, runs games first, checks for success, runs plays next, and logs the overall result.

If the games pipeline fails, the plays pipeline does not execute.

## 11. Large Play-by-Play Loads

### Issue

The 2025 play dataset contains more than 280,000 records.

Sending very large insert statements at once is less manageable and may increase memory and database load.

### Resolution

Database operations are processed in chunks.

For example:

```python
chunk_size = 5000
```

The plays DataFrame is processed batch-by-batch rather than as one massive database operation.

---

# Example SQL Queries

## Games Per Season

```sql
SELECT
    season,
    COUNT(*) AS number_of_games
FROM games
GROUP BY season
ORDER BY season;
```

## Notre Dame Games

```sql
SELECT
    season,
    week,
    "homeTeam",
    "awayTeam",
    "homePoints",
    "awayPoints"
FROM games
WHERE "homeTeam" = 'Notre Dame'
   OR "awayTeam" = 'Notre Dame'
ORDER BY season, week;
```

## Number of Plays Per Game

```sql
SELECT
    g.season,
    g.week,
    g."homeTeam",
    g."awayTeam",
    COUNT(p.id) AS number_of_plays
FROM games g
JOIN plays p
    ON g.id = p.game_id
GROUP BY
    g.season,
    g.week,
    g.id,
    g."homeTeam",
    g."awayTeam"
ORDER BY g.season, g.week;
```

## Notre Dame Play Types

```sql
SELECT
    play_type,
    COUNT(*) AS plays,
    ROUND(
        AVG(yards_gained)::numeric,
        2
    ) AS avg_yards
FROM plays
WHERE offense = 'Notre Dame'
GROUP BY play_type
ORDER BY plays DESC;
```

## Pipeline Run History

```sql
SELECT *
FROM pipeline_runs
ORDER BY run_timestamp DESC;
```

## Master Pipeline History

```sql
SELECT *
FROM pipeline_master_runs
ORDER BY start_timestamp DESC;
```

---

# Development History

The project has intentionally been built incrementally.

### v0.0.1

Load one season of CFBD game data into PostgreSQL.

### v0.0.2

Load multiple seasons into a single games table.

### v0.0.3

Define the PostgreSQL games schema manually instead of allowing pandas to generate it.

### v0.0.4

Add a relational teams table and foreign-key relationships.

### v0.0.5

Add play-by-play data and connect plays to games.

### v0.0.6

Add indexes and analyze PostgreSQL query performance.

### v0.0.7

Implement incremental loading and pipeline-run logging.

### v0.0.8

Implement validation, PostgreSQL upserts, rejected-row tracking, and failure logging.

### v0.0.9

Add full pipeline orchestration and master-run logging.

---

# Next Phase: v0.1.0

The core ingestion infrastructure is now complete.

The next phase will focus on building an analytics layer on top of PostgreSQL.

Planned work includes:

- reusable SQL views
- analytical SQL queries
- team-level metrics
- game-level feature tables
- play-by-play aggregations
- EPA / PPA analysis
- situational football analysis
- Python analysis directly from PostgreSQL
- machine-learning-ready datasets
- visualization and dashboard integration

The long-term architecture is intended to become:

```text
CFBD API
   |
   v
Data Engineering Pipeline
   |
   v
PostgreSQL
   |
   v
Analytics Layer
   |
   +----------------+
   |                |
   v                v
Python / ML      Tableau / App
```

---

# Project Goals

This project is primarily intended as a learning and portfolio project focused on understanding the complete data lifecycle.

Rather than beginning with a clean dataset, the goal is to gain experience with:

```text
external APIs
     |
     v
data ingestion
     |
     v
data validation
     |
     v
data transformation
     |
     v
relational modeling
     |
     v
SQL
     |
     v
pipeline maintenance
     |
     v
analytics
     |
     v
machine learning
```

The project is deliberately being built in small versions so that each component is understood before additional complexity is introduced.
