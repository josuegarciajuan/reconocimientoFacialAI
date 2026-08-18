-- Migración 2026-08-19: horario de trabajo por local + tabla de fichajes conciliados.
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-horarios-fichajes.sql
--
-- Horario habitual (único, todos los días):
--   * jornada_partida: 0 = jornada continua (1 bloque), 1 = partida (hasta 2 bloques).
--   * hora_entrada1 / hora_salida1: bloque de mañana.
--   * hora_entrada2 / hora_salida2: bloque de tarde (solo con jornada partida).
--   * margen_fichaje_min: tolerancia en minutos para las ventanas de horario.
--   * Sin horario (todo NULL) => comportamiento legacy: 1 entrada (1er cruce por
--     cámara puerta) y 1 salida (último cruce por cámara salida) al día.

ALTER TABLE `locales`
    ADD COLUMN `jornada_partida` TINYINT NOT NULL DEFAULT 0
        COMMENT '0 = jornada continua, 1 = jornada partida (2 bloques)',
    ADD COLUMN `hora_entrada1` TIME DEFAULT NULL
        COMMENT 'hora habitual de entrada (bloque 1)',
    ADD COLUMN `hora_salida1` TIME DEFAULT NULL
        COMMENT 'hora habitual de salida (bloque 1)',
    ADD COLUMN `hora_entrada2` TIME DEFAULT NULL
        COMMENT 'hora habitual de entrada (bloque 2, jornada partida)',
    ADD COLUMN `hora_salida2` TIME DEFAULT NULL
        COMMENT 'hora habitual de salida (bloque 2, jornada partida)',
    ADD COLUMN `margen_fichaje_min` INT NOT NULL DEFAULT 30
        COMMENT 'margen en minutos para las ventanas de horario';

-- Fichajes conciliados por trabajador, día y bloque.
-- El daemon conciliador.php (rf-conciliador) los calcula desde `estancias`
-- (cámaras puerta/salida) según el horario del local y los mantiene con
-- upsert idempotente: provisional durante el día y conciliado al cerrarse.
CREATE TABLE IF NOT EXISTS `fichajes` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `local_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `persona_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `fecha` DATE NOT NULL,
  `bloque` TINYINT UNSIGNED NOT NULL DEFAULT 1
      COMMENT '1 = mañana, 2 = tarde (solo si jornada partida)',
  `entrada_estancia_id` INT UNSIGNED DEFAULT NULL,
  `entrada_hora` DATETIME DEFAULT NULL,
  `entrada_camara_id` INT UNSIGNED DEFAULT NULL,
  `salida_estancia_id` INT UNSIGNED DEFAULT NULL,
  `salida_hora` DATETIME DEFAULT NULL,
  `salida_camara_id` INT UNSIGNED DEFAULT NULL,
  `estado` ENUM('provisional','conciliado') NOT NULL DEFAULT 'provisional',
  `creado` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizado` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_persona_dia_bloque` (`persona_id`, `fecha`, `bloque`),
  KEY `idx_fichajes_local_fecha` (`local_id`, `fecha`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Fichajes conciliados por trabajador, día y bloque';
