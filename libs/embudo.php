<?php

/**
 * Embudo de latencia (P0/WS1) — lectura/escritura del JSONL del motor.
 *
 * El motor Python escribe eventos en `motor/logs/embudo_<local>.jsonl` (tipos
 * `video`, `descarte`, `decision`, `cuerpo`, `latencia`). El panel PHP necesita
 * (a) añadir su propia etapa `bd` (foto publicada en BD, `clasificadorV2.php`) y
 * (b) agregar los percentiles de latencia para el diagnóstico. Este fichero
 * replica el contrato de `motor/core/embudo.py` (append bajo flock, best-effort)
 * para no depender de un subproceso Python en la web.
 *
 * Solo métricas; nunca datos personales. El JSONL es dato runtime (gitignored).
 */

if (!function_exists('embudo_log_latencia')) {

    /** Ruta del JSONL del embudo para un local. */
    function embudo_path($local_id): string
    {
        return rtrim(RUTA_PROYECTO, '/') . '/motor/logs/embudo_' . (int)$local_id . '.jsonl';
    }

    /**
     * Append best-effort de un evento `latencia` (mismo contrato que el motor).
     * Nunca lanza: un fallo de disco no debe romper la ingesta a BD.
     */
    function embudo_log_latencia($local_id, string $etapa, array $campos): void
    {
        try {
            $path = embudo_path($local_id);
            $dir = dirname($path);
            if (!is_dir($dir)) {
                @mkdir($dir, 0775, true);
            }
            $evento = array_merge(
                ['ts' => microtime(true), 'tipo' => 'latencia', 'etapa' => $etapa],
                $campos
            );
            $line = json_encode($evento, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
            if ($line === false) {
                return;
            }
            $fh = @fopen($path, 'a');
            if (!$fh) {
                return;
            }
            try {
                @flock($fh, LOCK_EX);
                @fwrite($fh, $line . "\n");
                @flock($fh, LOCK_UN);
            } finally {
                @fclose($fh);
            }
        } catch (Throwable $e) {
            // best-effort: la métrica nunca rompe el pipeline
        }
    }

    /** Percentil por interpolación lineal (equivalente al motor Python). */
    function embudo_pct(array $xs, float $p)
    {
        $n = count($xs);
        if ($n === 0) {
            return null;
        }
        sort($xs, SORT_NUMERIC);
        if ($n === 1) {
            return (float)$xs[0];
        }
        $k = ($n - 1) * $p / 100.0;
        $f = (int)floor($k);
        $c = (int)ceil($k);
        if ($f === $c) {
            return (float)$xs[(int)$k];
        }
        return $xs[$f] + ($xs[$c] - $xs[$f]) * ($k - $f);
    }

    /**
     * Agrega los eventos `latencia` del local en percentiles por etapa.
     * $desde (YYYY-MM-DD) filtra por fecha del evento (hora local).
     */
    function embudo_resumen_latencia($local_id, string $desde = ''): array
    {
        $extraccion = [];
        $espera = [];
        $clasificacion = [];
        $e2e = [];
        $path = embudo_path($local_id);
        if (is_file($path)) {
            $fh = @fopen($path, 'r');
            if ($fh) {
                while (($ln = fgets($fh)) !== false) {
                    $ln = trim($ln);
                    if ($ln === '') {
                        continue;
                    }
                    $e = json_decode($ln, true);
                    if (!is_array($e) || ($e['tipo'] ?? '') !== 'latencia') {
                        continue;
                    }
                    if ($desde !== '' && date('Y-m-d', (int)($e['ts'] ?? 0)) < $desde) {
                        continue;
                    }
                    $etapa = $e['etapa'] ?? '';
                    if ($etapa === 'extract') {
                        if (isset($e['dur_s']) && $e['dur_s'] !== null) {
                            $extraccion[] = (float)$e['dur_s'];
                        }
                        if (isset($e['espera_s']) && $e['espera_s'] !== null) {
                            $espera[] = (float)$e['espera_s'];
                        }
                    } elseif ($etapa === 'classify') {
                        if (isset($e['dur_s']) && $e['dur_s'] !== null) {
                            $clasificacion[] = (float)$e['dur_s'];
                        }
                    } elseif ($etapa === 'bd') {
                        if (isset($e['e2e_s']) && $e['e2e_s'] !== null) {
                            $e2e[] = (float)$e['e2e_s'];
                        }
                    }
                }
                @fclose($fh);
            }
        }

        $block = static function (array $xs): array {
            return [
                'n' => count($xs),
                'p50' => embudo_pct($xs, 50),
                'p95' => embudo_pct($xs, 95),
                'max' => $xs ? max($xs) : null,
            ];
        };

        return [
            'extraccion_s' => $block($extraccion),
            'espera_cola_s' => $block($espera),
            'clasificacion_s' => $block($clasificacion),
            'e2e_s' => $block($e2e),
        ];
    }
}
