-- Migración 2026-08-19: miniatura (poster) de los vídeos de movimiento.
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-videos-poster.sql
--
-- Un frame del MP4 (motor/archiva_video.py -> motor/core/video.py extraer_poster)
-- se guarda como JPG junto al vídeo y su ruta relativa se registra aquí para
-- mostrarlo como miniatura en la UI (video.php?id=<id>&poster=1).

ALTER TABLE `videos`
    ADD COLUMN `poster` VARCHAR(1024) DEFAULT NULL
    COMMENT 'ruta relativa del JPG miniatura (motor/videos_archivo/...)'
    AFTER `ruta`;
