-- =====================================================================
-- CrimeMind — 010_research_platform.sql
-- Live Experimental Research Platform Tables
-- Tracks genuine experiment runs, hyperparameter sweeps, metric evaluations,
-- per-seed case rankings, and execution audit logs.
-- =====================================================================

CREATE TABLE IF NOT EXISTS research_experiments (
  experiment_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name               text NOT NULL,
  algorithm          text NOT NULL,
  dataset_id         text NOT NULL,
  seeds              integer[] NOT NULL,
  config_json        jsonb NOT NULL DEFAULT '{}'::jsonb,
  status             text NOT NULL DEFAULT 'QUEUED',
  progress_pct       numeric(5, 2) NOT NULL DEFAULT 0.00,
  current_step       text,
  execution_time_sec numeric(8, 3),
  error_message      text,
  created_by         text NOT NULL DEFAULT 'admin',
  created_at         timestamptz NOT NULL DEFAULT now(),
  started_at         timestamptz,
  completed_at       timestamptz
);

CREATE INDEX IF NOT EXISTS idx_research_exp_status ON research_experiments(status);
CREATE INDEX IF NOT EXISTS idx_research_exp_created_at ON research_experiments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_exp_algorithm ON research_experiments(algorithm);

CREATE TABLE IF NOT EXISTS research_experiment_metrics (
  metric_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  experiment_id  bigint NOT NULL REFERENCES research_experiments(experiment_id) ON DELETE CASCADE,
  metric_name    text NOT NULL,
  mean_value     numeric(8, 4) NOT NULL,
  std_dev        numeric(8, 4),
  std_err        numeric(8, 4),
  ci_lower       numeric(8, 4),
  ci_upper       numeric(8, 4),
  min_value      numeric(8, 4),
  max_value      numeric(8, 4)
);

CREATE INDEX IF NOT EXISTS idx_research_exp_metrics_exp ON research_experiment_metrics(experiment_id);

CREATE TABLE IF NOT EXISTS research_experiment_seed_results (
  result_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  experiment_id  bigint NOT NULL REFERENCES research_experiments(experiment_id) ON DELETE CASCADE,
  seed           integer NOT NULL,
  case_ref       text NOT NULL,
  metrics_json   jsonb NOT NULL,
  top_ranked     jsonb NOT NULL,
  n_candidates   integer NOT NULL DEFAULT 0,
  n_relevant     integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_research_exp_seed_exp ON research_experiment_seed_results(experiment_id);

CREATE TABLE IF NOT EXISTS research_experiment_logs (
  log_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  experiment_id  bigint NOT NULL REFERENCES research_experiments(experiment_id) ON DELETE CASCADE,
  log_timestamp  timestamptz NOT NULL DEFAULT now(),
  level          text NOT NULL DEFAULT 'INFO',
  message        text NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_exp_logs_exp ON research_experiment_logs(experiment_id, log_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON research_experiments TO cm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON research_experiment_metrics TO cm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON research_experiment_seed_results TO cm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON research_experiment_logs TO cm_app;
