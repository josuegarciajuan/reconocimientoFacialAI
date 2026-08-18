-- Migración 2026-08-19: vínculos automáticos vídeos ↔ estancias (personas) ↔ cruces de línea.
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-vinculos-videos-cruces.sql
--
-- FKs NULLABLES (no siempre es posible el vínculo mutuo; lo rellena el daemon
-- vinculador.php vía libs/vinculos.php por cámara + solape temporal):
--   * estancias.video_id        -> vídeo de movimiento del que derivan sus fotos.
--   * cruces_lineas.video_id    -> vídeo donde se detectó el cruce.
--   * cruces_lineas.persona_id  -> persona a la que se atribuye el cruce (vía la
--                                  estancia del mismo vídeo que cubre el cruce).
--
-- No se re-extraen caras para vincular: solo si un vídeo no tiene NINGUNA estancia
-- se marca para re-estudio (caso raro: movimiento sin cara reconocible).

ALTER TABLE `estancias`
    ADD COLUMN `video_id` INT UNSIGNED DEFAULT NULL
        COMMENT 'vídeo de movimiento (tabla videos) del que derivan las fotos de esta estancia'
        AFTER `camara_id`,
    ADD KEY `idx_estancias_video` (`video_id`);

ALTER TABLE `cruces_lineas`
    ADD COLUMN `video_id` INT UNSIGNED DEFAULT NULL
        COMMENT 'vídeo de movimiento (tabla videos) donde se detectó el cruce'
        AFTER `linea_id`,
    ADD COLUMN `persona_id` INT UNSIGNED DEFAULT NULL
        COMMENT 'persona a la que se atribuye el cruce (estancia del mismo vídeo que cubre la fecha)'
        AFTER `video_id`,
    ADD KEY `idx_cruces_video` (`video_id`),
    ADD KEY `idx_cruces_persona` (`persona_id`);
