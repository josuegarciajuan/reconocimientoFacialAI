<?php

/* 
 * Capa de acceso a datos PDO — libs/db.php (Fase 4).
 * Sustituye a `mysql.class.php` (concatenación de strings → SQL injection, B9).
 * API: prepared statements con placeholders `?`.
 */

require_once __DIR__ . "/../config/rutas.php";

final class DB
{
    private static ?PDO $pdo = null;

    private static function conn(): PDO
    {
        if (self::$pdo === null) {
            $dsn = "mysql:host=" . BD_HOST . ";dbname=" . BD_BBDD . ";charset=latin1";
            self::$pdo = new PDO($dsn, BD_USUARIO, BD_PASS, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ]);
        }
        return self::$pdo;
    }

    /** SELECT → array de filas asociativas. */
    public static function select(string $sql, array $params = []): array
    {
        $st = self::conn()->prepare($sql);
        $st->execute($params);
        return $st->fetchAll();
    }

    /** SELECT → primera fila o null. */
    public static function selectOne(string $sql, array $params = []): ?array
    {
        $rows = self::select($sql, $params);
        return $rows ? $rows[0] : null;
    }

    /** INSERT → devuelve el último id insertado. */
    public static function insert(string $sql, array $params = []): int
    {
        $st = self::conn()->prepare($sql);
        $st->execute($params);
        return (int) self::conn()->lastInsertId();
    }

    /** UPDATE/DELETE → número de filas afectadas. */
    public static function execute(string $sql, array $params = []): int
    {
        $st = self::conn()->prepare($sql);
        $st->execute($params);
        return $st->rowCount();
    }

    /** Inicia una transacción (para escrituras atómicas en lote). */
    public static function beginTransaction(): void
    {
        self::conn()->beginTransaction();
    }

    /** Confirma la transacción en curso. */
    public static function commit(): void
    {
        self::conn()->commit();
    }

    /** Revierte la transacción en curso. */
    public static function rollBack(): void
    {
        self::conn()->rollBack();
    }

    public static function inTransaction(): bool { return self::conn()->inTransaction(); }
}
