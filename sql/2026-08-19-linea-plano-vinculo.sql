-- Migración 2026-08-19: vínculo 1:1 línea de cámara ↔ línea del plano.
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-linea-plano-vinculo.sql
--
-- Contexto: una línea de vigilancia se dibuja sobre lo que enfoca la cámara
-- (tabla `lineas`) y se guarda si algo la cruza. Ahora la MISMA línea se
-- representa sobre el plano 2D del local (tabla `lineas_plano`) para poder
-- ver en el mapa dónde enfoca cada cámara y dibujar recorridos.
-- `lineas_plano.linea_id` es la FK que une ambos artefactos (1:1):
--   * NULL      -> línea del plano decorativa, sin línea de cámara (compat).
--   * NOT NULL  -> la misma línea representada en la foto y en el plano.

ALTER TABLE `lineas_plano`
  ADD COLUMN `linea_id` INT UNSIGNED NULL
    COMMENT 'FK a lineas: la misma línea representada en la foto de cámara'
    AFTER `camara_id`,
  ADD UNIQUE KEY `uq_lineas_plano_linea` (`linea_id`);
