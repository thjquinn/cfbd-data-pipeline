
CREATE TABLE public.games (
    id bigint NOT NULL,
    season integer NOT NULL,
    week integer,
    "seasonType" text,
    "startDate" timestamp with time zone,
    "startTimeTBD" boolean,
    completed boolean,
    "neutralSite" boolean,
    "conferenceGame" boolean,
    attendance integer,
    "venueId" integer,
    venue text,
    "homeId" integer,
    "homeTeam" text,
    "homeClassification" text,
    "homeConference" text,
    "homePoints" integer,
    "homeLineScores" text,
    "homePostgameWinProbability" double precision,
    "homePregameElo" double precision,
    "homePostgameElo" double precision,
    "awayId" integer,
    "awayTeam" text,
    "awayClassification" text,
    "awayConference" text,
    "awayPoints" integer,
    "awayLineScores" text,
    "awayPostgameWinProbability" double precision,
    "awayPregameElo" double precision,
    "awayPostgameElo" double precision,
    "excitementIndex" double precision,
    highlights text,
    notes text,
    playoff text
);

CREATE TABLE public.pipeline_master_runs (
    run_id bigint NOT NULL,
    start_timestamp timestamp with time zone NOT NULL,
    end_timestamp timestamp with time zone,
    status text NOT NULL,
    completed_steps text,
    error_message text
);

CREATE SEQUENCE public.pipeline_master_runs_run_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.pipeline_master_runs_run_id_seq OWNED BY public.pipeline_master_runs.run_id;

CREATE TABLE public.pipeline_runs (
    run_id bigint NOT NULL,
    pipeline_name text NOT NULL,
    run_timestamp timestamp with time zone DEFAULT now(),
    rows_pulled integer,
    rows_inserted integer,
    status text,
    rows_updated integer DEFAULT 0,
    rows_rejected integer DEFAULT 0,
    error_message text
);

CREATE SEQUENCE public.pipeline_runs_run_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.pipeline_runs_run_id_seq OWNED BY public.pipeline_runs.run_id;

CREATE TABLE public.plays (
    id text NOT NULL,
    game_id bigint NOT NULL,
    drive_id text,
    drive_number integer,
    play_number integer,
    offense text,
    offense_conference text,
    offense_score integer,
    defense text,
    defense_conference text,
    defense_score integer,
    home text,
    away text,
    period integer,
    clock text,
    offense_timeouts double precision,
    defense_timeouts double precision,
    yardline integer,
    yards_to_goal integer,
    down integer,
    distance integer,
    yards_gained integer,
    scoring boolean,
    play_type text,
    play_text text,
    ppa double precision,
    wallclock timestamp with time zone
);

CREATE TABLE public.teams (
    team_id integer NOT NULL,
    school text NOT NULL,
    classification text,
    conference text
);

ALTER TABLE ONLY public.pipeline_master_runs ALTER COLUMN run_id SET DEFAULT nextval('public.pipeline_master_runs_run_id_seq'::regclass);

ALTER TABLE ONLY public.pipeline_runs ALTER COLUMN run_id SET DEFAULT nextval('public.pipeline_runs_run_id_seq'::regclass);

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.pipeline_master_runs
    ADD CONSTRAINT pipeline_master_runs_pkey PRIMARY KEY (run_id);

ALTER TABLE ONLY public.pipeline_runs
    ADD CONSTRAINT pipeline_runs_pkey PRIMARY KEY (run_id);

ALTER TABLE ONLY public.plays
    ADD CONSTRAINT plays_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id);

CREATE INDEX idx_games_season ON public.games USING btree (season);

CREATE INDEX idx_games_season_week ON public.games USING btree (season, week);

CREATE INDEX idx_plays_defense ON public.plays USING btree (defense);

CREATE INDEX idx_plays_game_id ON public.plays USING btree (game_id);

CREATE INDEX idx_plays_offense ON public.plays USING btree (offense);

CREATE INDEX idx_plays_play_type ON public.plays USING btree (play_type);

ALTER TABLE ONLY public.games
    ADD CONSTRAINT fk_away_team FOREIGN KEY ("awayId") REFERENCES public.teams(team_id);

ALTER TABLE ONLY public.games
    ADD CONSTRAINT fk_home_team FOREIGN KEY ("homeId") REFERENCES public.teams(team_id);

ALTER TABLE ONLY public.plays
    ADD CONSTRAINT fk_plays_game FOREIGN KEY (game_id) REFERENCES public.games(id);

