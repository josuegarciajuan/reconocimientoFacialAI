# 15 · Red de cámaras: subred de la oficina vía Tailscale

## Contexto

Las cámaras IP (`rtsp://…`, puerto 554) viven en la **LAN de la oficina**
(`172.16.51.0/24`), pero el motor corre en el **servidor de producción**
(`<HOST_PRODUCCION>`, remoto). Para que producción alcance las cámaras se usa un
**subnet router de Tailscale**: un equipo de la oficina anuncia la subred y
producción la acepta.

> Este mecanismo ya estaba configurado (de ahí que las cámaras funcionaran
> antes). No requiere tocar la red para el arranque normal; esta spec documenta
> cómo está montado y cómo verificarlo/recuperarlo.
>
> Convención del repo: **no se versionan IPs de infraestructura ni credenciales**.
> Las IPs concretas de cada nodo se consultan con `tailscale status`; las de las
> cámaras, en la tabla `camaras` de la BD de producción.

## Nodos implicados

| Nodo Tailscale | Rol |
|---|---|
| `oficina` | **Subnet router**: anuncia `172.16.51.0/24` |
| `<HOST_PRODUCCION>` (`mail`) | Consumidor: acepta rutas (`--accept-routes`) y ejecuta el motor |
| `liveyourdre2` | Dev (no ejecuta el motor) |

## Montaje (cómo se configuró)

### En el equipo de oficina (subnet router)
1. Activar el reenvío de paquetes:
   ```bash
   echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-tailscale.conf
   echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
   sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
   ```
2. Anunciar la subred:
   ```bash
   sudo tailscale up --advertise-routes=172.16.51.0/24
   ```
3. **Aprobar la ruta** en la consola de administración de Tailscale
   (Machines → `oficina` → Edit route settings → habilitar `172.16.51.0/24`).
   Sin aprobación, el resto de nodos no instalan la ruta.

### En producción (consumidor)
```bash
sudo tailscale up --ssh --accept-routes
```
Esto deja `RouteAll=true` en las preferencias (persiste entre reinicios) e
instala la subred en la tabla de Tailscale. No hace falta IP forwarding en prod.

## Verificación

```bash
# 1. La ruta está anunciada por oficina (PrimaryRoutes no vacío)
tailscale status | grep oficina
tailscale status --json | python3 -c \
  "import sys,json;d=json.load(sys.stdin);[print(p['HostName'],p.get('PrimaryRoutes')) for p in d['Peer'].values()]"

# 2. La ruta está instalada en prod (tabla 52 de Tailscale)
ip route show table 52 | grep 172.16.51
#   esperado: 172.16.51.0/24 dev tailscale0 table 52

# 3. El gateway de la oficina responde
ping -c 2 172.16.51.1
```

Comprobación de **todas** las cámaras (IPs leídas de la BD, sin exponer
credenciales):
```bash
mysql -N reconocimientofacial -e \
  "SELECT SUBSTRING_INDEX(SUBSTRING_INDEX(url_conexion,'@',-1),'/',1) FROM camaras" \
  | while read h; do timeout 4 bash -c "cat < /dev/null > /dev/tcp/${h%:*}/554" \
      2>/dev/null && echo "$h OK" || echo "$h FAIL"; done
```

## Estado de las cámaras (2026-09)

- Activas (`encendida=1`): ids **14–24** (todas alcanzables, puerto 554 abierto).
- Inactiva (`encendida=0`): id **13**, cámara caída (sin ping ni 554). Reactivar
  cuando se compruebe su estado o se conozca su nueva IP (`url_conexion`).

## Diagnóstico rápido

- **`No route to host` en una cámara**: comprobar `ip route show table 52`.
  Si falta la ruta → revisar que `oficina` está online, que anuncia la subred y
  que la ruta sigue aprobada; en prod, `sudo tailscale up --accept-routes`.
- **La subred responde pero una cámara no**: la cámara está apagada o cambió de
  IP (p. ej. DHCP). Actualizar su `url_conexion` en `camaras` o poner
  `encendida=0` mientras tanto.
- **Todo el motor sin procesar caras**: no es red; revisar el cgroup
  (`MemoryMax`) y `journalctl -k` por OOM (ver spec 14, instalación/servicios).
