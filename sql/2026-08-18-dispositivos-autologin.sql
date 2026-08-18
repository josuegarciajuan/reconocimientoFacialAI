-- Migración 2026-08-18: auto-login por dispositivo (matrícula única).
-- Aplicar en la BD reconociendofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-18-dispositivos-autologin.sql
--
-- Garantía "solo ese dispositivo": el código (libs/autologin.php) solo matricula
-- si NO existe fila activa, así que como máximo hay UNA fila con activo=1.
-- Revocación: UPDATE dispositivos_autologin SET activo = 0 WHERE id = <id>;

CREATE TABLE IF NOT EXISTS `dispositivos_autologin` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `token_hash` CHAR(64) NOT NULL COMMENT 'sha256 del token aleatorio del dispositivo',
  `ip` VARCHAR(45) NOT NULL COMMENT 'IP desde la que se matriculó el dispositivo',
  `local_id` INT UNSIGNED NOT NULL DEFAULT 1,
  `admin` TINYINT(1) NOT NULL DEFAULT 1,
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `creado_en` DATETIME NOT NULL,
  `ultimo_uso` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Matrícula única de auto-login por dispositivo';
