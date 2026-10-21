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


/* -------------------------------------------------------------------------
 * Autenticación por el gate universal de patrón (panel-gate).
 *
 * Solo se usa cuando RF_AUTH_MODE=gate (instancia `ojos`). El gate inyecta
 * `X-Panel-Gate: 1` en la petición proxada desde loopback. Nunca se acepta esa
 * cabecera si el cliente no es la propia máquina: un cliente público no puede
 * falsificarla porque Apache/panel-gate la eliminan y solo la añaden desde
 * 127.0.0.1.
 * ---------------------------------------------------------------------- */

function rf_auth_mode_gate(): bool
{
    return defined("RF_AUTH_MODE") && RF_AUTH_MODE === "gate";
}

function rf_gate_client_is_loopback(): bool
{
    $addr = (string)($_SERVER["REMOTE_ADDR"] ?? "");
    return in_array($addr, ["127.0.0.1", "::1", "::ffff:127.0.0.1"], true);
}

function rf_gate_authenticated(): bool
{
    return rf_gate_client_is_loopback()
        && (string)($_SERVER["HTTP_X_PANEL_GATE"] ?? "") === "1";
}

/** Crea la sesión admin una sola vez tras validar el patrón. */
function rf_gate_start_session(): void
{
    if (isset($_SESSION["user"]) && $_SESSION["user"] !== "") {
        return;
    }
    $_SESSION["user"] = session_user_id();
    $_SESSION["local_id"] = 1;
    $_SESSION["admin"] = 1;
    $_SESSION["auth_via"] = "gate";
    session_regenerate_id(true);
}

/** Rechaza accesos al backend interno que no vengan del gate. */
function rf_gate_deny(): void
{
    http_response_code(403);
    header("Content-Type: text/plain; charset=utf-8");
    echo "Acceso restringido: entra por https://josue.ink/ojos/";
    exit;
}


/**
 * Cierra la sesión PHP y la del patrón universal.
 *
 * No se puede cerrar `pg_session` desde PHP (es HttpOnly y la emite el gate):
 * se devuelve una página mínima que hace POST a /__gate/logout y vuelve a la
 * pantalla de patrón. Solo se usa con RF_AUTH_MODE=gate.
 */
function rf_gate_logout_page(): void
{
    $_SESSION = [];
    if (ini_get("session.use_cookies")) {
        $p = session_get_cookie_params();
        setcookie(session_name(), "", time() - 42000,
            $p["path"] ?: "/", $p["domain"] ?: "",
            !empty($p["secure"]), !empty($p["httponly"]));
    }
    @session_destroy();
    $base = defined("RF_BASE_PATH") ? RF_BASE_PATH : "/ojos/";
    header("Content-Type: text/html; charset=utf-8");
    header("Cache-Control: no-store");
    echo "<!doctype html><meta charset=\"utf-8\"><title>Cerrando sesión</title><script>"
       . "fetch('/__gate/logout',{method:'POST',credentials:'same-origin'})"
       . ".catch(function(){}).finally(function(){location.replace(" . json_encode($base) . ");});"
       . "</script>";
    exit;
}
