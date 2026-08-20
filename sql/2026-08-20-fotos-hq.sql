-- Fotos HQ progresivas (mejora de resolución, fase busto+hq).
-- La foto final se publica primero en calidad rápida (compact, aparece al instante)
-- y ~35-40 s después un hilo de fondo genera la versión HQ (x4plus) que sobreescribe
-- el mismo fichero. `generada_hq` permite al panel "autonitidar" la imagen sin recargar.
ALTER TABLE fotos ADD COLUMN generada_hq TINYINT(1) NOT NULL DEFAULT 0;
