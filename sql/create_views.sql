-- =========================================================
-- Game-level analytics view
-- =========================================================

CREATE OR REPLACE VIEW vw_games AS

SELECT
    g.id AS game_id,

    g.season,
    g.week,
    g."seasonType" AS season_type,
    g."startDate" AS start_date,

    g."homeId" AS home_team_id,
    g."homeTeam" AS home_team,
    g."homeConference" AS home_conference,

    g."awayId" AS away_team_id,
    g."awayTeam" AS away_team,
    g."awayConference" AS away_conference,

    g."homePoints" AS home_points,
    g."awayPoints" AS away_points,

    g."homePregameElo" AS home_pregame_elo,
    g."awayPregameElo" AS away_pregame_elo,

    g."homePostgameElo" AS home_postgame_elo,
    g."awayPostgameElo" AS away_postgame_elo,

    g."excitementIndex" AS excitement_index,

    g."conferenceGame" AS conference_game,
    g."neutralSite" AS neutral_site,
    g.completed,

    CASE
        WHEN g."homePoints" > g."awayPoints"
            THEN g."homeId"
        WHEN g."awayPoints" > g."homePoints"
            THEN g."awayId"
        ELSE NULL
    END AS winner_team_id,

    CASE
        WHEN g."homePoints" > g."awayPoints"
            THEN g."homeTeam"
        WHEN g."awayPoints" > g."homePoints"
            THEN g."awayTeam"
        ELSE NULL
    END AS winner_team,

    g."homePoints" - g."awayPoints"
        AS home_point_margin

FROM games g;

-- =========================================================
-- Play-level analytics view
-- =========================================================

CREATE OR REPLACE VIEW vw_plays AS

SELECT
    p.id AS play_id,
    p.game_id,

    g.season,
    g.week,

    g."homeTeam" AS home_team,
    g."awayTeam" AS away_team,

    p.drive_id,
    p.drive_number,
    p.play_number,

    p.offense,
    p.defense,

    p.period,
    p.clock,

    p.down,
    p.distance,
    p.yardline,
    p.yards_to_goal,
    p.yards_gained,

    p.scoring,
    p.play_type,
    p.play_text,
    p.ppa,

    p.offense_score,
    p.defense_score,

    p.wallclock

FROM plays p

JOIN games g
    ON p.game_id = g.id;

-- =========================================================
-- Team-level analytics view
-- =========================================================

CREATE OR REPLACE VIEW vw_team_game_stats AS

SELECT
    game_id,
    season,
    week,
    offense AS team,
    defense AS opponent,

    COUNT(*) AS total_plays,

    SUM(yards_gained) AS total_yards,

    ROUND(
        AVG(yards_gained)::numeric,
        2
    ) AS yards_per_play,

    ROUND(
        AVG(ppa)::numeric,
        3
    ) AS avg_ppa,

    SUM(
        CASE
            WHEN scoring = TRUE THEN 1
            ELSE 0
        END
    ) AS scoring_plays

FROM vw_plays

GROUP BY
    game_id,
    season,
    week,
    offense,
    defense;