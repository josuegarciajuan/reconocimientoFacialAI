-- 2026-08-20: journal de calibración / restauración (La Forja · Templar).
--
-- Registra cada cambio aplicado (o restauración) de parámetros de análisis,
-- por cámara o globales, con su valor ANTERIOR para poder deshacer
-- (mismo criterio reversible que motor/core/calibration.py).
--
-- git = código, no datos: la BD es runtime y no se versiona.

CREATE TABLE IF NOT EXISTS calibraciones (
  id INT NOT NULL AUTO_INCREMENT,
  local_id INT NOT NULL DEFAULT 0,
  camara_id INT NOT NULL DEFAULT 0,              -- 0 = global
  ambito VARCHAR(16) NOT NULL DEFAULT 'camara',  -- 'camara' | 'global'
  parametro VARCHAR(64) NOT NULL,
  antes VARCHAR(255) DEFAULT NULL,
  despues VARCHAR(255) DEFAULT NULL,
  aplicado TINYINT(1) NOT NULL DEFAULT 1,
  fecha TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_calib_camara (camara_id, parametro),
  KEY idx_calib_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
