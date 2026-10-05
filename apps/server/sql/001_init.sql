-- Raivon server schema v1: players (guest accounts) and their cloud saves (docs/gdd/12 §6.3, §8).
CREATE TABLE IF NOT EXISTS players (
  id          uuid PRIMARY KEY,
  device_id   text NOT NULL UNIQUE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  last_seen   timestamptz NOT NULL DEFAULT now(),
  country     text
);

CREATE TABLE IF NOT EXISTS saves (
  player_id   uuid PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  rev         integer NOT NULL,
  saved_at    timestamptz NOT NULL,
  data        jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_migrations (version) VALUES (1) ON CONFLICT DO NOTHING;
