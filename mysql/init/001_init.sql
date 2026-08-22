USE demoapp;

CREATE TABLE IF NOT EXISTS app_config (
  config_key VARCHAR(100) PRIMARY KEY,
  config_value VARCHAR(255) NOT NULL
);

INSERT INTO app_config(config_key, config_value) VALUES
('max_connections','200'),
('feature_x_enabled','true'),
('db_pool_timeout_seconds','30')
ON DUPLICATE KEY UPDATE config_value=VALUES(config_value);

-- PoC safety: the application user created by the official image is intentionally
-- restricted to SELECT on this one schema.
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'state_reader'@'%';
GRANT SELECT ON demoapp.* TO 'state_reader'@'%';
FLUSH PRIVILEGES;
