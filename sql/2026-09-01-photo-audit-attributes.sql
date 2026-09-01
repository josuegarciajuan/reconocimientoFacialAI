-- Per-photo immutable audit. Apply once on MySQL/MariaDB (InnoDB).
CREATE TABLE IF NOT EXISTS foto_audits (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  foto_id INT(11) NULL,
  correlation_id VARCHAR(255) NOT NULL,
  schema_version VARCHAR(32) NOT NULL,
  local_id VARCHAR(64) NOT NULL,
  camera_id VARCHAR(64) NOT NULL,
  classification VARCHAR(16) NOT NULL,
  classification_phase VARCHAR(16) NOT NULL DEFAULT 'initial',
  person_code VARCHAR(255) NULL,
  layers_json TEXT NOT NULL,
  attributes_json TEXT NULL,
  classified_at DOUBLE NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_foto_audit_correlation (correlation_id),
  KEY idx_foto_audit_foto (foto_id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

CREATE TABLE IF NOT EXISTS foto_audit_events (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  foto_id INT(11) NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  from_person_code VARCHAR(255) NULL,
  to_person_code VARCHAR(255) NULL,
  event_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_foto_audit_events_foto (foto_id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
