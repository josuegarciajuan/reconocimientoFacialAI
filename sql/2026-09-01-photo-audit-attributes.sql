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
  ,CONSTRAINT fk_foto_audit_foto FOREIGN KEY (foto_id) REFERENCES fotos(id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

CREATE TABLE IF NOT EXISTS foto_audit_events (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  foto_id INT(11) NOT NULL,
  event_key VARCHAR(160) NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  camera_id VARCHAR(64) NOT NULL,
  from_person_code VARCHAR(255) NULL,
  to_person_code VARCHAR(255) NULL,
  event_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_foto_audit_event_key (event_key),
  KEY idx_foto_audit_events_foto (foto_id),
  CONSTRAINT fk_foto_audit_event_foto FOREIGN KEY (foto_id) REFERENCES fotos(id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

-- Enforce append-only audit rows; the sole permitted update links foto_id once.
DELIMITER //
CREATE TRIGGER foto_audits_no_mutation BEFORE UPDATE ON foto_audits FOR EACH ROW
BEGIN
  IF NOT (OLD.foto_id IS NULL AND NEW.foto_id IS NOT NULL
    AND OLD.correlation_id = NEW.correlation_id AND OLD.schema_version = NEW.schema_version
    AND OLD.local_id = NEW.local_id AND OLD.camera_id = NEW.camera_id
    AND OLD.classification = NEW.classification AND OLD.classification_phase = NEW.classification_phase
    AND (OLD.person_code <=> NEW.person_code) AND OLD.layers_json = NEW.layers_json
    AND (OLD.attributes_json <=> NEW.attributes_json) AND OLD.classified_at = NEW.classified_at) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audits is append-only';
  END IF;
END//
CREATE TRIGGER foto_audits_no_delete BEFORE DELETE ON foto_audits FOR EACH ROW
BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audits is append-only'; END//
CREATE TRIGGER foto_audit_events_no_mutation BEFORE UPDATE ON foto_audit_events FOR EACH ROW
BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audit_events is append-only'; END//
CREATE TRIGGER foto_audit_events_no_delete BEFORE DELETE ON foto_audit_events FOR EACH ROW
BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audit_events is append-only'; END//
DELIMITER ;
