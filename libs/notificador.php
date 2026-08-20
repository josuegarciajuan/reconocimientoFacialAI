<?php

/*
 * libs/notificador.php — Notificador de alarmas con canales.
 *
 * Objetivo: que añadir avisos por WhatsApp en el futuro inmediato sea implementar
 * un canal, sin tocar la UI ni la lógica de alarmas. Hoy solo está activo el canal
 * in-app (la UI hace polling de alarmas no vistas vía accionesAjax.php a=9).
 *
 * Para activar WhatsApp:
 *   1. Implementar CanalWhatsApp::enviar() con el proveedor (Twilio / WhatsApp
 *      Business API / la pasarela que se elija).
 *   2. Poner RF_WA_ENABLED=1 en .env (y las credenciales que use el proveedor).
 *   3. Los teléfonos de recepción se configuran en la UI (tabla alarmas_telefonos).
 */

require_once __DIR__ . "/db.php";

interface CanalAlarma
{
    /** Nombre corto del canal (para logs). */
    public function nombre(): string;

    /** Envía la alarma por este canal. $alarma es una fila de la tabla `alarmas`. */
    public function enviar(array $alarma, int $local_id): void;
}

final class CanalInApp implements CanalAlarma
{
    public function nombre(): string
    {
        return "inapp";
    }

    public function enviar(array $alarma, int $local_id): void
    {
        // Sin-op intencional: el banner/badge del panel lee la BD directamente
        // (alarmas.notificacion_vista = 0). Nada que enviar aquí.
    }
}

final class CanalWhatsApp implements CanalAlarma
{
    public function nombre(): string
    {
        return "whatsapp";
    }

    public function enviar(array $alarma, int $local_id): void
    {
        if (getenv("RF_WA_ENABLED") !== "1") {
            return; // canal preparado pero inactivo
        }
        // TODO(futuro inmediato): POST al proveedor de WhatsApp con el mensaje:
        //   "🚨 La Almenara · <severidad>: <mensaje> (<fecha>)" a cada teléfono de
        //   alarmas_telefonos WHERE local_id = ? AND activo = 1.
        // Credenciales previstas en .env: RF_WA_URL / RF_WA_TOKEN / RF_WA_WHATSAPP_ID.
        $destinos = DB::select(
            "SELECT nombre, telefono FROM alarmas_telefonos WHERE local_id = ? AND activo = 1",
            [$local_id]
        );
        if (!$destinos) {
            return;
        }
        // Punto de enganche del proveedor (ver TODO arriba). Se deja la lista
        // de destinatarios ya cargada para no repetir la consulta al implementarlo.
    }
}

final class NotificadorAlarma
{
    /**
     * Canales activos en este despliegue. Para añadir WhatsApp:
     * descomentar CanalWhatsApp() una vez implementado el proveedor.
     * @return CanalAlarma[]
     */
    public static function canales(): array
    {
        return [new CanalInApp()];
    }

    /** Notifica la alarma por todos los canales activos. */
    public static function notificar(array $alarma, int $local_id): void
    {
        foreach (self::canales() as $canal) {
            $canal->enviar($alarma, $local_id);
        }
    }
}
