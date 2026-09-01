<?php

function rf_current_local_id(): int { return (int)($_SESSION['local_id'] ?? 0); }
function rf_require_local_session(): int {
    if (empty($_SESSION['user']) || rf_current_local_id() <= 0) { http_response_code(403); exit('Forbidden'); }
    return rf_current_local_id();
}
function rf_csrf_token(): string {
    if (empty($_SESSION['rf_csrf'])) $_SESSION['rf_csrf'] = bin2hex(random_bytes(32));
    return $_SESSION['rf_csrf'];
}
function rf_require_csrf(): void {
    $v = (string)($_POST['csrf'] ?? $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
    if ($v === '' || empty($_SESSION['rf_csrf']) || !hash_equals($_SESSION['rf_csrf'], $v)) { http_response_code(419); exit('Invalid CSRF token'); }
}
function rf_safe_component(string $value): string {
    if ($value === '' || strlen($value) > 128 || !preg_match('/^[A-Za-z0-9_-]+$/D', $value)) throw new InvalidArgumentException('Invalid path component');
    return $value;
}
function rf_audit_sidecar_path(string $root, string $local, string $camera, string $correlation): string {
    return rtrim($root, '/') . '/motor/audit_queue/' . rf_safe_component($local) . '/' . rf_safe_component($camera) . '/' . rf_safe_component($correlation) . '.json';
}
