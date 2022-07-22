-- MySQL dump 10.13  Distrib 5.7.33, for Linux (x86_64)
--
-- Host: localhost    Database: reconocimientofacial2
-- ------------------------------------------------------
-- Server version	5.7.33-0ubuntu0.16.04.1

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
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `url_desdeserver` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `camaras`
--

LOCK TABLES `camaras` WRITE;
/*!40000 ALTER TABLE `camaras` DISABLE KEYS */;
INSERT INTO `camaras` VALUES (1,1,'Camara fichador',NULL,'rtsp://admin:bakcAse4@172.16.51.51:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-09-30 14:40:44','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0'),(2,1,'Camara pasillo',NULL,'rtsp://admin:bakcAse4@172.16.51.50:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-09-30 14:41:33','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:777/cam/realmonitor?channel=1&subtype=0'),(3,1,'Camara josue',NULL,'rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-09-30 14:42:02','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:779/cam/realmonitor?channel=1&subtype=0'),(4,1,'Camara salida',NULL,'rtsp://admin:bakcAse4@172.16.51.53:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,1,1,'-','2021-09-30 14:42:19','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:780/cam/realmonitor?channel=1&subtype=0'),(5,1,'Camara entrada',NULL,'rtsp://admin:bakcAse4@172.16.51.54:554/cam/realmonitor?channel=1&subtype=0',0,0,0,1,0,1,'-','2021-09-30 14:43:06','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:781/cam/realmonitor?channel=1&subtype=0');
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
  `fecha` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `direccion` int(11) DEFAULT '0',
  `x_cruce` int(11) DEFAULT '0',
  `y_cruce` int(11) DEFAULT '0',
  `identificador` varchar(255) DEFAULT NULL,
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cruces_lineas`
--

LOCK TABLES `cruces_lineas` WRITE;
/*!40000 ALTER TABLE `cruces_lineas` DISABLE KEYS */;
INSERT INTO `cruces_lineas` VALUES (1,9,'2021-09-30 15:31:52',1,386,421,'bqAbiLG04D6oGO4uyXAA4qoICj','2021-09-30 15:57:00');
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
  `fecha_ini` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_fin` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `notificacion_vista` int(11) DEFAULT '0',
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `estancias`
--

LOCK TABLES `estancias` WRITE;
/*!40000 ALTER TABLE `estancias` DISABLE KEYS */;
INSERT INTO `estancias` VALUES (1,1,3,'2021-09-30 15:36:56','2021-09-30 15:36:56',0,'2021-09-30 16:34:57'),(2,1,3,'2021-09-30 15:32:00','2021-09-30 15:32:00',0,'2021-09-30 16:34:57'),(3,1,3,'2021-09-30 15:31:58','2021-09-30 15:31:58',0,'2021-09-30 16:34:57'),(4,1,3,'2021-09-30 16:43:24','2021-09-30 16:43:24',0,'2021-09-30 16:43:55'),(5,2,2,'2021-09-30 16:44:38','2021-09-30 16:44:38',0,'2021-09-30 16:45:09'),(6,2,3,'2021-09-30 16:55:32','2021-09-30 16:55:32',0,'2021-09-30 16:55:51'),(7,3,1,'2021-10-01 07:33:02','2021-10-01 07:33:02',0,'2021-10-01 07:33:41');
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
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fotos`
--

LOCK TABLES `fotos` WRITE;
/*!40000 ALTER TABLE `fotos` DISABLE KEYS */;
INSERT INTO `fotos` VALUES (1,1,'3_2021-09-30_15:36:56.437027.avi_0.5448105335235596.jpg----3_2021-09-30_15:36:56.437027.avi_0.711728572845459.jpg_bT8zN5runSwmjUdmu3wn9WG87U.jpg','bT8zN5runSwmjUdmu3wn9WG87U','2021-09-30 16:34:57'),(2,2,'3_2021-09-30_15:31:58.745293.avi_2.7709617614746094.jpg_b2NGea0RxMmii28FmYjCTeobo3.jpg','b2NGea0RxMmii28FmYjCTeobo3','2021-09-30 16:34:57'),(3,3,'3_2021-09-30_15:31:58.745293.avi_0.28623223304748535.jpg----3_2021-09-30_15:31:58.745293.avi_0.7331881523132324.jpg_bdQ9Z3GDhRcnK5OL2b460Juitp.jpg','bdQ9Z3GDhRcnK5OL2b460Juitp','2021-09-30 16:34:57'),(4,3,'3_2021-09-30_15:31:58.745293.avi_0.2497386932373047.jpg_b2cUhZ3EPfkOoPLdtWDk577hGr.jpg','b2cUhZ3EPfkOoPLdtWDk577hGr','2021-09-30 16:34:57'),(5,4,'3_2021-09-30_16:43:24.313113.avi_0.5057532787322998.jpg----3_2021-09-30_16:43:24.313113.avi_0.8731725215911865.jpg_b3NVtxgWQp6myWn0HWdJOEQhCZ.jpg','b3NVtxgWQp6myWn0HWdJOEQhCZ','2021-09-30 16:43:55'),(6,5,'2_2021-09-30_16:44:38.104530.avi_0.43654346466064453.jpg_buPdiiPlUyXF1oDRiPW4I5d9a0.jpg','buPdiiPlUyXF1oDRiPW4I5d9a0','2021-09-30 16:45:09'),(7,6,'3_2021-09-30_16:55:32.221593.avi_0.8269133567810059.jpg----3_2021-09-30_16:55:32.221593.avi_0.9945807456970215.jpg_bUxuFrsn2GBVuSrriBXdnCpmsz.jpg','bUxuFrsn2GBVuSrriBXdnCpmsz','2021-09-30 16:55:51'),(8,7,'1_2021-10-01_07:33:02.145890.avi_0.5162773132324219.jpg_b8PoET1kt4L5hseCKxcf8KVzPG.jpg','b8PoET1kt4L5hseCKxcf8KVzPG','2021-10-01 07:33:41'),(9,7,'1_2021-10-01_07:33:02.145890.avi_0.7599067687988281.jpg_bgZwiumfZ19w2cwmPOGoL0Vo9v.jpg','bgZwiumfZ19w2cwmPOGoL0Vo9v','2021-10-01 07:33:42');
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
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lineas`
--

LOCK TABLES `lineas` WRITE;
/*!40000 ALTER TABLE `lineas` DISABLE KEYS */;
INSERT INTO `lineas` VALUES (1,1,'paso administracion',101,392,114,726,0,'2021-09-30 15:06:21'),(2,1,'agua',641,431,648,477,0,'2021-09-30 15:09:09'),(3,1,'entrada',294,618,390,624,0,'2021-09-30 15:09:34'),(4,1,'banyo xicas',402,405,406,501,0,'2021-09-30 15:09:57'),(5,1,'banyo xicos',303,413,308,502,0,'2021-09-30 15:10:18'),(6,2,'mar',164,403,169,488,0,'2021-09-30 15:18:27'),(7,3,'mapa',93,549,109,719,0,'2021-09-30 15:19:15'),(8,3,'lorenzo',509,494,523,705,0,'2021-09-30 15:19:15'),(9,3,'pilar paleta salida',370,524,380,607,0,'2021-09-30 15:20:14'),(10,4,'paso entrada',246,287,252,398,0,'2021-09-30 15:21:08'),(11,4,'mitad esaleras',129,589,433,621,0,'2021-09-30 15:21:08'),(12,4,'por el pasillito al lado del pilar palketa salida',101,249,106,411,0,'2021-09-30 15:21:46'),(13,4,'ratas',569,673,638,662,0,'2021-09-30 15:22:04'),(14,5,'paso banyo xicas',328,119,333,261,0,'2021-09-30 15:23:04'),(15,5,'paso banyo hombres',176,89,183,271,0,'2021-09-30 15:23:04'),(16,5,'ratas',100,568,145,567,0,'2021-09-30 15:23:23'),(17,5,'puerta calle',179,419,184,475,0,'2021-09-30 15:24:32'),(18,5,'trastero',309,463,311,534,0,'2021-09-30 15:25:41'),(19,5,'antes sillas',501,134,499,305,0,'2021-09-30 15:26:14');
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
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `locales`
--

LOCK TABLES `locales` WRITE;
/*!40000 ALTER TABLE `locales` DISABLE KEYS */;
INSERT INTO `locales` VALUES (1,'Oficina','https://ichef.bbci.co.uk/news/976/cpsprodpb/3066/production/_111609321_1-1.jpg',100,0,'ofi','a',NULL,'2021-09-30 14:39:28'),(2,'Luna Azul','https://www.pikpng.com/pngl/m/429-4298683_media-luna-azul-png-imagenes-de-media-luna.png',100,0,'lunaazul','a',NULL,'2021-09-30 14:39:53');
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
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `personas`
--

LOCK TABLES `personas` WRITE;
/*!40000 ALTER TABLE `personas` DISABLE KEYS */;
INSERT INTO `personas` VALUES (1,'1','','bA1qhrUdwmmT95c1IThepKZsoU',0,'2021-09-30 16:34:57'),(2,'1','','bN7jPxhX1Ix5ZAcqRjI1wtcRZ4',0,'2021-09-30 16:45:09'),(3,'1','','bWsppBFLCGa1TyVf2VLqGkuzln',0,'2021-10-01 07:33:41');
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

-- Dump completed on 2021-10-01 16:07:59
