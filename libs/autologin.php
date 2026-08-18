<?php

/*
 * Auto-login por dispositivo (matrícula única) — libs/autologin.php.
 * Solo se activa si AUTOLOGIN_ENABLED y la petición va por HTTPS (josue.ink),
 * nunca por el panel http :8090.
 *
 * Flujo:
 *  1. Matrícula: la primera visita GET a login.php desde AUTOLOGIN_IP genera un
 *     token aleatorio, guarda su hash sha256 en `dispositivos_autologin` y
 *     entrega el token como cookie HttpOnly+Secure (~1 año).
 *  2. Accesos siguientes: si la cookie coincide con la matrícula activa, se crea
 *     la sesión Admin sin pedir usuario/contraseña.
 *  3. Solo hay UNA matrícula activa: otros dispositivos/IPs ven el login normal.
 *
 * Revocación: `UPDATE dispositivos_autologin SET activo = 0` o AUTOLOGIN_ENABLED=0.
 */

/** ¿Petición segura (HTTPS) y funcionalidad habilitada? Excluye :8090 (http). */
function autologin_https_ok(): bool
{
    if (!defined("AUTOLOGIN_ENABLED") || AUTOLOGIN_ENABLED !== true) {
        return false;
    }
    if (isset($_SERVER["HTTPS"]) && $_SERVER["HTTPS"] !== "" && $_SERVER["HTTPS"] !== "off") {
        return true;
    }
    return (int) ($_SERVER["SERVER_PORT"] ?? 0) === 443;
}

/** Devuelve la fila activa del dispositivo matriculado (o null). */
function autologin_active_row(): ?array
{
    try {
        return DB::selectOne("SELECT * FROM dispositivos_autologin WHERE activo = 1 LIMIT 1");
    } catch (Throwable $e) {
        // Tabla ausente o BD caída: el login normal sigue funcionando.
        return null;
    }
}

/** ¿Existe ya una matrícula activa? (garantiza "solo ese dispositivo") */
function autologin_is_enrolled(): bool
{
    return autologin_active_row() !== null;
}

/** Valida un token de cookie contra la matrícula activa (comparación en tiempo constante). */
function autologin_validate_token(string $token): ?array
{
    if ($token === "") {
        return null;
    }
    $row = autologin_active_row();
    if ($row === null) {
        return null;
    }
    if (!hash_equals($row["token_hash"], hash("sha256", $token))) {
        return null;
    }
    return $row;
}

/** Crea la sesión Admin (local_id 1, admin 1) y regenera el id de sesión. */
function autologin_set_session(): void
{
    $_SESSION["user"] = session_user_id();
    $_SESSION["local_id"] = 1;
    $_SESSION["admin"] = 1;
    session_regenerate_id(true);
}

/** Matricula el dispositivo actual; devuelve el token o null si ya hay matrícula. */
function autologin_enroll(): ?string
{
    if (autologin_is_enrolled()) {
        return null;
    }
    $token = bin2hex(random_bytes(32));
    DB::insert(
        "INSERT INTO dispositivos_autologin (token_hash, ip, local_id, admin, activo, creado_en)
         VALUES (?, ?, 1, 1, 1, NOW())",
        [hash("sha256", $token), $_SERVER["REMOTE_ADDR"] ?? ""]
    );
    return $token;
}

/** Entrega la cookie del dispositivo (HttpOnly + Secure + SameSite=Lax, 1 año). */
function autologin_set_cookie(string $token): void
{
    setcookie(AUTOLOGIN_COOKIE, $token, [
        "expires"  => time() + 31536000,
        "path"     => "/reconocimientoFacial/",
        "secure"   => true,
        "httponly" => true,
        "samesite" => "Lax",
    ]);
}
