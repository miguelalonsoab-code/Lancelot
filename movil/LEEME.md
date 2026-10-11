# Lancelot en el celular (Fase 2: etapas 1 y 2)

Un servidor gratis en tu cuenta de Cloudflare y una app web que se instala en tu Android:

- **Escribes** tareas igual que en la laptop: «mañana 8pm pagar la luz», «cada lunes 9am reunión».
  Si falta algo, Lancelot pregunta («¿Para cuándo?», «¿Qué te recuerdo?»).
- **Te avisa** con una notificación cuando vence una tarea, **aunque la app y la laptop estén apagadas**.
  La notificación trae los botones **✓ Hecho** y **+10 min**.
- **Organiza** la lista en vencidas, hoy, mañana y los días siguientes. Toca el círculo para completar
  una tarea; toca la tarea para posponerla, reprogramarla, editarla o borrarla.
- Preguntas que entiende: «¿qué tengo para hoy?», «¿qué tengo vencido?», «pasa las vencidas a mañana», «¿qué hora es?».

> En esta etapa el celular y la laptop todavía tienen **listas separadas**. La sincronización es la etapa 3.

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
- El script crea la base de datos, sube el servidor y genera tu **clave**.
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
| Subir cambios del servidor o de la app | `npm run publicar` |
| Cambiar la clave (perdí el celular) | `npm run configurar -- --nueva-clave` |
| Configurar desde otra PC | Copia `movil/.lancelot-local.json` de esta laptop; si no lo tienes, `npm run configurar` crea una clave nueva |
| Probar todo en la laptop, sin internet | `npm test` y `npm run test:servidor` |
| Ver errores del servidor | dash.cloudflare.com → Workers & Pages → lancelot → *Logs* |

La app del celular se actualiza sola: cada vez que la abres con internet descarga la versión nueva.

## Cómo funciona

```
 celular (app web) ──/api + clave──►  Worker de Cloudflare  ──►  D1 (base de datos SQLite)
        ▲                                   │
        └── notificación cifrada ◄── cada minuto revisa qué venció (Cron)
```

| Archivo | Qué hace |
|---|---|
| `src/index.js` | La API (`/api/tareas`…) y lo que corre cada minuto |
| `src/almacen.js` | Las tareas en D1: mismas operaciones que `nucleo/almacen.py` |
| `src/push.js` | Notificaciones: firma VAPID y cifrado aes128gcm, solo con WebCrypto |
| `src/seguridad.js` | La clave y las firmas de los botones de las notificaciones |
| `publico/comun/*.js` | Intérprete, comandos, fechas y repeticiones: los usan el servidor **y** el celular |
| `publico/app.js` | La app: lista, escribir, preguntas, opciones, ajustes |
| `publico/cara.js` | La cara animada (el mismo personaje de la laptop) |
| `publico/sw.js` | Recibe las notificaciones y hace funcionar sus botones con la app cerrada |
| `migraciones/` | Las tablas de la base de datos (se aplican en orden, una sola vez) |
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
