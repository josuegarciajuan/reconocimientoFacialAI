-- Índices para los escaneos completos que provocaban deadlocks y lastraban la
-- ingesta. `fotos` solo tenía PRIMARY: cada `WHERE estancia_id = ?` y cada
-- `WHERE nombre_real_antesconversion = ?` era un full scan con locks amplios
-- bajo escritura concurrente (de ahí los SQLSTATE 40001 en clasificadorV2.php).
-- `estancias` se filtra por camara_id + rango de fecha_fin -> índice compuesto.
--
-- Idempotente: MySQL 8 no soporta `ADD INDEX IF NOT EXISTS`, así que se usa un
-- procedimiento que comprueba information_schema.STATISTICS antes de crear.
DROP PROCEDURE IF EXISTS rf_add_index;
DELIMITER $$
CREATE PROCEDURE rf_add_index(IN p_tabla VARCHAR(64), IN p_indice VARCHAR(64), IN p_cols VARCHAR(255))
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_tabla AND INDEX_NAME = p_indice
    ) THEN
        SET @rf_sql = CONCAT('ALTER TABLE `', p_tabla, '` ADD INDEX `', p_indice, '` (', p_cols, ')');
        PREPARE rf_stmt FROM @rf_sql;
        EXECUTE rf_stmt;
        DEALLOCATE PREPARE rf_stmt;
    END IF;
END$$
DELIMITER ;

CALL rf_add_index('fotos', 'idx_fotos_estancia', 'estancia_id');
CALL rf_add_index('fotos', 'idx_fotos_nombre', 'nombre_real_antesconversion(191)');
CALL rf_add_index('estancias', 'idx_estancias_cam_fecha', 'camara_id, fecha_fin');

DROP PROCEDURE IF EXISTS rf_add_index;
