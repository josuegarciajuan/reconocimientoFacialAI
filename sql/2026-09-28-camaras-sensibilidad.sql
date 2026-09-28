-- Fase 1 (recall): sensibilidad del disparador POR CÁMARA.
-- Idempotente (deploy_prod.sh aplica solo migraciones nuevas con `mysql < f`).
-- Las columnas NULL/'': capturador.php envía -1 y guarda_movimientosV3 usa el
-- global de .env (RF_MOV_*) o el default del código.

ALTER TABLE camaras ADD COLUMN IF NOT EXISTS threshold INT NULL;
ALTER TABLE camaras ADD COLUMN IF NOT EXISTS blur INT NULL;
ALTER TABLE camaras ADD COLUMN IF NOT EXISTS dilate INT NULL;
ALTER TABLE camaras ADD COLUMN IF NOT EXISTS seg_antes INT NULL;
ALTER TABLE camaras ADD COLUMN IF NOT EXISTS seg_despues INT NULL;

-- Cámaras que siguen con los valores de fábrica antiguos (60/220) pasan a los
-- nuevos defaults más sensibles. Las que el operador ya ajustó NO se tocan.
UPDATE camaras SET porcentaje_mov = 35 WHERE porcentaje_mov = 60;
UPDATE camaras SET dontCare = 120 WHERE dontCare = 220;
