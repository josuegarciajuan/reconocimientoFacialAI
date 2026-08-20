-- MySQL dump 10.13  Distrib 5.7.42, for Linux (x86_64)
--
-- Host: localhost    Database: reconocimientofacial
-- ------------------------------------------------------
-- Server version	5.7.42-0ubuntu0.18.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `camaras`
--

DROP TABLE IF EXISTS `camaras`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `camaras` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `local_id` int(11) DEFAULT '0',
  `descripcion` varchar(1024) DEFAULT NULL,
  `directorio` varchar(255) DEFAULT NULL,
  `url_conexion` varchar(255) DEFAULT NULL,
  `sistema` int(11) DEFAULT '0',
  `x` int(11) DEFAULT '0',
  `y` int(11) DEFAULT '0',
  `puerta` int(11) DEFAULT '0',
  `salida` int(11) DEFAULT '0',
  `encendida` int(11) DEFAULT '0',
  `ipcamlive_alias` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `segundos_analizar` int(11) DEFAULT '3',
  `porcentaje_mov` int(11) DEFAULT '80',
  `dontCare` int(11) DEFAULT '500',
  `fps` int(11) DEFAULT '15',
  `maximo_videos` int(11) DEFAULT '60',
  `redimesionframe` int(11) DEFAULT '60',
  `sensibilidad` int(11) DEFAULT '1',
  `url_desdeserver` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `camaras`
--

LOCK TABLES `camaras` WRITE;
/*!40000 ALTER TABLE `camaras` DISABLE KEYS */;
INSERT INTO `camaras` VALUES (1,1,'cam_lorenzo',NULL,'rtsp://admin:bakcAse4@93.176.162.71:901/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:19:59',2,60,220,14,60,60,1,''),(2,1,'cam_adrian',NULL,'rtsp://admin:bakcAse4@93.176.162.71:902/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:20:24',2,60,220,14,60,60,1,NULL),(3,1,'cam_fran',NULL,'rtsp://admin:bakcAse4@93.176.162.71:903/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:21:01',2,60,220,14,60,60,1,NULL),(4,1,'cam_laura',NULL,'rtsp://admin:bakcAse4@93.176.162.71:904/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'1','2024-01-31 11:21:21',2,60,220,14,60,60,1,NULL),(5,1,'cam_recepcion',NULL,'rtsp://admin:bakcAse4@93.176.162.71:905/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:21:43',2,60,220,14,60,60,1,NULL),(6,1,'cam_archivo',NULL,'rtsp://admin:bakcAse4@93.176.162.71:906/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:22:01',2,60,220,14,60,60,1,NULL),(7,1,'cam_oscar',NULL,'rtsp://admin:bakcAse4@93.176.162.71:907/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:22:23',2,60,220,14,60,60,1,NULL),(8,1,'cam_escalera',NULL,'rtsp://admin:bakcAse4@93.176.162.71:908/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:22:41',2,60,220,14,60,60,1,NULL),(9,1,'cam_pepe',NULL,'rtsp://admin:bakcAse4@93.176.162.71:909/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:23:00',2,60,220,14,60,60,1,NULL),(10,1,'cam_juntas',NULL,'rtsp://admin:bakcAse4@93.176.162.71:910/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:23:19',2,60,220,14,60,60,1,NULL),(11,1,'cam_pasillo',NULL,'rtsp://admin:bakcAse4@93.176.162.71:911/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:23:42',2,60,220,14,60,60,1,NULL),(12,1,'cam_puerta',NULL,'rtsp://admin:bakcAse4@93.176.162.71:912/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2024-01-31 11:24:01',2,60,220,14,60,60,1,NULL);
/*!40000 ALTER TABLE `camaras` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cruces_lineas`
--

DROP TABLE IF EXISTS `cruces_lineas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cruces_lineas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `linea_id` int(11) DEFAULT '0',
  `fecha` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `direccion` int(11) DEFAULT '0',
  `x_cruce` int(11) DEFAULT '0',
  `y_cruce` int(11) DEFAULT '0',
  `identificador` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cruces_lineas`
--

LOCK TABLES `cruces_lineas` WRITE;
/*!40000 ALTER TABLE `cruces_lineas` DISABLE KEYS */;
/*!40000 ALTER TABLE `cruces_lineas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `estancias`
--

DROP TABLE IF EXISTS `estancias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `estancias` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `persona_id` int(11) DEFAULT '0',
  `camara_id` int(11) DEFAULT '0',
  `fecha_ini` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_fin` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `notificacion_vista` int(11) DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `estancias`
--

LOCK TABLES `estancias` WRITE;
/*!40000 ALTER TABLE `estancias` DISABLE KEYS */;
/*!40000 ALTER TABLE `estancias` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `fotos`
--

DROP TABLE IF EXISTS `fotos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fotos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `estancia_id` int(11) DEFAULT '0',
  `nombre_real_antesconversion` varchar(255) DEFAULT NULL,
  `identificador_unico` varchar(255) DEFAULT NULL,
  `generada_hq` tinyint(1) NOT NULL DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fotos`
--

LOCK TABLES `fotos` WRITE;
/*!40000 ALTER TABLE `fotos` DISABLE KEYS */;
/*!40000 ALTER TABLE `fotos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lineas`
--

DROP TABLE IF EXISTS `lineas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `lineas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `camara_id` int(11) DEFAULT '0',
  `nombre` varchar(255) DEFAULT NULL,
  `x1` float DEFAULT '0',
  `y1` float DEFAULT '0',
  `x2` float DEFAULT '0',
  `y2` float DEFAULT '0',
  `eliminada` int(11) DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lineas`
--

LOCK TABLES `lineas` WRITE;
/*!40000 ALTER TABLE `lineas` DISABLE KEYS */;
/*!40000 ALTER TABLE `lineas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `locales`
--

DROP TABLE IF EXISTS `locales`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `locales` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(255) DEFAULT NULL,
  `url_logo` varchar(255) DEFAULT NULL,
  `aforo_max` int(11) DEFAULT NULL,
  `aforo_actual` int(11) DEFAULT '0',
  `usuario` varchar(255) DEFAULT NULL,
  `passw` varchar(255) DEFAULT NULL,
  `directorio` varchar(255) DEFAULT NULL,
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `locales`
--

LOCK TABLES `locales` WRITE;
/*!40000 ALTER TABLE `locales` DISABLE KEYS */;
INSERT INTO `locales` VALUES (1,'Oficina','https://ichef.bbci.co.uk/news/976/cpsprodpb/3066/production/_111609321_1-1.jpg',50,0,'ofi','o',NULL,'2024-01-31 11:18:09');
/*!40000 ALTER TABLE `locales` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `nodos`
--

DROP TABLE IF EXISTS `nodos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `nodos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `camara_id1` int(11) DEFAULT '0',
  `camara_id2` int(11) DEFAULT '0',
  `x` int(11) DEFAULT '0',
  `y` int(11) DEFAULT '0',
  `orden` int(11) DEFAULT '0',
  `camino` tinyint(4) NOT NULL DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `nodos`
--

LOCK TABLES `nodos` WRITE;
/*!40000 ALTER TABLE `nodos` DISABLE KEYS */;
/*!40000 ALTER TABLE `nodos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `personas`
--

DROP TABLE IF EXISTS `personas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `personas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `local_id` varchar(255) DEFAULT NULL,
  `nombre` varchar(1024) DEFAULT '',
  `cod_interno` varchar(255) DEFAULT NULL,
  `trabajador` int(11) DEFAULT '0',
  `created` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `personas`
--

LOCK TABLES `personas` WRITE;
/*!40000 ALTER TABLE `personas` DISABLE KEYS */;
/*!40000 ALTER TABLE `personas` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-17 12:28:53
