# Lancelot en el celular (Fase 2)

Un servidor gratis en tu cuenta de Cloudflare y una app web que se instala en tu Android:

- **Escribes** tareas igual que en la laptop: «mañana 8pm pagar la luz», «cada lunes 9am reunión».
  Si falta algo, Lancelot pregunta («¿Para cuándo?», «¿Qué te recuerdo?»).
- **Te avisa** con una notificación cuando vence una tarea, **aunque la app y la laptop estén apagadas**.
  La notificación trae los botones **✓ Hecho** y **+10 min**.
- **Organiza** la lista en vencidas, hoy, mañana y los días siguientes. Toca el círculo para completar
  una tarea; toca la tarea para posponerla, reprogramarla, editarla o borrarla.
- Preguntas que entiende: «¿qué tengo para hoy?», «¿qué tengo vencido?», «pasa las vencidas a mañana», «¿qué hora es?».

- **Una sola lista** con la laptop (desde la v3.9): lo que haces en un lado aparece en el otro en menos de un minuto.
- **Eventos** (desde la v3.10): «el 15 de noviembre aniversario», «examen de cálculo el 20/10». Salen con 📅 y
  «faltan N días», y llega una notificación **una semana antes y un día antes** (a las 9:00), además de la del día.
  Al tocar uno → Editar puedes cambiarlo entre Tarea y 📅 Evento.
- La lista empieza por **Tareas vencidas** (siempre a la vista), luego **📅 Próximos eventos** y tus tareas por día.
- **Toca la cara** y te dice una frase, en voz alta (⚙ → Voz para apagarla). Incluye tus frases de la laptop.
- Si la laptop ya te mostró un aviso anticipado, el celular **no lo repite** (espera 5 minutos para saberlo).
- Los avisos anticipados salen a las 9:00. Si cambias `HORA_AVISO_PREVIO` en config.py, agrega la misma hora en
  `wrangler.jsonc`, dentro de `"vars"`: `"HORA_AVISO_PREVIO": "08:30",` y ejecuta `npm run configurar`.

## Instalación (una sola vez)

### 1. Node.js
Es lo que usa la herramienta de Cloudflare. En la terminal:
```powershell
winget install OpenJS.NodeJS.LTS
```
**Cierra la terminal y ábrela de nuevo** (en tu carpeta de proyectos), y comprueba: `node --version` → v20 o más.

### 2. Configurar Cloudflare
```powershell
cd movil
npm install
npm run configurar
```
- La primera vez se abre el navegador: entra a Cloudflare (con tu GitHub) y pulsa **Allow**.
- El script crea la base de datos, sube el servidor, genera tu **clave** y deja la laptop conectada
  (escribe `nube.json` en sus carpetas de datos). **Reinicia Lancelot** en la laptop para que empiece a sincronizar.
- Al final muestra un **código QR**, la dirección (`https://lancelot.TU-SUBDOMINIO.workers.dev`) y la clave.
- Si dice que tu cuenta no tiene subdominio: entra a dash.cloudflare.com → *Workers & Pages*, elige uno
  (por ejemplo `miguel`) y vuelve a ejecutar `npm run configurar`.

La dirección y la clave quedan guardadas en `movil/.lancelot-local.json` (no se sube a GitHub).
`wrangler.jsonc` sí cambia (se anota el id de la base de datos): súbelo con tu próximo commit.

### 3. En el celular
1. Escanea el QR con la cámara y ábrelo en **Chrome**. La app se abre ya conectada.
   (Sin QR: entra a la dirección y escribe la clave.)
2. **⚙ → Activar notificaciones → Permitir.** Te llega una de prueba.
3. Menú **⋮** de Chrome → **Agregar a la pantalla principal** (o **Instalar app**). Queda con el ícono de la cara.
4. **Vivo:** para que los avisos no lleguen tarde, en *Ajustes → Batería* busca la gestión del consumo en
   segundo plano y permite que **Chrome** funcione en segundo plano.

## Después

| Quiero… | Comando (dentro de `movil`) |
|---|---|
| Subir cambios del servidor o de la app | `npm run configurar` (aplica también los cambios de la base de datos) |
| Cambiar la clave (perdí el celular) | `npm run configurar -- --nueva-clave` |
| Configurar desde otra PC | Copia `movil/.lancelot-local.json` de esta laptop; si no lo tienes, `npm run configurar` crea una clave nueva |
| Probar todo en la laptop, sin internet | `npm test` y `npm run test:servidor` |
| Ver errores del servidor | dash.cloudflare.com → Workers & Pages → lancelot → *Logs* |

La app del celular se actualiza sola: cada vez que la abres con internet descarga la versión nueva.

## Cómo funciona

```
 celular (app web) ──/api + clave──►  Worker de Cloudflare  ──►  D1 (base de datos SQLite)
        ▲                              ▲    │
        │       laptop ──/api/sync─────┘    │   cada minuto: la laptop sube sus cambios y baja los del celular
        └── notificación cifrada ◄── cada minuto revisa qué venció (Cron)
```

**Sincronización (etapa 3).** Cada tarea tiene un identificador que es el mismo en todos lados y la hora de su
último cambio. La laptop manda lo que cambió desde la última vez y recibe lo que cambió en el servidor; si una
tarea cambió en los dos lados, gana el cambio más reciente. Al borrar, la tarea se marca como borrada (no
desaparece) para que el otro lado se entere. Lo que no se sincroniza es «ya avisé»: cada dispositivo avisa por
su cuenta (la cara en la laptop, la notificación en el celular).

| Archivo | Qué hace |
|---|---|
| `src/index.js` | La API (`/api/tareas`, `/api/sync`…) y lo que corre cada minuto |
| `src/almacen.js` | Las tareas en D1: mismas operaciones que `nucleo/almacen.py` |
| `src/push.js` | Notificaciones: firma VAPID y cifrado aes128gcm, solo con WebCrypto |
| `src/seguridad.js` | La clave y las firmas de los botones de las notificaciones |
| `publico/comun/*.js` | Intérprete, comandos, fechas y repeticiones: los usan el servidor **y** el celular |
| `publico/app.js` | La app: lista, escribir, preguntas, opciones, ajustes |
| `publico/cara.js` | La cara animada (el mismo personaje de la laptop) |
| `publico/sw.js` | Recibe las notificaciones y hace funcionar sus botones con la app cerrada |
| `migraciones/` | Las tablas de la base de datos (se aplican en orden, una sola vez; `0003` = eventos, `0004` = frases y aprendizaje) |
| `publico/comun/frases.js` | Las frases de la cara (las mismas de la laptop; una prueba lo revisa) |
| `configurar.mjs` | La instalación de arriba |

**El intérprete existe dos veces** (Python en la laptop, JavaScript aquí). Las dos versiones se prueban contra los
mismos casos: `tests/casos_interprete.json`. Si mejoras el de Python: `python tests/generar_casos.py` y luego
`npm test` te dice qué ajustar en `publico/comun/interprete.js`.

## Privacidad y costo

- Tus tareas se guardan en **tu** cuenta de Cloudflare. Todo pedido necesita la clave; sin ella el servidor no
  muestra nada. Aun así, no anotes contraseñas ni datos de pacientes.
- Las notificaciones viajan **cifradas**: Google las entrega a tu celular pero no puede leerlas.
- Los botones de una notificación llevan una firma que solo sirve para esa tarea y esa acción.
- El plan gratuito de Cloudflare sobra: Lancelot usa unas 1 500 ejecuciones al día del reloj de cada minuto y
  muy pocas consultas a la base de datos.
