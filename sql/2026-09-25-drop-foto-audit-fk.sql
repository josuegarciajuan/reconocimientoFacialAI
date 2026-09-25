-- 2026-09-25 — Elimina las FK foto_audits.foto_id / foto_audit_events.foto_id -> fotos.id.
--
-- Motivo: las auditorías son append-only (triggers foto_audits_no_delete /
-- foto_audit_events_no_delete) y deben sobrevivir al borrado runtime de fotos
-- duplicadas que hace el clasificador (clasificadorV2.php, dedup por estancia).
-- Con las FK RESTRICT ese DELETE fallaba con error 1451 y dejaba al daemon
-- rf-clasificador en bucle de caída (no publicaba ninguna foto).
--
-- Se conservan los índices idx_foto_audit_foto / idx_foto_audit_events_foto.
-- El foto_id histórico puede quedar "colgando" cuando la foto se elimina: es
-- evidencia histórica inmutable, no una referencia operativa.
--
-- Idempotente: re-ejecutable sin error si las FK ya no existen.

SET @fk := (SELECT CONSTRAINT_NAME FROM information_schema.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND TABLE_NAME = 'foto_audits'
              AND CONSTRAINT_NAME = 'fk_foto_audit_foto');
SET @sql := IF(@fk IS NOT NULL,
               'ALTER TABLE foto_audits DROP FOREIGN KEY fk_foto_audit_foto',
               'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk := (SELECT CONSTRAINT_NAME FROM information_schema.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND TABLE_NAME = 'foto_audit_events'
              AND CONSTRAINT_NAME = 'fk_foto_audit_event_foto');
SET @sql := IF(@fk IS NOT NULL,
               'ALTER TABLE foto_audit_events DROP FOREIGN KEY fk_foto_audit_event_foto',
               'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
