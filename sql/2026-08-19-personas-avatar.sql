-- Migración 2026-08-19: avatar por persona (cabeza recortada con fondo
-- transparente para el monigote de los Caminos).
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-personas-avatar.sql
--
-- `personas_avatar` guarda la foto elegida como "mejor cara frontal" y la
-- ruta del PNG generado (motor/core/avatar.py) con el recorte de cabeza y
-- canal alfa. El PNG vive en admin/caras_procesadas/avatares/{persona_id}.png.

CREATE TABLE IF NOT EXISTS `personas_avatar` (
  `persona_id` INT NOT NULL,
  `foto_id`    INT NOT NULL DEFAULT 0,
  `png`        VARCHAR(255) NOT NULL DEFAULT '',
  `updated`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`persona_id`),
  KEY `idx_avatar_foto` (`foto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Avatar recortado (cabeza transparente) por persona';
