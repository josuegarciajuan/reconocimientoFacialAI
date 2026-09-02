<?php

/** Consume the classifier's atomic, access-controlled audit sidecar after fotos.id exists. */
function ingest_photo_audit(int $foto_id, string $correlation_id, string $local_id, string $camera_id): void
{
    require_once __DIR__ . "/security.php";
    try { $path = rf_audit_sidecar_path(RUTA_PROYECTO, $local_id, $camera_id, $correlation_id); }
    catch (InvalidArgumentException $e) { return; }
    if (!is_file($path)) {
        return;
    }
    $raw = file_get_contents($path);
    $record = json_decode((string)$raw, true);
    $valid_attributes = static function ($value): bool {
        if ($value === null) return true;
        $fields = [
            'glasses' => ['visible','absent','unknown'], 'headwear' => ['visible','absent','unknown'],
            'mask' => ['visible','absent','unknown'], 'beard_moustache' => ['visible','absent','unknown'],
            'hair' => ['visible','silhouette','absent','unknown'],
            'accessories' => ['unknown','none','backpack','bag','scarf','jewellery','other'],
            'clothing_color' => ['black','white','gray','blue','green','red','yellow','brown','orange','purple','multicolor','unknown'],
        ];
        if (!is_array($value) || ($value['version'] ?? '') !== 'appearance-1' || !is_array($value['attributes'] ?? null)) return false;
        foreach ($fields as $name => $allowed) {
            $v = $value['attributes'][$name] ?? 'unknown';
            if ($name === 'accessories' && is_array($v)) { if (!$v || count(array_unique($v)) !== count($v)) return false; foreach ($v as $x) if (!is_string($x) || !in_array($x, array_diff($allowed, ['unknown']), true)) return false; }
            elseif (!is_string($v) || !in_array($v, $allowed, true)) return false;
        }
        return is_numeric($value['confidence'] ?? null) && (float)$value['confidence'] >= 0 && (float)$value['confidence'] <= 1;
    };
    $valid_layers = static function ($layers): bool {
        if (!is_array($layers)) return false;
        foreach ($layers as $layer) if (!is_array($layer) || !is_numeric($layer['score'] ?? null) || !is_numeric($layer['confidence'] ?? null) || !is_bool($layer['available'] ?? null) || (float)$layer['score'] < 0 || (float)$layer['score'] > 1 || (float)$layer['confidence'] < 0 || (float)$layer['confidence'] > 1) return false;
        return true;
    };
    if (!is_array($record) || ($record["schema_version"] ?? "") !== "photo-audit-1"
        || (string)($record["correlation_id"] ?? "") !== $correlation_id
        || (string)($record["local_id"] ?? "") !== $local_id
        || (string)($record["camera_id"] ?? "") !== $camera_id
        || !in_array((string)($record["classification"] ?? ""), ["match", "new", "unknown", "uncertain", "review"], true)
        || !is_array($record["layers"] ?? null)
        || !$valid_layers($record["layers"])
        || !$valid_attributes($record["attributes"] ?? null)
        || (isset($record["person"]) && $record["person"] !== null && !is_string($record["person"]))
        || !is_numeric($record["classified_at"] ?? null)) {
        return; // fail closed; leave it for diagnosis/retry
    }
    $existing = DB::selectOne("SELECT id FROM foto_audits WHERE correlation_id = ? LIMIT 1", [$correlation_id]);
    $phase = "initial";
    if (($record["person"] ?? null) !== null) {
        $moved = DB::selectOne("SELECT 1 FROM foto_audit_events WHERE camera_id = ? AND to_person_code = ? AND UNIX_TIMESTAMP(event_at) <= ? ORDER BY id DESC LIMIT 1", [$camera_id, $record["person"], (float)$record["classified_at"]]);
        $phase = $moved ? "post_move" : "initial";
    }
    if (!$existing) {
        DB::insert(
            "INSERT IGNORE INTO foto_audits (foto_id, correlation_id, schema_version, local_id, camera_id,
             classification, classification_phase, person_code, layers_json, attributes_json, classified_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
             [$foto_id, $correlation_id, "photo-audit-1", $local_id, $camera_id, (string)$record["classification"],
              $phase, $record["person"] ?? null,
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
