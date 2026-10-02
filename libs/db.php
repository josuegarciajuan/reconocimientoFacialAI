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

    /** Reintentos ante deadlock de InnoDB (SQLSTATE 40001 / error 1213). */
    public const DEADLOCK_RETRIES = 4;

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

    /**
     * ¿Es un deadlock transitorio de InnoDB (recuperable con un reintento)?
     * MySQL devuelve SQLSTATE 40001 ("Serialization failure") y error 1213.
     */
    public static function esReintentable(?array $errorInfo): bool
    {
        if (!$errorInfo) {
            return false;
        }
        $sqlstate = (string) ($errorInfo[0] ?? "");
        $code = (int) ($errorInfo[1] ?? 0);
        return $sqlstate === "40001" || $code === 1213;
    }

    /**
     * Ejecuta `$fn` reintentando ante deadlock con backoff aleatorio.
     *
     * No reintenta dentro de una transacción explícita: el deadlock deja la
     * transacción abortada por MySQL y hay que rehacerla entera (el llamador
     * debe capturar y decidir). Fuera de transacción (autocommit, que es como
     * escriben los daemons) el reintento de la sentencia es seguro.
     */
    public static function conReintento(callable $fn)
    {
        $intento = 0;
        while (true) {
            try {
                return $fn();
            } catch (PDOException $e) {
                $intento++;
                if (!self::esReintentable($e->errorInfo) || self::enTransaccion()
                        || $intento >= self::DEADLOCK_RETRIES) {
                    throw $e;
                }
                // Backoff exponencial suave con jitter (20-100 ms).
                usleep((int) (20000 * $intento) + random_int(0, 20000));
            }
        }
    }

    /** INSERT → devuelve el último id insertado. */
    public static function insert(string $sql, array $params = []): int
    {
        self::conReintento(static function () use ($sql, $params): void {
            $st = self::conn()->prepare($sql);
            $st->execute($params);
        });
        return (int) self::conn()->lastInsertId();
    }

    /** UPDATE/DELETE → número de filas afectadas. */
    public static function execute(string $sql, array $params = []): int
    {
        return (int) self::conReintento(static function () use ($sql, $params): int {
            $st = self::conn()->prepare($sql);
            $st->execute($params);
            return $st->rowCount();
        });
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

    /** ¿Hay conexión abierta con transacción explícita en curso? (no conecta) */
    private static function enTransaccion(): bool
    {
        return self::$pdo !== null && self::$pdo->inTransaction();
    }

    public static function inTransaction(): bool { return self::conn()->inTransaction(); }
}
