-- Migración 2026-08-18: registro de vídeos de movimiento archivados.
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-18-tabla-videos.sql
--
-- Cada movimiento capturado por guarda_movimientosV3.py se comprime a MP4 H.264
-- (motor/archiva_video.py) y se registra aquí para poder enlazarlo desde la UI
-- (video.php?id=<id>) y purgarlo por retención (borrar_videos_antiguos).

CREATE TABLE IF NOT EXISTS `videos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `local_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `camara_id` INT UNSIGNED NOT NULL DEFAULT 0,
  `nombre` VARCHAR(255) NOT NULL COMMENT 'nombre del fichero .mp4',
  `ruta` VARCHAR(1024) NOT NULL COMMENT 'ruta relativa a la raíz (motor/videos_archivo/...)',
  `fecha_ini` DATETIME NOT NULL COMMENT 'inicio del movimiento (del nombre del AVI)',
  `fecha_fin` DATETIME DEFAULT NULL,
  `duracion` FLOAT NOT NULL DEFAULT 0 COMMENT 'segundos',
  `peso` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'bytes del MP4',
  `fps` FLOAT NOT NULL DEFAULT 10,
  `ancho` INT UNSIGNED NOT NULL DEFAULT 0,
  `alto` INT UNSIGNED NOT NULL DEFAULT 0,
  `creado` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_videos_local_fecha` (`local_id`, `camara_id`, `fecha_ini`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Vídeos de movimiento comprimidos (H.264)';
