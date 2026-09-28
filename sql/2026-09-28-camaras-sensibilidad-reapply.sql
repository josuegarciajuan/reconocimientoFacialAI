-- Re-aplicación de Fase 1 (recall) para producción.
-- El deploy automático SOLO aplica ficheros SQL NUEVOS (--diff-filter=A), y el
-- primer intento falló en MySQL por `ADD COLUMN IF NOT EXISTS`. Este fichero
-- nuevo vuelve a aplicar las columnas con DDL idempotente (procedimiento +
-- INFORMATION_SCHEMA), sin error si ya existen.

DROP PROCEDURE IF EXISTS rf_camaras_add_sensibilidad2;
DELIMITER //
CREATE PROCEDURE rf_camaras_add_sensibilidad2()
BEGIN
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'camaras'
                     AND COLUMN_NAME = 'threshold') THEN
        ALTER TABLE camaras ADD COLUMN threshold INT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'camaras'
                     AND COLUMN_NAME = 'blur') THEN
        ALTER TABLE camaras ADD COLUMN blur INT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'camaras'
                     AND COLUMN_NAME = 'dilate') THEN
        ALTER TABLE camaras ADD COLUMN dilate INT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'camaras'
                     AND COLUMN_NAME = 'seg_antes') THEN
        ALTER TABLE camaras ADD COLUMN seg_antes INT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'camaras'
                     AND COLUMN_NAME = 'seg_despues') THEN
        ALTER TABLE camaras ADD COLUMN seg_despues INT NULL;
    END IF;
END //
DELIMITER ;
CALL rf_camaras_add_sensibilidad2();
DROP PROCEDURE rf_camaras_add_sensibilidad2;

UPDATE camaras SET porcentaje_mov = 35 WHERE porcentaje_mov = 60;
UPDATE camaras SET dontCare = 120 WHERE dontCare = 220;
