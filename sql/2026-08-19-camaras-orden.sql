-- Migración 2026-08-19: orden manual de las cámaras en "El Ojo en Vivo".
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-camaras-orden.sql
--
-- La rejilla de Cámaras en Directo permite arrastrar y soltar para reordenar.
-- La posición se guarda en `camaras.orden` (0 = sin orden explícito, se usa
-- descripcion ASC como desempate). Al soltar una tarjeta se reescribe el orden
-- completo de la rejilla, así que los valores son contiguos y por local.

ALTER TABLE `camaras`
    ADD COLUMN `orden` INT NOT NULL DEFAULT 0
        COMMENT 'posición en la rejilla de El Ojo en Vivo (arrastrar y soltar)';

CREATE INDEX `idx_camaras_local_orden` ON `camaras` (`local_id`, `orden`);
