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


-- =========================================================
-- Football Metrics
-- =========================================================

CREATE OR REPLACE VIEW vw_team_game_metrics AS

SELECT
    game_id,
    season,
    week,
    offense AS team,
    defense AS opponent,

    COUNT(*) AS total_plays,

    ROUND(
        AVG(yards_gained)::numeric,
        2
    ) AS yards_per_play,

    ROUND(
        AVG(ppa)::numeric,
        3
    ) AS avg_ppa,

    ROUND(
        100.0 * AVG(
            CASE
                WHEN down = 1 AND yards_gained >= distance * 0.50 THEN 1
                WHEN down = 2 AND yards_gained >= distance * 0.70 THEN 1
                WHEN down IN (3, 4) AND yards_gained >= distance THEN 1
                ELSE 0
            END
        ),
        2
    ) AS success_rate,

    ROUND(
        100.0 * AVG(
            CASE
                WHEN yards_gained >= 20 THEN 1
                ELSE 0
            END
        ),
        2
    ) AS explosive_play_rate,

    ROUND(
        AVG(
            CASE
                WHEN down IN (1, 2)
                THEN yards_gained
            END
        )::numeric,
        2
    ) AS early_down_yards_per_play,

    ROUND(
        100.0 * AVG(
            CASE
                WHEN down = 3 AND yards_gained >= distance THEN 1
                WHEN down = 3 THEN 0
                ELSE NULL
            END
        ),
        2
    ) AS third_down_conversion_rate

FROM vw_plays

WHERE down BETWEEN 1 AND 4

GROUP BY
    game_id,
    season,
    week,
    offense,
    defense;

-- =========================================================
-- Team Level Season Metrics
-- =========================================================

CREATE OR REPLACE VIEW vw_team_season_metrics AS

SELECT
    season,
    team,

    COUNT(*) AS games_played,

    ROUND(
        AVG(total_plays)::numeric,
        1
    ) AS avg_plays_per_game,

    ROUND(
        AVG(yards_per_play)::numeric,
        2
    ) AS avg_yards_per_play,

    ROUND(
        AVG(avg_ppa)::numeric,
        3
    ) AS avg_ppa,

    ROUND(
        AVG(success_rate)::numeric,
        2
    ) AS avg_success_rate,

    ROUND(
        AVG(explosive_play_rate)::numeric,
        2
    ) AS avg_explosive_play_rate,

    ROUND(
        AVG(early_down_yards_per_play)::numeric,
        2
    ) AS avg_early_down_yards_per_play,

    ROUND(
        AVG(third_down_conversion_rate)::numeric,
        2
    ) AS avg_third_down_conversion_rate

FROM vw_team_game_metrics

GROUP BY
    season,
    team;

-- =========================================================
-- Team Level Defensive Season Metrics
-- =========================================================

CREATE OR REPLACE VIEW vw_team_season_defense_metrics AS

SELECT
    season,
    opponent AS team,

    COUNT(*) AS games_played,

    ROUND(
        AVG(total_plays)::numeric,
        1
    ) AS avg_plays_faced_per_game,

    ROUND(
        AVG(yards_per_play)::numeric,
        2
    ) AS avg_yards_per_play_allowed,

    ROUND(
        AVG(avg_ppa)::numeric,
        3
    ) AS avg_ppa_allowed,

    ROUND(
        AVG(success_rate)::numeric,
        2
    ) AS avg_success_rate_allowed,

    ROUND(
        AVG(explosive_play_rate)::numeric,
        2
    ) AS avg_explosive_play_rate_allowed,

    ROUND(
        AVG(early_down_yards_per_play)::numeric,
        2
    ) AS avg_early_down_yards_per_play_allowed,

    ROUND(
        AVG(third_down_conversion_rate)::numeric,
        2
    ) AS avg_third_down_conversion_rate_allowed

FROM vw_team_game_metrics

GROUP BY
    season,
    opponent;

-- =========================================================
-- Team Season Profile
-- =========================================================

CREATE OR REPLACE VIEW vw_team_season_profile AS

SELECT
    o.season,
    o.team,

    -- Offense
    o.games_played AS offensive_games,
    o.avg_plays_per_game,
    o.avg_yards_per_play,
    o.avg_ppa,
    o.avg_success_rate,
    o.avg_explosive_play_rate,
    o.avg_early_down_yards_per_play,
    o.avg_third_down_conversion_rate,

    -- Defense
    d.games_played AS defensive_games,
    d.avg_plays_faced_per_game,
    d.avg_yards_per_play_allowed,
    d.avg_ppa_allowed,
    d.avg_success_rate_allowed,
    d.avg_explosive_play_rate_allowed,
    d.avg_early_down_yards_per_play_allowed,
    d.avg_third_down_conversion_rate_allowed

FROM vw_team_season_metrics o

LEFT JOIN vw_team_season_defense_metrics d
    ON o.season = d.season
   AND o.team = d.team;

-- =========================================================
-- Game Model Features
-- =========================================================

CREATE OR REPLACE VIEW vw_game_model_features AS

SELECT
    g.game_id,
    g.season,
    g.week,
    g.start_date,

    g.home_team_id,
    g.home_team,
    g.away_team_id,
    g.away_team,

    -- Target / result fields
    g.home_points,
    g.away_points,

    CASE
        WHEN g.home_points > g.away_points THEN 1
        ELSE 0
    END AS home_win,

    g.home_point_margin,

    -- Home team season metrics
    h.avg_yards_per_play AS home_avg_yards_per_play,
    h.avg_ppa AS home_avg_ppa,
    h.avg_success_rate AS home_avg_success_rate,
    h.avg_explosive_play_rate AS home_avg_explosive_play_rate,
    h.avg_early_down_yards_per_play AS home_avg_early_down_yards_per_play,
    h.avg_third_down_conversion_rate AS home_avg_third_down_conversion_rate,

    h.avg_yards_per_play_allowed AS home_avg_yards_per_play_allowed,
    h.avg_ppa_allowed AS home_avg_ppa_allowed,
    h.avg_success_rate_allowed AS home_avg_success_rate_allowed,
    h.avg_explosive_play_rate_allowed AS home_avg_explosive_play_rate_allowed,

    -- Away team season metrics
    a.avg_yards_per_play AS away_avg_yards_per_play,
    a.avg_ppa AS away_avg_ppa,
    a.avg_success_rate AS away_avg_success_rate,
    a.avg_explosive_play_rate AS away_avg_explosive_play_rate,
    a.avg_early_down_yards_per_play AS away_avg_early_down_yards_per_play,
    a.avg_third_down_conversion_rate AS away_avg_third_down_conversion_rate,

    a.avg_yards_per_play_allowed AS away_avg_yards_per_play_allowed,
    a.avg_ppa_allowed AS away_avg_ppa_allowed,
    a.avg_success_rate_allowed AS away_avg_success_rate_allowed,
    a.avg_explosive_play_rate_allowed AS away_avg_explosive_play_rate_allowed

FROM vw_games g

LEFT JOIN vw_team_season_profile h
    ON g.season = h.season
   AND g.home_team = h.team

LEFT JOIN vw_team_season_profile a
    ON g.season = a.season
   AND g.away_team = a.team

WHERE g.completed = TRUE;