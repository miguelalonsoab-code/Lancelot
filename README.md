# Lancelot — asistente de escritorio · v3.10

Una carita flotante en tu escritorio que te recuerda tus pendientes y te acompaña a estudiar.
Escribes "mañana 8pm pagar la luz" y a esa hora la cara se pone en alerta,
te muestra una burbuja y Windows lanza una notificación.

## Lancelot en el celular (Fase 2)
- Carpeta **`movil/`**: un servidor gratis en Cloudflare y una app web para tu Android, con la misma cara.
  Anotas tareas escribiendo como en la laptop y te llegan **notificaciones aunque la laptop esté apagada**,
  con botones **✓ Hecho** y **+10 min**.
- Instalación paso a paso en **[movil/LEEME.md](movil/LEEME.md)** (necesita Node.js y tu cuenta de Cloudflare).

## Novedades v3.10: eventos y frases
- 📅 Eventos: aniversarios, exámenes o viajes te avisan una semana y un día antes.
- 💬 Frases: deja el mouse sobre la cara y te dice una (también las tuyas).
- **Eventos además de tareas.** Un evento es algo que *pasa* un día (aniversario, cumpleaños, examen, viaje, cita,
  boda, concierto, reunión…); una tarea es algo que *haces* (limpiar la sala). Lancelot los distingue solo:
  «el 15 de noviembre aniversario» es evento; «estudiar para el examen mañana» es tarea (empieza con un verbo).
- Los eventos te avisan **una semana antes y un día antes** (a las 9:00), además del aviso a su hora ese día.
  Para otro plazo: «…, avísame 3 días antes» o «con 2 semanas de anticipación». Para forzarlo: «evento: …».
- Cumpleaños y aniversarios **se repiten cada año** solos. Nueva repetición: **cada año** («pagar el seguro cada año el 10 de enero»).
- En la lista se ven con 📅 y **«faltan 5 días»**. El saludo de la mañana y «¿qué tengo para hoy?» mencionan los
  eventos de la semana. Cuando el día de un evento pasa, se cierra solo (no queda como «vencida»).
- En el panel, el selector **Tarea / 📅 Evento** muestra lo que entendió; si se equivocó, cámbialo antes de Agregar.
- Por voz: «Lancelot, el 15 de noviembre es mi aniversario» o «Lancelot, nuevo evento: examen final el 2 de diciembre».
- Todo se sincroniza con el celular, y el servidor también manda los avisos anticipados como notificación.
- **Frases**: deja el mouse quieto sobre la cara 1,5 s y te dice una frase (solo si no hay avisos ni estás
  estudiando; como mucho una cada 2 minutos y sin repetir hasta usarlas todas). El clic sigue abriendo el panel.
  Trae 42 (las tuyas incluidas). Agrega las tuyas: **«guarda esta frase: …»** o escribiendo en `frases.txt`
  (carpeta de datos, una por línea). Pide una cuando quieras: **«dime una frase»** o **«motívame»**.
- Celular: ejecuta `npm run configurar` en `movil` (aplica la tabla nueva y sube el servidor).

## Novedades v3.9: laptop y celular sincronizados
- **Una sola lista** en la laptop, el celular y la web: lo que agregas, completas, editas o borras en un lado
  aparece en el otro en menos de un minuto (y a los pocos segundos cuando el cambio es en la laptop).
- Si cambias la misma tarea en los dos lados, **gana el cambio más reciente**.
- **Sin internet** la laptop funciona igual: guarda los cambios y los sube cuando vuelve la conexión.
- Si completas en el celular una tarea que estaba sonando en la laptop, **deja de sonar** sola.
- El panel muestra el estado: «☁ Sincronizado con el celular · 14:05». En el menú: **☁ Sincronizar ahora**.
- La primera vez se suben todas tus tareas actuales. Tu base de datos se actualiza sola, sin perder nada.
- Para activarla: dentro de `movil`, `npm run configurar` (crea `nube.json` en tus carpetas de datos)
  y reinicia Lancelot. Sin ese archivo, Lancelot funciona como antes.

## Novedades v3.8.1
- Conectado a GitHub: desde esta versión, Lancelot se actualiza solo.

## Novedades v3.8: actualizaciones y voz incluida
- **Actualizaciones automáticas**: Lancelot revisa en GitHub si hay una versión nueva (al minuto de abrir y cada
  6 horas). Si la hay, te ofrece **Actualizar · Ahora no · Omitir**. Al aceptar, la descarga, comprueba que el
  archivo esté intacto, se cierra, se instala y vuelve a abrirse solo. Nunca interrumpe una sesión de estudio.
- Pídelo cuando quieras: **"busca actualizaciones"** o **"¿qué versión tienes?"** (también en el menú 🔄).
- **La voz viene en el instalador**: el modelo de reconocimiento y tus voces Piper van dentro, así que en una
  PC nueva funciona sin descargar nada. Tus tareas y apodos nunca van en el instalador.
- `python construir.py --publicar` sube la versión a GitHub (ver "Actualizaciones" abajo).

## Actualizaciones (cómo publicar una versión)
1. Una sola vez:
   - En `config.py`, escribe tu repositorio: `REPO_ACTUALIZACIONES = "tu-usuario/lancelot"`.
   - El repositorio debe ser **público** para que Lancelot lea sus Releases sin contraseñas.
     Si prefieres que tu código siga privado, crea otro repositorio **público y vacío** (p. ej. `lancelot-versiones`)
     solo para publicar los instaladores, y pon ese en `REPO_ACTUALIZACIONES`.
   - Instala GitHub CLI y conéctalo: `winget install --id GitHub.cli -e` y luego `gh auth login`.
2. Cada versión nueva:
   - Sube `VERSION` en `config.py` y agrega su sección `## Novedades vX.Y` en este README (son las notas que verás
     en la burbuja).
   - `git add .`, `git commit -m "..."`, `git push`.
   - `python construir.py --publicar`
3. Tus Lancelot instalados la verán en las próximas horas, o al decir "busca actualizaciones".

## Novedades v3.7: instalador
- **`Lancelot-setup-3.7.exe`**: un solo archivo que instala Lancelot como cualquier programa:
  menú Inicio, inicio con Windows (opcional), acceso en el escritorio (opcional) y **desinstalador** en
  *Configuración → Aplicaciones*. No pide permisos de administrador (se instala solo para tu usuario).
- **Actualizar** = ejecutar el instalador de la versión nueva encima. Tus tareas no se tocan.
- **Desinstalar** te pregunta si también quieres borrar tus datos (por defecto, no).
- Si Lancelot está abierto, el instalador lo detecta y te pide cerrarlo.
- El panel muestra la versión en su título.

## Novedades v3.6: tu día, tu semana y un .exe
- **Saludo del día**: la primera vez que te ve cada día (desde las 6:00), te dice tus pendientes de hoy,
  cuántas vencidas tienes y tu racha de estudio, en la burbuja y en voz alta. Si dejaste la laptop prendida
  de noche, espera a que toques el teclado o el mouse. Pídelo cuando quieras: **"buenos días"** u **"hola"**.
  Se ajusta en `config.py` (`SALUDO_ACTIVO`, `HORA_SALUDO`, `SALUDO_HABLADO`).
- **Tareas vencidas aparte**: arriba del panel, en rojo, con cuánto hace que vencieron. El botón **↻** ofrece
  *En 1 hora · Hoy a las… · Esta noche · Mañana a la misma hora · Mañana 09:00 · Elegir fecha…*.
  **"Todas a mañana →"** las mueve todas de una vez. Por voz: **"¿qué tengo vencido?"** y
  **"pasa las vencidas a mañana"**. "¿Qué tengo para hoy?" ahora también te avisa si hay vencidas.
- **Pestaña 📊 Estudio**: gráfico de barras de los últimos 7 días, con ◀ ▶ para ver semanas anteriores,
  tu mejor día, la comparación con la semana anterior y una línea con tu meta diaria (`META_ESTUDIO_DIARIO`).
  Por voz: **"resumen semanal"** o **"¿cómo voy esta semana?"**.
- **Lancelot.exe**: un programa normal de Windows, sin Python ni terminal (ver "Crear el .exe" abajo).
- Menú de la cara: **📈 Mi semana** y **📁 Carpeta de datos**.
- Actualizar: copiar encima y reemplazar. No hay librerías nuevas (PyInstaller solo si quieres el .exe).

## Crear el .exe y el instalador (opcional)
1. Una sola vez: instala **Inno Setup** (gratis) y PyInstaller:
   ```powershell
   winget install --id JRSoftware.InnoSetup -e -s winget
   pip install pyinstaller
   ```
   (Inno Setup también se descarga de https://jrsoftware.org/isdl.php. `pip` va con el entorno activado.)
2. Cierra Lancelot. En la terminal, dentro de la carpeta y con el entorno activado (`.venv\Scripts\activate`):
   ```powershell
   python construir.py
   ```
3. Tarda unos minutos y crea dos cosas en `dist\`:
   - `Lancelot\Lancelot.exe`: el programa suelto (~300 MB: lleva Python, Qt, Vosk y Piper adentro).
   - `Lancelot-setup-3.7.exe`: el instalador (más liviano, va comprimido). Es el que conviene usar.
   Al final te pregunta si quieres copiar tus datos, quitar el inicio viejo con `iniciar.bat` e instalar.
   Sin Inno Setup, solo crea el .exe y los accesos directos (`python construir.py --sin-instalador` hace lo mismo).
4. **Dónde quedan los datos:** `Lancelot.exe` usa `%LOCALAPPDATA%\Lancelot` (menú → 📁 Carpeta de datos);
   `python main.py` sigue usando `datos\` del proyecto. Así puedes probar cambios sin tocar tus tareas reales,
   y reconstruir el .exe nunca las borra. Solo puede haber uno abierto a la vez.
5. Cada vez que cambies el código: sube `VERSION` en `config.py`, cierra Lancelot, ejecuta
   `python construir.py` e instala el nuevo `Lancelot-setup-X.Y.exe` encima del anterior.
6. Si Windows muestra "Windows protegió su PC" la primera vez: *Más información → Ejecutar de todas formas*.
   Pasa con cualquier programa nuevo sin firma digital; es tu propio código.

## Novedades v3.5: bases sólidas
- **Registro de errores** en `datos/lancelot.log` (rotativo: máximo ~4 MB entre todos). Si algo falla, ahí queda
  el detalle. Con `NIVEL_REGISTRO = "DEBUG"` en config.py también guarda lo que el oído reconoce de tu voz.
- **Copia de seguridad diaria** de tus tareas, sesiones y apodos en `datos/respaldos/` (se guardan 7 días).
  Para restaurar: cierra Lancelot, copia el respaldo sobre `datos/tareas.db` (con ese nombre) y ábrelo.
- **Código reorganizado**: `app.py` se dividió en tres piezas (ver Estructura). El comportamiento es el mismo,
  comprobado con pruebas de integración del asistente completo (`tests/test_app.py`).
- Actualizar: copiar encima y reemplazar. No hay librerías nuevas.

## Novedades v3.4: páginas web y navegadores
- **"Abre Netflix desde Chrome"**, **"entra a YouTube en Edge"**: abre la página en el navegador que digas
  (Chrome, Edge, Firefox, Brave u Opera). Si no está instalado, usa tu navegador predeterminado y te avisa.
- **"Abre Netflix"** sin navegador: si no tienes la app, abre la página en tu navegador predeterminado.
- **"Busca lofi para estudiar en YouTube"** (también Google y Wikipedia, y "… desde Chrome").
- Dominios dichos en voz alta: **"entra a upn punto edu punto pe"**.
- Páginas por nombre en `SITIOS_CONOCIDOS` (config.py): agrega las tuyas. Si no conoce una, la busca en Google.

## Novedades v3.3
- **"Abre Dota"** y cualquier juego de **Steam** instalado (lee tus bibliotecas de Steam, también las de otros discos).
- También encuentra los **accesos directos del escritorio** (juegos de Epic, programas portables…).
- Actualizar: copiar encima y reemplazar. No hay librerías nuevas.

## Novedades v3.2: apodos por voz
- **"Lancelot, cuando diga el código abre Visual Studio Code"** → desde entonces, "abre el código" abre VS Code.
- Se guardan en la base de datos (tabla `apodos`), así que sobreviven a reinicios.
- Antes de guardar, comprueba que la app exista: si oyó mal, no guarda nada.
- **"Olvida el apodo código"** y **"mis apodos"**. También funcionan escritos en el panel.
- Actualizar desde la v3.x: copiar encima y reemplazar. No hay librerías nuevas.

## Novedades v3.1
- **Lancelot pregunta lo que falta.** "Recuérdame comprar pan" → *"¿Para cuándo?"* → "mañana a las ocho".
  "Recuérdame mañana a las 5" → *"¿Qué te recuerdo?"*. Di "olvídalo" para cancelar.
  Si no te entiende dos veces o no respondes, te deja la tarea en el panel (nunca se pierde).
- **Apodos para apps** en `APPS_EXTRA` (config.py): `"el código": "Visual Studio Code"`.
- Actualizar desde la v3: copiar encima y reemplazar. No hay librerías nuevas.

## Novedades v3: voz
- **Se llama Lancelot** (o "Lance"). Di **"Lancelot, abre Spotify"**, **"Lance, modo estudio"**,
  **"Lancelot, recuérdame mañana a las ocho de la noche pagar la luz"**, **"Lance, ¿qué tengo para hoy?"**.
- **Escucha continua** (botón 🎙 o menú): espera oír su nombre. Apagada por defecto.
- **Atajo Ctrl + Alt + Espacio** (o botón 🗣): lo pulsas una vez y hablas, sin decir el nombre.
- **Responde con voz**: con voces de Windows o con una voz Piper (más natural) que pongas en `datos/voces/`.
- Todo funciona **sin internet** (salvo la descarga única del modelo de voz, 39 MB). Nada de lo que dices sale de tu laptop.
- La voz solo **abre** apps del menú Inicio o páginas de `APPS_EXTRA`; nunca ejecuta comandos del sistema.

### Actualizar desde la v2 (hay librerías nuevas)
1. Cierra el asistente. Copia el contenido del zip encima de tu carpeta (reemplazar). No borres `.venv` ni `datos`.
2. En la terminal, dentro de la carpeta: `.venv\Scripts\activate` y luego `pip install -r requirements.txt`
3. `python probar_voz.py` → prueba micrófono, reconocimiento y voz paso a paso.
4. Abre `iniciar.bat`.

### Voces más naturales (Piper, gratis)
1. Escucha las voces en https://rhasspy.github.io/piper-samples/ (elige idioma Español).
2. Descárgalas de https://huggingface.co/rhasspy/piper-voices/tree/main/es → `es_MX`, `es_ES` o `es_AR`
   → la voz → la calidad (`medium` es buen equilibrio) → baja **los dos archivos**: `.onnx` y `.onnx.json`.
3. Ponlos en `datos/voces/` (crea la carpeta). Si hay varias, se usa la primera por orden alfabético.
4. Reinicia el asistente.

### Comandos de voz (también sirven escritos)
| Dices / escribes | Hace |
|---|---|
| `abre <app>` | Abre una app del menú Inicio, un juego de Steam, un acceso del escritorio o una página de `APPS_EXTRA` |
| `abre <página> desde <navegador>` | "abre netflix desde chrome", "entra a youtube en edge" |
| `busca <algo> en youtube/google` | Abre la búsqueda (opcional: "… desde chrome") |
| `qué hora es` | Te dice la hora |
| `qué tengo para hoy` · `mis tareas` | Te lee tus pendientes de hoy |
| `recuérdame … <cuándo> …` · `anota …` | Crea una tarea; si falta el qué o el cuándo, te lo pregunta |
| `escúchame` / `deja de escuchar` | Activa o apaga la escucha continua |
| `cuando diga <apodo> abre <app>` | Aprende un apodo para una app |
| `olvida el apodo <apodo>` · `mis apodos` | Borra un apodo · lista tus apodos |
| + todos los comandos del modo estudio y silencio | |

## Novedades v2.1
- **Editar tareas**: botón ✎ en cada tarea. Cambias el texto, la fecha o la repetición y pulsas **Guardar**.
  Si escribes una fecha nueva en el texto ("mañana 10am"), se aplica sola.

## Novedades v2
- **Modo estudio** con pomodoros, frases de aliento en cada cambio de etapa, resumen del día y racha de días.
- **Detección de distracciones** (solo durante el estudio, solo mira el título de la ventana activa).
- **Modo silencio**: sin sonidos ni notificaciones de Windows.
- **Comandos** en el mismo cuadro de las tareas.
- **Instancia única**: si abres el asistente dos veces, solo se abre el panel de la copia que ya corre.

## Actualizar desde la v1 sin perder tus tareas
1. Cierra el asistente (clic derecho en la cara → **Salir**).
2. Descomprime el zip nuevo y copia su contenido **encima** de tu carpeta actual, aceptando **reemplazar** archivos.
3. **No borres** `.venv` (tus librerías) ni `datos` (tus tareas): el zip no los trae, así que no se tocan.
4. Abre `iniciar.bat`. No hace falta instalar nada nuevo.

## Instalación (Windows 11)

1. Instala **Python 3.11 o superior** desde https://www.python.org/downloads/
   (en el instalador marca **"Add python.exe to PATH"**).
2. Descomprime esta carpeta donde quieras (por ejemplo `Documentos\asistente`).
3. Abre una terminal en esa carpeta (clic derecho → "Abrir en Terminal") y ejecuta:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

La cara aparece abajo a la derecha. La próxima vez basta con doble clic en `iniciar.bat`.

### Que arranque solo al prender la laptop
1. `Win + R` → escribe `shell:startup` → Enter.
2. En la carpeta que se abre, crea un **acceso directo** a `iniciar.bat`.

(Si usas el .exe, `python construir.py` crea este acceso por ti.)

## Uso

| Acción | Resultado |
|---|---|
| Clic en la cara | Abre / cierra "Mis tareas" |
| Arrastrar la cara | La mueves (recuerda la posición) |
| Clic derecho en la cara o en el ícono de la bandeja | Menú: tareas, ocultar cara, salir |
| Burbuja de aviso | ✓ Hecho · +10 min · +1 h |
| ✎ / ✓ / ✕ en cada tarea | Editar · completar · eliminar |
| ↻ en una vencida | Reprogramar (en 1 hora, esta noche, mañana…) |
| Pestaña 📊 Estudio | Gráfico de la semana; ◀ ▶ semanas anteriores |

## Comandos (en el cuadro de texto del panel)

| Escribes | Hace |
|---|---|
| `modo estudio` · `a estudiar` · `pomodoro` | Empieza pomodoros de 25 min (descanso 5, largo 15 cada 4) |
| `modo estudio 50` | Bloques de 50 min (el descanso crece: 10 min) |
| `pausa` / `seguir` | Pausa o reanuda; tras un descanso, `seguir` arranca el siguiente bloque |
| `terminar` | Cierra la sesión y la guarda |
| `modo silencio` · `no molestar` | Sin sonido ni notificaciones de Windows |
| `modo normal` | Quita el silencio y termina el estudio |
| `cuánto estudié hoy` · `resumen` | Tu día en una burbuja |
| `resumen semanal` · `cómo voy esta semana` | Tu semana (y abre la pestaña 📊 Estudio) |
| `buenos días` · `hola` | El saludo con tus pendientes de hoy |
| `vencidas` · `qué tengo vencido` | Lista tus tareas vencidas |
| `pasa las vencidas a mañana` | Las mueve todas a mañana, a la misma hora |
| `busca actualizaciones` · `qué versión tienes` | Revisa si hay una versión nueva en GitHub |
| `dime una frase` · `motívame` | Una frase (las tuyas incluidas) |
| `guarda esta frase: …` | La agrega a `frases.txt` para que te la diga de vez en cuando |

Si el texto no es un comando, se guarda como tarea. Mientras escribes, debajo dice cuál de los dos entendió.

**Durante el estudio:** el anillo violeta se vacía con el tiempo y abajo ves los minutos.
Los mensajes de aliento salen al terminar cada bloque y cada descanso, no en medio
(interrumpir la concentración para animarte sería contraproducente).
Si pasas más de 1 minuto en YouTube, TikTok, etc., la cara te mira de reojo y pregunta.
**"Es para estudiar"** deja de avisar por esa ventana durante la sesión.
La lista de distracciones y los tiempos se cambian en `config.py`; las frases, en `nucleo/frases.py`.

**Colores del anillo:** turquesa = nada para hoy · ámbar = hay tareas hoy (el número dice cuántas) ·
naranja latiendo = algo venció · verde = completaste algo · azul oscuro = durmiendo (de noche) · violeta = estudiando · verde agua = descanso ·
naranja con ojos entrecerrados = te pilló distraído.

**Frases que entiende:**
```
mañana 8pm pagar la luz           en 20 minutos estirar
el viernes a las 3 llamar al banco  15/10 10:30 entregar informe
esta noche a las 8 llamar a mamá    el 20 de octubre cumple de Juan
cada lunes 9am reunión              de lunes a viernes a las 7am tomar agua
todos los días a las 10 de la noche tomar pastilla
el 15 de noviembre aniversario      📅 evento: avisa 1 semana y 1 día antes (y se repite cada año)
evento: cena con amigos el sábado, avísame 3 días antes
pagar el seguro cada año el 10 de enero
```
Mientras escribes ves cómo lo entendió ("Entendí: …"). Si se equivocó, corrige
la fecha o la repetición en los selectores antes de pulsar **Agregar**.
Ojo: "a las 3" sin "am" se entiende como 15:00 (lo más común al hablar).

## Estructura

```
main.py                  arranque
construir.py             crea dist\Lancelot\Lancelot.exe (PyInstaller) y el instalador (Inno Setup)
instalador/lancelot.iss  receta del instalador: qué copia, accesos directos, desinstalación
registro.py              registro de errores en datos/lancelot.log
config.py                nombre, colores, tiempos (personaliza aquí)
nucleo/                  lógica pura, sin interfaz
  almacen.py             SQLite: guardar, completar, posponer
  interprete.py          texto en español -> título + fecha + repetición + ¿tarea o evento?
  planificador.py        repeticiones, avisos anticipados de eventos y "ánimo" de la cara
  pomodoro.py            máquina de estados del pomodoro (sin reloj propio: fácil de probar)
  comandos.py            "modo estudio 50" -> Comando("estudio", 50)
  frases.py              frases de aliento (estudio) y las que dice al dejar el mouse sobre la cara
  distraccion.py         ¿la ventana activa es una distracción?
  numeros.py             "a las ocho y media" -> "a las 8 y media" (para la voz)
  hablado.py             20:40 -> "a las 8 y 40 de la noche"
  dialogo.py             "¿para cuándo?" / "¿qué te recuerdo?": completa tareas por voz
  respaldo.py            copia de seguridad diaria de la base de datos
  saludo.py              el saludo del día (textos para la burbuja y la voz)
  estadisticas.py        la semana de estudio: totales, mejor día, comparación
  version.py             comparar versiones y leer las Releases de GitHub
sensores/
  ventana_activa.py      título y programa de la ventana al frente (API de Windows)
  inactividad.py         segundos sin tocar teclado ni mouse (para no saludar a nadie)
voz/
  oido.py                micrófono + Vosk (reconocimiento local) + nombre "Lancelot"
  habla.py               voz: Piper o voces de Windows, en un hilo aparte
  despertar.py           separa el nombre de la orden
  apps.py                catálogo de apps del menú Inicio para "abre …"
  atajo.py               Ctrl+Alt+Espacio desde cualquier app
  web.py                 páginas conocidas, búsquedas y "abrir en Chrome/Edge/Firefox…"
probar_voz.py            diagnóstico de voz paso a paso
movil/                   Lancelot en el celular: servidor Cloudflare + app web (ver movil/LEEME.md)
notificadores/           canales de aviso (en la Fase 2 se agrega el del celular)
  base.py                contrato común
  windows.py             notificación nativa + sonido
interfaz/                todo lo visual (PySide6)
  cara.py                la carita animada
  burbuja.py             avisos y mensajes junto a la cara
  estudio.py             modo estudio: pomodoro + frases + distracciones + sesiones
  panel.py               ventana "Mis tareas" (pestañas Tareas y 📊 Estudio)
  grafico.py             gráfico de barras de la semana (QPainter)
  actualizador.py        buscar, descargar (verificando) e instalar versiones nuevas
  sincronizador.py       sincronización con el servidor (y el celular), en segundo plano
  app.py                 director: crea las piezas, tareas, comandos, estado de la cara, menú
  avisos.py              qué muestra la burbuja y en qué orden (tareas primero, mensajes después)
  asistente_voz.py       oír, hablar, diálogo, abrir apps y páginas, apodos
tests/                   pruebas: núcleo, estudio, voz e integración del asistente completo
datos/tareas.db          se crea solo (puedes abrirlo con DB Browser for SQLite)
datos/frases.txt         tus frases, una por línea (se crea sola la primera vez)
```

## Pruebas
```powershell
python -m unittest discover tests -v
cd movil; npm test                 # el intérprete JavaScript da lo mismo que el de Python, y más
```
`tests/casos_interprete.json` es el "contrato" entre los dos intérpretes (laptop y celular).
Si cambias el de Python, regenéralo con `python tests/generar_casos.py`.
