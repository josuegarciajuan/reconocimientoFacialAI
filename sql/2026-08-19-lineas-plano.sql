-- Migración 2026-08-19: líneas del plano (independientes de los triples de foto).
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-lineas-plano.sql
--
-- Líneas dibujadas sobre el PLANO del local (La Forja → Trazos → Plano).
-- Son independientes de la tabla `lineas` (triples de vigilancia sobre la foto
-- de una cámara): cada una tiene nombre propio y se asigna a una cámara del
-- local solo para organizarlas/identificarlas en el listado.
-- Coordenadas x1/y1/x2/y2 en píxeles del lienzo (750x562), igual que cámaras y nodos.

CREATE TABLE IF NOT EXISTS `lineas_plano` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `camara_id` INT NOT NULL DEFAULT 0
      COMMENT 'cámara a la que se asigna la línea (solo identificativa)',
  `nombre` VARCHAR(255) DEFAULT NULL,
  `x1` INT NOT NULL DEFAULT 0,
  `y1` INT NOT NULL DEFAULT 0,
  `x2` INT NOT NULL DEFAULT 0,
  `y2` INT NOT NULL DEFAULT 0,
  `eliminada` TINYINT NOT NULL DEFAULT 0,
  `created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_lineas_plano_camara` (`camara_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Líneas dibujadas sobre el plano del local';
