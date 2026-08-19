-- Migración 2026-08-19: grafo de senderos para La Forja / Caminos.
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-senderos.sql
--
-- Nuevo modelo de recorridos (sustituye al concepto de cadenas cámara→cámara):
--   * NODO del grafo:
--       - tipo 'camara'      -> cámara SIN líneas configuradas.
--       - tipo 'linea_plano' -> línea de cámara colocada en el plano (punto medio).
--     Las cámaras CON líneas NO son nodos: sus líneas (sobre el plano) sí.
--   * SENDERO (arista): conexión entre dos nodos, con estilo recto/ortogonal/curvo.
--     senderos_puntos guarda SOLO puntos intermedios; los extremos se derivan
--     de la posición de los nodos en el momento de dibujar.
--
-- Compleción:
--   * camaras.colocada = 1 cuando la cámara se arrastra al plano en El Yunque.
--   * Una cámara está "completa" si no tiene líneas o todas sus líneas tienen
--     representación en lineas_plano (linea_id vinculado).

ALTER TABLE `camaras`
    ADD COLUMN `colocada` TINYINT NOT NULL DEFAULT 0
        COMMENT '1 si la cámara ya se ha arrastrado al plano en El Yunque';

-- Backfill: cámaras que ya tenían posición X/Y se consideran colocadas.
UPDATE `camaras` SET `colocada` = 1 WHERE `x` <> 0 OR `y` <> 0;

CREATE TABLE IF NOT EXISTS `senderos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `local_id` INT NOT NULL DEFAULT 0,
  `origen_tipo` ENUM('camara','linea_plano') NOT NULL,
  `origen_id` INT NOT NULL,
  `destino_tipo` ENUM('camara','linea_plano') NOT NULL,
  `destino_id` INT NOT NULL,
  `estilo` ENUM('recto','ortogonal','curvo') NOT NULL DEFAULT 'recto',
  `nombre` VARCHAR(255) DEFAULT NULL,
  `created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_senderos_local` (`local_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1
  COMMENT='Aristas del grafo de senderos (nodos = cámaras sin líneas o líneas de plano)';

CREATE TABLE IF NOT EXISTS `senderos_puntos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `sendero_id` INT UNSIGNED NOT NULL,
  `x` INT NOT NULL,
  `y` INT NOT NULL,
  `orden` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_senderos_puntos_sendero` (`sendero_id`, `orden`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1
  COMMENT='Puntos intermedios de cada sendero (extremos derivados de los nodos)';

-- Migración de cadenas legacy `nodos` (cámara→cámara) a senderos curvos.
-- Solo se migran pares donde AMBAS cámaras no tienen líneas (ahora nodos-cámara).
-- El resto se descarta: se reconectan a mano en El Yunque.
INSERT INTO `senderos` (`local_id`, `origen_tipo`, `origen_id`, `destino_tipo`, `destino_id`, `estilo`, `nombre`)
SELECT c1.local_id, 'camara', n.camara_id1, 'camara', n.camara_id2, 'curvo',
       CONCAT('sendero ', n.camara_id1, '-', n.camara_id2)
FROM (SELECT DISTINCT camara_id1, camara_id2, camino FROM nodos) n
JOIN camaras c1 ON c1.id = n.camara_id1
JOIN camaras c2 ON c2.id = n.camara_id2
WHERE c1.local_id = c2.local_id
  AND NOT EXISTS (SELECT 1 FROM lineas l WHERE l.camara_id = n.camara_id1 AND l.eliminada = 0)
  AND NOT EXISTS (SELECT 1 FROM lineas l WHERE l.camara_id = n.camara_id2 AND l.eliminada = 0);

-- Puntos intermedios de los senderos migrados: se excluyen el primer y el
-- último punto de cada cadena (son los anclajes de las cámaras, ya derivados).
INSERT INTO `senderos_puntos` (`sendero_id`, `x`, `y`, `orden`)
SELECT s.id, n.x, n.y, n.orden
FROM senderos s
JOIN nodos n ON (
     (n.camara_id1 = s.origen_id AND n.camara_id2 = s.destino_id)
  OR (n.camara_id1 = s.destino_id AND n.camara_id2 = s.origen_id)
)
WHERE s.origen_tipo = 'camara' AND s.destino_tipo = 'camara'
  AND n.orden > 1
  AND n.orden < (SELECT MAX(n2.orden) FROM nodos n2
                 WHERE (n2.camara_id1 = s.origen_id AND n2.camara_id2 = s.destino_id)
                    OR (n2.camara_id1 = s.destino_id AND n2.camara_id2 = s.origen_id))
ORDER BY s.id, n.orden ASC;
