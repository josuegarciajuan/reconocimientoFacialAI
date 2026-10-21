
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `alarmas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alarmas` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `local_id` int unsigned NOT NULL DEFAULT '0',
  `camara_id` int unsigned DEFAULT NULL COMMENT 'cámara que detectó el movimiento (NULL = alarma a nivel de local)',
  `video_id` int unsigned DEFAULT NULL COMMENT 'vídeo de movimiento asociado (lo rellena el vinculador)',
  `fecha` datetime NOT NULL,
  `severidad` enum('aviso','asedio') NOT NULL DEFAULT 'aviso' COMMENT 'aviso = primer movimiento; asedio = actividad sostenida/repetición',
  `eventos` int unsigned NOT NULL DEFAULT '1' COMMENT 'disparos agrupados por cooldown; al superar el umbral escala a asedio',
  `origen` enum('camara','local') NOT NULL DEFAULT 'camara',
  `mensaje` varchar(1024) DEFAULT NULL,
  `notificacion_vista` tinyint NOT NULL DEFAULT '0',
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_alarmas_local_fecha` (`local_id`,`fecha`),
  KEY `idx_alarmas_camara` (`camara_id`),
  KEY `idx_alarmas_video` (`video_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Alarmas de inactividad disparadas (La Almenara)';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `alarmas_telefonos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alarmas_telefonos` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `local_id` int unsigned NOT NULL DEFAULT '0',
  `nombre` varchar(255) DEFAULT NULL,
  `telefono` varchar(32) NOT NULL,
  `activo` tinyint NOT NULL DEFAULT '1',
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_alarmas_telefonos_local` (`local_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Teléfonos de recepción de alarmas (WhatsApp futuro)';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `calibraciones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `calibraciones` (
  `id` int NOT NULL AUTO_INCREMENT,
  `local_id` int NOT NULL DEFAULT '0',
  `camara_id` int NOT NULL DEFAULT '0',
  `ambito` varchar(16) NOT NULL DEFAULT 'camara',
  `parametro` varchar(64) NOT NULL,
  `antes` varchar(255) DEFAULT NULL,
  `despues` varchar(255) DEFAULT NULL,
  `aplicado` tinyint(1) NOT NULL DEFAULT '1',
  `fecha` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_calib_camara` (`camara_id`,`parametro`),
  KEY `idx_calib_fecha` (`fecha`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `camaras`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `camaras` (
  `id` int NOT NULL AUTO_INCREMENT,
  `local_id` int DEFAULT '0',
  `descripcion` varchar(1024) DEFAULT NULL,
  `directorio` varchar(255) DEFAULT NULL,
  `url_conexion` varchar(255) DEFAULT NULL,
  `sistema` int DEFAULT '0',
  `x` int DEFAULT '0',
  `y` int DEFAULT '0',
  `puerta` int DEFAULT '0',
  `salida` int DEFAULT '0',
  `encendida` int DEFAULT '0',
  `ipcamlive_alias` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `segundos_analizar` int DEFAULT '3',
  `porcentaje_mov` int DEFAULT '80',
  `dontCare` int DEFAULT '220',
  `fps` int DEFAULT '15',
  `maximo_videos` int DEFAULT '60',
  `redimesionframe` int DEFAULT '60',
  `sensibilidad` int DEFAULT '1',
  `url_desdeserver` varchar(255) DEFAULT NULL,
  `orden` int NOT NULL DEFAULT '0' COMMENT 'posición en la rejilla de El Ojo en Vivo (arrastrar y soltar)',
  `colocada` tinyint NOT NULL DEFAULT '0' COMMENT '1 si la cámara ya se ha arrastrado al plano en El Yunque',
  `alarma_heredar` tinyint NOT NULL DEFAULT '1' COMMENT '1 = hereda el horario de inactividad del local, 0 = horario propio',
  `alarma_hora_inicio` time DEFAULT NULL COMMENT 'inicio de inactividad propio (solo si alarma_heredar=0)',
  `alarma_hora_fin` time DEFAULT NULL COMMENT 'fin de inactividad propio (solo si alarma_heredar=0)',
  `alarma_24h` tinyint NOT NULL DEFAULT '0' COMMENT '1 = actividad 24h: esta cámara nunca alarma',
  `threshold` int DEFAULT NULL,
  `blur` int DEFAULT NULL,
  `dilate` int DEFAULT NULL,
  `seg_antes` int DEFAULT NULL,
  `seg_despues` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_camaras_local_orden` (`local_id`,`orden`)
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cruces_lineas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cruces_lineas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `linea_id` int DEFAULT '0',
  `video_id` int unsigned DEFAULT NULL COMMENT 'vídeo de movimiento (tabla videos) donde se detectó el cruce',
  `persona_id` int unsigned DEFAULT NULL COMMENT 'persona a la que se atribuye el cruce (estancia del mismo vídeo que cubre la fecha)',
  `fecha` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `direccion` int DEFAULT '0',
  `x_cruce` int DEFAULT '0',
  `y_cruce` int DEFAULT '0',
  `identificador` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cruces_video` (`video_id`),
  KEY `idx_cruces_persona` (`persona_id`),
  KEY `idx_cruces_fecha` (`fecha`)
) ENGINE=InnoDB AUTO_INCREMENT=559 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `dispositivos_autologin`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dispositivos_autologin` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `token_hash` char(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'sha256 del token aleatorio del dispositivo',
  `ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'IP desde la que se matriculó el dispositivo',
  `local_id` int unsigned NOT NULL DEFAULT '1',
  `admin` tinyint(1) NOT NULL DEFAULT '1',
  `activo` tinyint(1) NOT NULL DEFAULT '1',
  `creado_en` datetime NOT NULL,
  `ultimo_uso` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Matrícula única de auto-login por dispositivo';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `estancias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `estancias` (
  `id` int NOT NULL AUTO_INCREMENT,
  `persona_id` int DEFAULT '0',
  `camara_id` int DEFAULT '0',
  `video_id` int unsigned DEFAULT NULL COMMENT 'vídeo de movimiento (tabla videos) del que derivan las fotos de esta estancia',
  `fecha_ini` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_fin` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `notificacion_vista` int DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_estancias_video` (`video_id`),
  KEY `idx_estancias_fecha_ini` (`fecha_ini`),
  KEY `idx_estancias_camara` (`camara_id`),
  KEY `idx_estancias_persona` (`persona_id`),
  KEY `idx_estancias_cam_fecha` (`camara_id`,`fecha_fin`)
) ENGINE=InnoDB AUTO_INCREMENT=658 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `fichajes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fichajes` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `local_id` int unsigned NOT NULL DEFAULT '0',
  `persona_id` int unsigned NOT NULL DEFAULT '0',
  `fecha` date NOT NULL,
  `bloque` tinyint unsigned NOT NULL DEFAULT '1' COMMENT '1 = mañana, 2 = tarde (solo si jornada partida)',
  `entrada_estancia_id` int unsigned DEFAULT NULL,
  `entrada_hora` datetime DEFAULT NULL,
  `entrada_camara_id` int unsigned DEFAULT NULL,
  `salida_estancia_id` int unsigned DEFAULT NULL,
  `salida_hora` datetime DEFAULT NULL,
  `salida_camara_id` int unsigned DEFAULT NULL,
  `estado` enum('provisional','conciliado') NOT NULL DEFAULT 'provisional',
  `creado` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizado` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_persona_dia_bloque` (`persona_id`,`fecha`,`bloque`),
  KEY `idx_fichajes_local_fecha` (`local_id`,`fecha`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Fichajes conciliados por trabajador, día y bloque';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `foto_audit_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `foto_audit_events` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `foto_id` int NOT NULL,
  `event_key` varchar(160) NOT NULL,
  `event_type` varchar(32) NOT NULL,
  `camera_id` varchar(64) NOT NULL,
  `from_person_code` varchar(255) DEFAULT NULL,
  `to_person_code` varchar(255) DEFAULT NULL,
  `event_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_foto_audit_event_key` (`event_key`),
  KEY `idx_foto_audit_events_foto` (`foto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `foto_audit_events_no_mutation` BEFORE UPDATE ON `foto_audit_events` FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audit_events is append-only'; END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `foto_audit_events_no_delete` BEFORE DELETE ON `foto_audit_events` FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audit_events is append-only'; END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
DROP TABLE IF EXISTS `foto_audits`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `foto_audits` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `foto_id` int DEFAULT NULL,
  `correlation_id` varchar(255) NOT NULL,
  `schema_version` varchar(32) NOT NULL,
  `local_id` varchar(64) NOT NULL,
  `camera_id` varchar(64) NOT NULL,
  `classification` varchar(16) NOT NULL,
  `classification_phase` varchar(16) NOT NULL DEFAULT 'initial',
  `person_code` varchar(255) DEFAULT NULL,
  `layers_json` text NOT NULL,
  `attributes_json` text,
  `classified_at` double NOT NULL,
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_foto_audit_correlation` (`correlation_id`),
  KEY `idx_foto_audit_foto` (`foto_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1034 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `foto_audits_no_mutation` BEFORE UPDATE ON `foto_audits` FOR EACH ROW BEGIN
  IF NOT (OLD.foto_id IS NULL AND NEW.foto_id IS NOT NULL
    AND OLD.correlation_id = NEW.correlation_id AND OLD.schema_version = NEW.schema_version
    AND OLD.local_id = NEW.local_id AND OLD.camera_id = NEW.camera_id
    AND OLD.classification = NEW.classification AND OLD.classification_phase = NEW.classification_phase
    AND (OLD.person_code <=> NEW.person_code) AND OLD.layers_json = NEW.layers_json
    AND (OLD.attributes_json <=> NEW.attributes_json) AND OLD.classified_at = NEW.classified_at) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audits is append-only';
  END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `foto_audits_no_delete` BEFORE DELETE ON `foto_audits` FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'foto_audits is append-only'; END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
DROP TABLE IF EXISTS `fotos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fotos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `estancia_id` int DEFAULT '0',
  `nombre_real_antesconversion` varchar(255) DEFAULT NULL,
  `identificador_unico` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `generada_hq` tinyint(1) NOT NULL DEFAULT '0',
  `original_width` int unsigned DEFAULT NULL,
  `original_height` int unsigned DEFAULT NULL,
  `processed_width` int unsigned DEFAULT NULL,
  `processed_height` int unsigned DEFAULT NULL,
  `original_face_width` int unsigned DEFAULT NULL,
  `original_face_height` int unsigned DEFAULT NULL,
  `original_sharpness` decimal(12,3) DEFAULT NULL,
  `quality_label` varchar(16) DEFAULT NULL,
  `sr_applied` tinyint(1) NOT NULL DEFAULT '0',
  `display_upscaled` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_fotos_estancia` (`estancia_id`),
  KEY `idx_fotos_nombre` (`nombre_real_antesconversion`(191))
) ENGINE=InnoDB AUTO_INCREMENT=1034 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `lineas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lineas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `camara_id` int DEFAULT '0',
  `nombre` varchar(255) DEFAULT NULL,
  `x1` float DEFAULT '0',
  `y1` float DEFAULT '0',
  `x2` float DEFAULT '0',
  `y2` float DEFAULT '0',
  `eliminada` int DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `lineas_plano`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lineas_plano` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `camara_id` int NOT NULL DEFAULT '0' COMMENT 'cámara a la que se asigna la línea (solo identificativa)',
  `linea_id` int unsigned DEFAULT NULL COMMENT 'FK a lineas: la misma línea representada en la foto de cámara',
  `nombre` varchar(255) DEFAULT NULL,
  `x1` int NOT NULL DEFAULT '0',
  `y1` int NOT NULL DEFAULT '0',
  `x2` int NOT NULL DEFAULT '0',
  `y2` int NOT NULL DEFAULT '0',
  `eliminada` tinyint NOT NULL DEFAULT '0',
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_lineas_plano_linea` (`linea_id`),
  KEY `idx_lineas_plano_camara` (`camara_id`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=latin1 COMMENT='Líneas dibujadas sobre el plano del local';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `locales`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `locales` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(255) DEFAULT NULL,
  `url_logo` varchar(255) DEFAULT NULL,
  `aforo_max` int DEFAULT NULL,
  `aforo_actual` int DEFAULT '0',
  `usuario` varchar(255) DEFAULT NULL,
  `passw` varchar(255) DEFAULT NULL,
  `directorio` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `jornada_partida` tinyint NOT NULL DEFAULT '0' COMMENT '0 = jornada continua, 1 = jornada partida (2 bloques)',
  `hora_entrada1` time DEFAULT NULL COMMENT 'hora habitual de entrada (bloque 1)',
  `hora_salida1` time DEFAULT NULL COMMENT 'hora habitual de salida (bloque 1)',
  `hora_entrada2` time DEFAULT NULL COMMENT 'hora habitual de entrada (bloque 2, jornada partida)',
  `hora_salida2` time DEFAULT NULL COMMENT 'hora habitual de salida (bloque 2, jornada partida)',
  `margen_fichaje_min` int NOT NULL DEFAULT '30' COMMENT 'margen en minutos para las ventanas de horario',
  `plano_activo` enum('subida','dibujo') NOT NULL DEFAULT 'subida' COMMENT 'plano usado como fondo: subida (imagen) o dibujo (croquis)',
  `alarma_activa` tinyint NOT NULL DEFAULT '0' COMMENT 'interruptor maestro del sistema de alarmas del local',
  `alarma_hora_inicio` time DEFAULT NULL COMMENT 'inicio de la ventana de inactividad (cruce de medianoche permitido)',
  `alarma_hora_fin` time DEFAULT NULL COMMENT 'fin de la ventana de inactividad',
  `alarma_24h` tinyint NOT NULL DEFAULT '0' COMMENT '1 = actividad 24h: el local nunca alarma',
  `alarma_margen_min` int NOT NULL DEFAULT '0' COMMENT 'minutos de gracia tras el inicio de la inactividad (último en salir)',
  `alarma_boost_hasta` datetime DEFAULT NULL COMMENT 'hasta cuándo las cámaras del local graban en continuo (modo asedio)',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `nodos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `nodos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `camara_id1` int DEFAULT '0',
  `camara_id2` int DEFAULT '0',
  `x` int DEFAULT '0',
  `y` int DEFAULT '0',
  `orden` int DEFAULT '0',
  `camino` tinyint NOT NULL DEFAULT '0' COMMENT 'camino entre el par de cámaras: 0=principal, 1..N=alternativos',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `personas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `personas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `local_id` varchar(255) DEFAULT NULL,
  `nombre` varchar(1024) DEFAULT '',
  `cod_interno` varchar(255) DEFAULT NULL,
  `trabajador` int DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=185 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `personas_avatar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `personas_avatar` (
  `persona_id` int NOT NULL,
  `foto_id` int NOT NULL DEFAULT '0',
  `png` varchar(255) NOT NULL DEFAULT '',
  `updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`persona_id`),
  KEY `idx_avatar_foto` (`foto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Avatar recortado (cabeza transparente) por persona';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `senderos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `senderos` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `local_id` int NOT NULL DEFAULT '0',
  `origen_tipo` enum('camara','linea_plano') NOT NULL,
  `origen_id` int NOT NULL,
  `destino_tipo` enum('camara','linea_plano') NOT NULL,
  `destino_id` int NOT NULL,
  `estilo` enum('recto','ortogonal','curvo') NOT NULL DEFAULT 'recto',
  `nombre` varchar(255) DEFAULT NULL,
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_senderos_local` (`local_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Aristas del grafo de senderos (nodos = cámaras sin líneas o líneas de plano)';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `senderos_puntos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `senderos_puntos` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `sendero_id` int unsigned NOT NULL,
  `x` int NOT NULL,
  `y` int NOT NULL,
  `orden` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_senderos_puntos_sendero` (`sendero_id`,`orden`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1 COMMENT='Puntos intermedios de cada sendero (extremos derivados de los nodos)';
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `videos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `videos` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `local_id` int unsigned NOT NULL DEFAULT '0',
  `camara_id` int unsigned NOT NULL DEFAULT '0',
  `nombre` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'nombre del fichero .mp4',
  `ruta` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT 'ruta relativa a la raíz (motor/videos_archivo/...)',
  `poster` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT 'ruta relativa del JPG miniatura (motor/videos_archivo/...)',
  `fecha_ini` datetime NOT NULL COMMENT 'inicio del movimiento (del nombre del AVI)',
  `fecha_fin` datetime DEFAULT NULL,
  `duracion` float NOT NULL DEFAULT '0' COMMENT 'segundos',
  `peso` bigint unsigned NOT NULL DEFAULT '0' COMMENT 'bytes del MP4',
  `fps` float NOT NULL DEFAULT '10',
  `ancho` int unsigned NOT NULL DEFAULT '0',
  `alto` int unsigned NOT NULL DEFAULT '0',
  `creado` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_videos_local_fecha` (`local_id`,`camara_id`,`fecha_ini`),
  KEY `idx_videos_fecha_ini` (`fecha_ini`),
  KEY `idx_videos_camara` (`camara_id`)
) ENGINE=InnoDB AUTO_INCREMENT=7052 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Vídeos de movimiento comprimidos (H.264)';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

