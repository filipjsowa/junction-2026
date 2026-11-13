-- MariaDB 11.8+ (native VECTOR type). Runs automatically on the first `docker compose up`.
-- TODO before first start: replace 1024 with the embedding API's dimension (EMBEDDING_DIM).

CREATE TABLE seed_channels (
  channel_id   VARCHAR(255) PRIMARY KEY,
  platform     VARCHAR(16) NOT NULL,     -- 'telegram' | 'bluesky' | 'synthetic' | 'twitter'
  name         VARCHAR(255),
  role         VARCHAR(16) NOT NULL,     -- 'suspect' | 'known_actor' | 'control'
  source_url   TEXT                      -- why it is on the list
);

CREATE TABLE messages (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  platform       VARCHAR(16) NOT NULL,
  channel_id     VARCHAR(255) NOT NULL,
  author_id      VARCHAR(255),
  text           TEXT NOT NULL,
  text_hash      CHAR(64) NOT NULL,
  lang           VARCHAR(8),
  ts             DATETIME(3) NOT NULL,   -- always UTC
  url            TEXT,
  forwarded_from VARCHAR(255),
  is_control     BOOLEAN DEFAULT FALSE,
  synthetic      BOOLEAN DEFAULT FALSE,  -- dev data; never counts in reported metrics
  label          VARCHAR(64),            -- ground truth for synthetic rows, e.g. 'swarm:ukrainian-soldier' | 'benign:wire-story' | 'organic'
  embedding      VECTOR(1024) NOT NULL,  -- indexed, so must be NOT NULL
  cluster_id     INT,
  UNIQUE KEY uq_channel_hash_ts (channel_id, text_hash, ts),
  KEY (ts), KEY (channel_id), KEY (cluster_id),
  VECTOR INDEX (embedding) M=16 DISTANCE=cosine
);

CREATE TABLE clusters (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  size            INT,
  first_seen      DATETIME(3),
  last_seen       DATETIME(3),
  centroid        VECTOR(1024),         -- no index: few hundred rows, a scan is fine
  features        JSON,  -- {match_similarity, near_dup_share, account_spread, burstiness, known_actor_share, null_model_z}
  auto_score      FLOAT,
  contributions   JSON,  -- [{feature, value, contribution, text}]
  narrative       TEXT,
  techniques      JSON,  -- [{name, quote, message_id}]
  suggested       VARCHAR(32),          -- auto verdict
  human_label     VARCHAR(16),          -- 'confirmed' | 'rejected' | 'benign'
  labeled_by      VARCHAR(64),
  labeled_at      DATETIME(3),
  label_note      TEXT
);

CREATE TABLE eval_runs (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  run_at          DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  threshold       FLOAT,
  precision_score FLOAT,                -- PRECISION is a reserved word
  fpr             FLOAT,
  n_labels        INT,
  eval_set        VARCHAR(255)
);
