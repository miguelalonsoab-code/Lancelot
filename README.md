# Lancelot — asistente de escritorio · v3.5

Una carita flotante en tu escritorio que te recuerda tus pendientes y te acompaña a estudiar.
Escribes "mañana 8pm pagar la luz" y a esa hora la cara se pone en alerta,
te muestra una burbuja y Windows lanza una notificación.

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

## Uso

| Acción | Resultado |
|---|---|
| Clic en la cara | Abre / cierra "Mis tareas" |
| Arrastrar la cara | La mueves (recuerda la posición) |
| Clic derecho en la cara o en el ícono de la bandeja | Menú: tareas, ocultar cara, salir |
| Burbuja de aviso | ✓ Hecho · +10 min · +1 h |
| ✎ / ✓ / ✕ en cada tarea | Editar · completar · eliminar |

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
```
Mientras escribes ves cómo lo entendió ("Entendí: …"). Si se equivocó, corrige
la fecha o la repetición en los selectores antes de pulsar **Agregar**.
Ojo: "a las 3" sin "am" se entiende como 15:00 (lo más común al hablar).

## Estructura

```
main.py                  arranque
registro.py              registro de errores en datos/lancelot.log
config.py                nombre, colores, tiempos (personaliza aquí)
nucleo/                  lógica pura, sin interfaz
  almacen.py             SQLite: guardar, completar, posponer
  interprete.py          texto en español -> título + fecha + repetición
  planificador.py        repeticiones y "ánimo" de la cara
  pomodoro.py            máquina de estados del pomodoro (sin reloj propio: fácil de probar)
  comandos.py            "modo estudio 50" -> Comando("estudio", 50)
  frases.py              frases de aliento por momento (edítalas a tu gusto)
  distraccion.py         ¿la ventana activa es una distracción?
  numeros.py             "a las ocho y media" -> "a las 8 y media" (para la voz)
  hablado.py             20:40 -> "a las 8 y 40 de la noche"
  dialogo.py             "¿para cuándo?" / "¿qué te recuerdo?": completa tareas por voz
  respaldo.py            copia de seguridad diaria de la base de datos
sensores/
  ventana_activa.py      título y programa de la ventana al frente (API de Windows)
voz/
  oido.py                micrófono + Vosk (reconocimiento local) + nombre "Lancelot"
  habla.py               voz: Piper o voces de Windows, en un hilo aparte
  despertar.py           separa el nombre de la orden
  apps.py                catálogo de apps del menú Inicio para "abre …"
  atajo.py               Ctrl+Alt+Espacio desde cualquier app
  web.py                 páginas conocidas, búsquedas y "abrir en Chrome/Edge/Firefox…"
probar_voz.py            diagnóstico de voz paso a paso
notificadores/           canales de aviso (en la Fase 2 se agrega el del celular)
  base.py                contrato común
  windows.py             notificación nativa + sonido
interfaz/                todo lo visual (PySide6)
  cara.py                la carita animada
  burbuja.py             avisos y mensajes junto a la cara
  estudio.py             modo estudio: pomodoro + frases + distracciones + sesiones
  panel.py               ventana "Mis tareas"
  app.py                 director: crea las piezas, tareas, comandos, estado de la cara, menú
  avisos.py              qué muestra la burbuja y en qué orden (tareas primero, mensajes después)
  asistente_voz.py       oír, hablar, diálogo, abrir apps y páginas, apodos
tests/                   pruebas: núcleo, estudio, voz e integración del asistente completo
datos/tareas.db          se crea solo (puedes abrirlo con DB Browser for SQLite)
```

## Pruebas
```powershell
python -m unittest discover tests -v
```
