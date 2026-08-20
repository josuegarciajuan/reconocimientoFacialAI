-- Migración 2026-08-20: sistema de alarmas de inactividad ("La Almenara").
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-20-alarmas.sql
--
-- Concepto:
--   * Cada LOCAL puede tener una ventana de "inactividad" (alarma_hora_inicio/fin,
--     admite cruce de medianoche). Dentro de esa ventana, cualquier movimiento en
--     cualquier cámara del local dispara una alarma.
--   * Cada CÁMARA hereda el horario del local (alarma_heredar=1) o define el suyo
--     propio. `alarma_24h` = "actividad 24h": nunca alarma.
--   * Al disparar una alarma se abre una ventana de "asedio" (alarma_boost_hasta):
--     todas las cámaras del local graban en continuo y afinan el umbral de
--     detección para capturar cualquier mínimo movimiento (leído por
--     guarda_movimientosV3.py vía ws.php).
--   * `alarmas` guarda cada evento (cooldown + escalada aviso→asedio en libs/alarmas.php).
--   * `alarmas_telefonos` prepara el envío WhatsApp futuro (canal stub en
--     libs/notificador.php).

ALTER TABLE `locales`
    ADD COLUMN `alarma_activa` TINYINT NOT NULL DEFAULT 0
        COMMENT 'interruptor maestro del sistema de alarmas del local',
    ADD COLUMN `alarma_hora_inicio` TIME DEFAULT NULL
        COMMENT 'inicio de la ventana de inactividad (cruce de medianoche permitido)',
    ADD COLUMN `alarma_hora_fin` TIME DEFAULT NULL
        COMMENT 'fin de la ventana de inactividad',
    ADD COLUMN `alarma_24h` TINYINT NOT NULL DEFAULT 0
        COMMENT '1 = actividad 24h: el local nunca alarma',
    ADD COLUMN `alarma_margen_min` INT NOT NULL DEFAULT 0
        COMMENT 'minutos de gracia tras el inicio de la inactividad (último en salir)',
    ADD COLUMN `alarma_boost_hasta` DATETIME DEFAULT NULL
        COMMENT 'hasta cuándo las cámaras del local graban en continuo (modo asedio)';

ALTER TABLE `camaras`
    ADD COLUMN `alarma_heredar` TINYINT NOT NULL DEFAULT 1
        COMMENT '1 = hereda el horario de inactividad del local, 0 = horario propio',
    ADD COLUMN `alarma_hora_inicio` TIME DEFAULT NULL
        COMMENT 'inicio de inactividad propio (solo si alarma_heredar=0)',
    ADD COLUMN `alarma_hora_fin` TIME DEFAULT NULL
        COMMENT 'fin de inactividad propio (solo si alarma_heredar=0)',
    ADD COLUMN `alarma_24h` TINYINT NOT NULL DEFAULT 0
        COMMENT '1 = actividad 24h: esta cámara nunca alarma';

CREATE TABLE IF NOT EXISTS `alarmas` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `local_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `camara_id` INT UNSIGNED DEFAULT NULL
      COMMENT 'cámara que detectó el movimiento (NULL = alarma a nivel de local)',
  `video_id` INT UNSIGNED DEFAULT NULL
      COMMENT 'vídeo de movimiento asociado (lo rellena el vinculador)',
  `fecha` DATETIME NOT NULL,
  `severidad` ENUM('aviso','asedio') NOT NULL DEFAULT 'aviso'
      COMMENT 'aviso = primer movimiento; asedio = actividad sostenida/repetición',
  `eventos` INT UNSIGNED NOT NULL DEFAULT 1
      COMMENT 'disparos agrupados por cooldown; al superar el umbral escala a asedio',
  `origen` ENUM('camara','local') NOT NULL DEFAULT 'camara',
  `mensaje` VARCHAR(1024) DEFAULT NULL,
  `notificacion_vista` TINYINT NOT NULL DEFAULT 0,
  `created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_alarmas_local_fecha` (`local_id`, `fecha`),
  KEY `idx_alarmas_camara` (`camara_id`),
  KEY `idx_alarmas_video` (`video_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Alarmas de inactividad disparadas (La Almenara)';

CREATE TABLE IF NOT EXISTS `alarmas_telefonos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `local_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `nombre` VARCHAR(255) DEFAULT NULL,
  `telefono` VARCHAR(32) NOT NULL,
  `activo` TINYINT NOT NULL DEFAULT 1,
  `created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_alarmas_telefonos_local` (`local_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Teléfonos de recepción de alarmas (WhatsApp futuro)';
