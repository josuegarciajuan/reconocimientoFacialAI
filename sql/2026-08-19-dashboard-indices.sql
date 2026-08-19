-- Migración 2026-08-19: índices de soporte para el nuevo dashboard (vista de pájaro).
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-dashboard-indices.sql
--
-- El dashboard agrega por persona/cámara/fecha (estancias, cruces_lineas, videos).
-- Sin estos índices las consultas de "Almas Dentro", "Feed en vivo", "Heatmap"
-- y "Ranking" degeneran en escaneos completos según crezca el histórico.

-- Nota: idx_estancias_video, idx_cruces_video, idx_cruces_persona e
-- idx_videos_local_fecha ya existen (migraciones de vínculos/vídeos).

CREATE INDEX idx_estancias_fecha_ini  ON estancias (fecha_ini);
CREATE INDEX idx_estancias_camara     ON estancias (camara_id);
CREATE INDEX idx_estancias_persona    ON estancias (persona_id);
CREATE INDEX idx_cruces_fecha         ON cruces_lineas (fecha);
CREATE INDEX idx_videos_fecha_ini     ON videos (fecha_ini);
CREATE INDEX idx_videos_camara        ON videos (camara_id);
