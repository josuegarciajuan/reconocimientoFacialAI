-- Migración 2026-08-19: plano del local dual (imagen subida + croquis dibujado).
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-plano-dibujo.sql
--
-- El local puede tener DOS planos guardados en pages/config/planos/:
--   * plano_<local_id>.<ext>        -> imagen subida (comportamiento legacy).
--   * plano_dibujo_<local_id>.png   -> croquis dibujado a mano alzada.
-- `plano_activo` decide cuál se muestra/usa (canvas de La Forja, rutas, etc.):
--   'subida' (default) o 'dibujo'. La resolución del archivo la hace libs/planos.php
--   (plano_url()), con fallback al otro plano si el activo no existe.

ALTER TABLE `locales`
    ADD COLUMN `plano_activo` ENUM('subida','dibujo') NOT NULL DEFAULT 'subida'
        COMMENT 'plano usado como fondo: subida (imagen) o dibujo (croquis)';
