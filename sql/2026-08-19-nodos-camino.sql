-- Migración 2026-08-19: caminos múltiples entre el mismo par de cámaras (nodos).
-- Aplicar en la BD reconocimientofacial:
--   mysql -uroot reconocimientofacial < sql/2026-08-19-nodos-camino.sql
--
-- Un mismo par de cámaras puede tener varios caminos reales (p. ej. los dos arcos
-- de un pasillo en anillo). `camino` discrimina cada cadena de nodos:
--   0 = principal (comportamiento previo), 1..N = caminos alternativos.
-- La columna es aditiva con DEFAULT 0: los nodos existentes pasan a ser el camino 0.

ALTER TABLE `nodos`
    ADD COLUMN `camino` TINYINT NOT NULL DEFAULT 0
        COMMENT 'camino entre el par de cámaras: 0=principal, 1..N=alternativos'
        AFTER `orden`;
