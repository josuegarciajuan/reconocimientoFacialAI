-- Proveniencia de imagen: conserva las dimensiones nativas y evita presentar
-- un top-up CSS/legacy como resolución capturada.
ALTER TABLE fotos
  ADD COLUMN original_width INT UNSIGNED NULL,
  ADD COLUMN original_height INT UNSIGNED NULL,
  ADD COLUMN processed_width INT UNSIGNED NULL,
  ADD COLUMN processed_height INT UNSIGNED NULL,
  ADD COLUMN original_face_width INT UNSIGNED NULL,
  ADD COLUMN original_face_height INT UNSIGNED NULL,
  ADD COLUMN original_sharpness DECIMAL(12,3) NULL,
  ADD COLUMN quality_label VARCHAR(16) NULL,
  ADD COLUMN sr_applied TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN display_upscaled TINYINT(1) NOT NULL DEFAULT 0;
