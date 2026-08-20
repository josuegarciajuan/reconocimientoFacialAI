-- 2026-08-20: alinear default de dontCare de la tabla camaras con config/config.php.
-- La config real para cámaras NUEVAS es 220 (CONFIG_dontCare en config/config.php y
-- edit.php); el DEFAULT de la columna decía 500 (valor antiguo) y solo afectaba a
-- inserts crudos sin pasar por acciones.php. NO se tocan las filas existentes:
-- cada cámara conserva su valor calibrado a mano.
ALTER TABLE camaras MODIFY dontCare int(11) DEFAULT 220;
