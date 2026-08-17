<?php

/* 
 * Seguridad web — libs/auth.php (Fase 4).
 * CSRF + rate-limit + helpers. Usa $_SESSION.
 */

/** Token CSRF (genera si no existe). */
function csrf_token(): string
{
    if (empty($_SESSION["csrf"])) {
        $_SESSION["csrf"] = bin2hex(random_bytes(32));
    }
    return $_SESSION["csrf"];
}

/** Campo oculto para formularios. */
function csrf_field(): string
{
    return '<input type="hidden" name="csrf" value="' . htmlspecialchars(csrf_token()) . '">';
}

/** Valida el token CSRF recibido. */
function csrf_validate(?string $token): bool
{
    return !empty($_SESSION["csrf"]) && is_string($token) && hash_equals($_SESSION["csrf"], $token);
}

/** ¿Se ha superado el límite de intentos fallidos? (por clave, p.ej. login_IP) */
function rate_limit_check(string $key, int $max = 5, int $window = 300): bool
{
    $now = time();
    $d = $_SESSION["rl"][$key] ?? ["n" => 0, "t" => $now];
    if ($now - $d["t"] > $window) {
        $d = ["n" => 0, "t" => $now];
    }
    return $d["n"] >= $max;
}

/** Registra un intento fallido. */
function rate_limit_record(string $key): void
{
    $now = time();
    $d = $_SESSION["rl"][$key] ?? ["n" => 0, "t" => $now];
    if ($now - $d["t"] > 300) {
        $d = ["n" => 0, "t" => $now];
    }
    $d["n"]++;
    $d["t"] = $now;
    $_SESSION["rl"][$key] = $d;
}

/** ID de sesión seguro (no rand() predecible). */
function session_user_id(): string
{
    return bin2hex(random_bytes(8));
}
