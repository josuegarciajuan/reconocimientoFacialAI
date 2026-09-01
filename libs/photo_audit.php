<?php

/** Consume the classifier's atomic, non-sensitive audit sidecar after fotos.id exists. */
function ingest_photo_audit(int $foto_id, string $correlation_id, string $local_id, string $camera_id): void
{
    $path = RUTA_PROYECTO . "motor/audit_queue/" . rawurlencode($local_id) . "/"
        . rawurlencode($camera_id) . "/" . rawurlencode($correlation_id) . ".json";
    if (!is_file($path)) {
        return;
    }
    $raw = file_get_contents($path);
    $record = json_decode((string)$raw, true);
    if (!is_array($record) || ($record["schema_version"] ?? "") !== "photo-audit-1"
        || (string)($record["correlation_id"] ?? "") !== $correlation_id) {
        return; // fail closed; leave it for diagnosis/retry
    }
    $existing = DB::selectOne("SELECT id FROM foto_audits WHERE correlation_id = ? LIMIT 1", [$correlation_id]);
    if (!$existing) {
        DB::insert(
            "INSERT INTO foto_audits (foto_id, correlation_id, schema_version, local_id, camera_id,
             classification, classification_phase, person_code, layers_json, attributes_json, classified_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [$foto_id, $correlation_id, "photo-audit-1", (string)($record["local_id"] ?? $local_id),
             (string)($record["camera_id"] ?? $camera_id), (string)($record["classification"] ?? "unknown"),
             (string)($record["classification_phase"] ?? "initial"), $record["person"] ?? null,
             json_encode($record["layers"] ?? [], JSON_UNESCAPED_UNICODE),
             isset($record["attributes"]) ? json_encode($record["attributes"], JSON_UNESCAPED_UNICODE) : null,
             (float)($record["classified_at"] ?? 0.0)]
        );
    } elseif (DB::selectOne("SELECT foto_id FROM foto_audits WHERE correlation_id = ?", [$correlation_id])["foto_id"] === null) {
        // The only mutable field is the post-insert FK correlation.
        DB::execute("UPDATE foto_audits SET foto_id = ? WHERE correlation_id = ? AND foto_id IS NULL", [$foto_id, $correlation_id]);
    }
    @unlink($path);
}
