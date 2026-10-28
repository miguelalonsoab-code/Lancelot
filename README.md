# Lancelot — asistente de escritorio · v3.24

Una carita flotante en tu escritorio que te recuerda tus pendientes y te acompaña a estudiar.
Escribes "mañana 8pm pagar la luz" y a esa hora la cara se pone en alerta,
te muestra una burbuja y Windows lanza una notificación.

## Lancelot en el celular (Fase 2)
- Carpeta **`movil/`**: un servidor gratis en Cloudflare y una app web para tu Android, con la misma cara.
  Anotas tareas escribiendo como en la laptop y te llegan **notificaciones aunque la laptop esté apagada**,
  con botones **✓ Hecho** y **+10 min**.
- Instalación paso a paso en **[movil/LEEME.md](movil/LEEME.md)** (necesita Node.js y tu cuenta de Cloudflare).

## Novedades v3.24: tema Zafiro completo, guiones en español, categoría por voz y nombres en la semana
- **Tema Zafiro** (sistema de diseño de Lancelot) en la laptop y en el celular: fondo azul marino, pestañas en
  píldora, botones con iconos de línea y letras **Manrope** (texto) y **JetBrains Mono** (horas y fechas), que
  vienen dentro del programa y de la app (licencia SIL OFL, `interfaz/fuentes/` y `movil/publico/fuentes/`).
- Sin emoji en la interfaz ni en los mensajes de Lancelot. Se quedan solo en las **notificaciones del sistema**
  (Android solo muestra texto ahí). La cara mantiene sus colores de ánimo; el resto usa los del tema.
- Los nombres largos de la semana se parten **por sílabas con guion** («Com-pu-ta-ción»), con un separador en
  español propio (`nucleo/silabas.py` y `movil/publico/comun/silabas.js`, mismos resultados en las dos).
- **Categoría por texto o voz**: «computación gráfica es clase», «marca inglés como otro», «la categoría de IHC
  es curso». Cambia todos los bloques con ese nombre (laptop y celular).
- En la vista **Semana**, las tareas y eventos también muestran su nombre si el rectángulo tiene alto.
- Arreglado (venía de la v3.20): en el celular el botón Mes/Semana elegido no se veía marcado.
- App del celular 1.9 (`npm run configurar` para publicarla). El servidor no cambia.

## Novedades v3.23: el horario con el sistema de diseño de Lancelot
- 🎨 Colores nuevos para las categorías: **trabajo** azul medio, **clase** lavanda (texto oscuro encima) y
  **otro** gris pizarra. Se distinguen por claridad, no solo por tono (pensado para daltonismo), y ya no hay
  naranja: en el sistema de diseño el naranja significa «vencida».
- Iconos de línea (maletín, birrete, etiqueta) en lugar de emoji, en la laptop y en el celular.
- En la pestaña **Horario** (laptop) y en «Horario, días libres y actividades» (celular), cada bloque tiene el
  selector **Trabajo · Clase · Otro**. **Desde el celular ya puedes cambiar la categoría**: la laptop la guarda.
- Un bloque nuevo con el **mismo nombre** que uno que ya tienes toma su categoría: marcas «Computación Gráfica»
  como clase una vez y los demás días salen bien.
- Semana: leyenda con las categorías en la laptop; tareas y eventos van con borde (sin relleno) para no
  confundirse con los bloques; en el celular el nombre del bloque va en 11 px y se parte con guion.
- Servidor 1.8 (acción `categoria_bloque`). Sin migración de la nube: `npm run configurar` para publicarlo.

## Novedades v3.22: categorías en el horario (trabajo, clase, otro), con colores y nombres en el calendario
- 🎨 Cada bloque de tu horario ahora tiene una **categoría**: 💼 trabajo (azul), 🎓 clase (naranja) o 📌 otro (gris).
  Lancelot la deduce del nombre al anotarlo («trabajo en Sanna», «oficina», «turno» → trabajo; «clase de redes»,
  «curso», «universidad», «taller», «laboratorio» → clase; el resto, otro). Tus bloques de antes se clasifican solos.
- 🗓 En la **semana** de la laptop y del celular cada bloque lleva su color **y su nombre adentro**
  (rayado y tachado si ese día no va). En la agenda del día el bloque también muestra su categoría.
- ✏️ Si Lancelot se equivocó, en la pestaña **Horario** de la laptop toca el botón 💼/🎓/📌 de la fila:
  da la vuelta trabajo → clase → otro. El cambio llega al celular en la siguiente sincronización.
- Servidor 1.7: el bloque que anotas desde el celular manda su categoría. Los celulares sin actualizar
  siguen funcionando (la laptop la deduce). **No hace falta migración de la nube**; vuelve a ejecutar
  `npm run configurar` para publicar el servidor nuevo.
- 🧹 `salir()` ahora detiene los relojes (antes podían dispararse con la base ya cerrada; solo se notaba en las pruebas).

## Novedades v3.21: botones en el aviso de hueco libre, horario editable desde el celular y semana en la laptop
- 💡 La notificación «Tienes un hueco libre» trae **✓ Lo hago** (la actividad cuenta como hecha hoy) y
  **⏰ Más tarde** (te lo vuelve a proponer en 1 hora, si estás libre; si no, cuando quedes libre ese día).
- 🗓 Desde el celular ahora también cambias tu **horario fijo** («horario: miércoles de 7:30 pm a 10:40 pm
  Computación Gráfica», «borra el horario de trabajo») y tu **sueño y meta** («me duermo a las 11:30»,
  «meta de estudio 90 minutos»), o en Calendario → «Horario, días libres y actividades». La laptop lo aplica.
- 📅 En la pestaña Calendario de la laptop: botones **Mes / Semana**. La semana se dibuja en 7 columnas
  (gris = horario, rayado = no va, verde = libre, turquesa = tareas, lila = eventos); clic en un día = su agenda.
- Servidor 1.6. Opcional en `vars` de wrangler.jsonc: `MINUTOS_MAS_TARDE` (60 por defecto).

## Novedades v3.20: calendario en la laptop, semana en el celular y más control desde el celular
- 📅 **Laptop**: pestaña **Calendario** con el mes (en negrita los días con tareas, lila con eventos, verde
  los días libres) y la agenda del día elegido: horario, tareas, huecos libres y sugerencias con «📌 Agendar».
- 🗓 **Celular**: en Calendario, botón **Semana**: 7 columnas con tu día de arriba a abajo (gris = horario,
  verde = libre, turquesa = tareas, lila = eventos). Toca un día para ver su agenda.
- 💡 **Aviso de hueco libre en el celular**: cuando sales del trabajo o termina una clase, el servidor te
  manda una notificación con la sugerencia, aunque la laptop esté apagada. Si estabas frente a la laptop y
  ella ya te lo dijo, el celular no lo repite. Se apaga con `SUGERENCIAS_EN_CELULAR = False` en config.py.
- 🏖 **Desde el celular** ahora también puedes quitar días libres y agregar o quitar actividades
  («actividad: yoga 45 min 2 veces por semana», «borra la actividad yoga», o en Calendario → «Días libres y
  actividades»). La laptop lo aplica al sincronizar.
- «en las mañanas» ya no queda pegado al nombre de una actividad («Meditar 10 min cada día en las mañanas»).

## Novedades v3.19: tu horario y tus sugerencias en el celular, y vista Calendario
- 📱 El celular ya sabe tu horario, días libres, perfil y actividades: la laptop se los pasa en la
  sincronización de siempre (solo cuando cambian). **Ejecuta `npm run configurar`** (migración nueva).
- 🗓 Pestaña **Calendario** en el celular: el mes con puntitos (tareas y 📅 eventos; verde = día libre) y la
  agenda del día que toques: tu horario, tareas, 🕒 huecos libres y 💡 sugerencias con «📌 Agendar».
- En el celular ahora puedes: «¿qué hago hoy?» / «¿qué hago mañana?» (+ Agendar), «ya fui al gimnasio»
  (o ✓ en la sugerencia), «el viernes no trabajo» / «vacaciones del 20 al 30 de diciembre», «mis días
  libres», «¿cuándo estoy libre mañana?» y «mi horario».
- Lo que haces en el celular se ve al instante allí y la laptop lo guarda en su próxima sincronización
  («🏖 Desde el celular: vie 23/10 · No trabajo»).
- Las tareas 💡 agendadas desde una sugerencia tampoco salen como vencidas en el celular.
- El horario fijo, el perfil y las actividades se siguen editando en la laptop (cambian poco).
- El celular calcula horas libres y sugerencias con la misma lógica que la laptop (portada a JavaScript y
  comparada con Python en las pruebas, como el intérprete).

## Novedades v3.18: «más tarde, a las 8» y un resumen más honesto
- ⏰ Cuando te sugiere algo, puedes escribir o decir **«más tarde, a las 8»** (o «luego a las 8:30 de la
  noche»): te lo propone a esa hora exacta, aunque antes empiece otro hueco. «8» es la próxima vez que sean
  las 8 (si ya pasaron las 8 de la mañana, las 8 de la noche).
- 📌 Si agendas algo desde una sugerencia y casi nunca lo haces, la pestaña 📊 Estudio y el «resumen
  semanal» te lo dicen: «Agendaste Gimnasio 3 veces y lo hiciste 1. Quizá esa hora no te sirve…».
- 💡 Lo agendado desde una sugerencia ya no aparece en **vencidas**: pasada su hora sigue en próximas tareas
  con 💡 («era a las 18:15 · si no la haces, mañana se quita sola»). En el celular todavía se ve como vencida.

## Novedades v3.17: «Más tarde» y control de lo aprendido
- ⏰ El aviso de hueco libre tiene un tercer botón, **Más tarde**: no cuenta como rechazo y te lo vuelve a
  proponer en 1 hora (si estás libre) o al empezar tu próximo hueco (`MINUTOS_MAS_TARDE`).
- 💡 La pestaña 🗓 Horario muestra **NO TE SUGIERO**: lo que aprendió de tus «Ahora no» («Leer · en la
  noche»). Con ✕ lo olvidas solo a eso.
- 📌 Lo que agendas desde una sugerencia y no haces se **borra solo al día siguiente** (también del celular),
  en vez de quedarse en vencidas. Si lo completas, aquí o en el celular, cuenta para tu actividad.

## Novedades v3.16: sugerencias que aprenden y se agendan
- 📌 «¿Qué hago hoy?» trae el botón **Agendar** (o di «agéndalo»): cada sugerencia pasa a ser una tarea con
  su hora y duración. Te avisa a esa hora y, al completarla, cuenta para tu meta.
- Lo que ya agendaste no se vuelve a sugerir (y «Estudiar» agendado cuenta para tu meta del día).
- El aviso de hueco libre tiene **✓ Lo hago** (estudiar abre el modo estudio; una actividad cuenta como
  hecha hoy) y **Ahora no**.
- Si dices «Ahora no» 2 veces a lo mismo en el mismo momento del día (mañana/tarde/noche), durante 3 semanas
  no te lo sugiere ahí. «Vuelve a sugerirme todo» lo olvida. Se ajusta en config.py
  (`RECHAZOS_PARA_APRENDER`, `DIAS_QUE_RECUERDA_RECHAZOS`).
- No sugiere nada en los primeros 30 min después de despertar (`MINUTOS_PARA_ARRANCAR`).
- La pestaña 📊 Estudio muestra tus actividades de esos 7 días: «💪 Actividades: Gimnasio 2 de 3 · Leer 5 de 7».

## Novedades v3.15: Lancelot te sugiere qué hacer
- 💡 Pregúntale «¿qué hago hoy?» o «recomiéndame algo para mañana»: arma un plan con tus horas libres.
- 💪 Di «ya fui al gimnasio» (o marca «○ hoy» en 🙂 Perfil) y cuenta para tu meta de la semana.
- **Cómo decide**: primero estudiar si no llegaste a tu meta del día (sesiones de hasta 100 min); después
  tus actividades con meta semanal, primero las más atrasadas («llevas 1 de 3 y quedan 2 días»); al final las
  que no tienen meta. Cada una va en su momento preferido (mañana/tarde/noche) si hay hueco; si no, en otro,
  y te lo dice («no hay hueco en la tarde»). Lo que no entra se avisa: «No entra hoy: Gimnasio».
- **Al quedar libre** (sales del trabajo, termina una clase) te propone lo que toca: «Estás libre hasta las
  19:00. ¿Qué tal Gimnasio?». Una vez por hueco, solo si estás frente a la laptop.
  Se apaga con `SUGERENCIAS_AL_QUEDAR_LIBRE = False` en config.py.
- El saludo del día incluye la primera sugerencia, y la pestaña 🗓 Horario muestra las de hoy.
- Completar una tarea que se llama como una actividad («Gimnasio», «Leer el libro…») también cuenta.
- Por ahora solo en la laptop (el celular responde «eso lo hago en la laptop»).

## Novedades v3.14: duración de tus planes y días libres
- ⏱ Tareas y eventos con duración: «examen el viernes de 8 a 10», «cine el sábado 7pm durante 2 horas».
- 🏖 Días que tu horario no se cumple: «el 1 de noviembre no trabajo», «vacaciones del 20 al 30 de diciembre».
- La duración se ve en la lista (laptop y celular: «De 08:00 a 10:00») y **resta de tus horas libres**.
- **⚠ Choques**: si un evento o algo con duración se cruza con tu horario (por ejemplo, con el trabajo),
  Lancelot te avisa al anotarlo y en la vista previa del panel. No lo impide: solo te avisa.
  Una tarea de un momento («llamar al banco a las 10») no avisa: se puede hacer en el trabajo.
- **Excepciones** (por voz, en la caja de tareas o en el campo de la pestaña 🗓 Horario):
  «mañana no tengo clases», «el viernes es feriado», «el 15 tengo libre», «no voy al gimnasio el lunes»,
  «del 28 de diciembre al 3 de enero son mis vacaciones». «No trabajo» o «no tengo clases» liberan solo
  esos bloques; «feriado», «vacaciones» o «tengo libre», todo el horario. «Mis días libres» las lista; se
  quitan con ✕ en la pestaña 🗓 Horario. Las que pasaron hace más de 30 días se borran solas.
- Servidor 1.3: guarda la duración (migración `0005_duracion.sql`). Una laptop o celular viejo que no la
  conoce no la borra al editar.

## Novedades v3.13: tu perfil y el tiempo de traslado
- 🙂 Lancelot conoce tu perfil: a qué hora te despiertas y te duermes, tu meta de estudio y tus actividades.
- 🚌 El viaje al trabajo o a clases también resta de tus horas libres.
- **Perfil** (pestaña **🙂 Perfil** o por voz): «me despierto a las 6:30», «me duermo a las 11 de la noche»,
  «meta de estudio 2 horas», «actividad: gimnasio 1 hora 3 veces por semana en la tarde», «me gusta leer
  30 min todos los días», «mis actividades», «borra la actividad gimnasio».
- **«¿Qué sabes de mí?»** te muestra todo lo que Lancelot sabe: sueño, meta, horario y actividades.
- Tus horas de sueño reemplazan a `HORA_DESPERTAR`/`HORA_DORMIR` de config.py (que quedan como valor inicial):
  las usan las horas libres y la cara de noche. Tu meta de estudio la usa el gráfico de la semana.
- **Traslado**: al anotar un bloque, «…, traslado 45 min» o «… con 1 hora de viaje»; o después:
  «al trabajo tardo 45 minutos». Se resta antes y después del bloque.
- Las actividades todavía no generan recomendaciones: eso es lo próximo (usa justamente estos datos).

## Novedades v3.12.1: la voz ya no se queda muda
- 🔊 Arreglado: Lancelot decía la primera frase y después se quedaba callado. Ahora habla todos los avisos.
- La voz de Windows (Sabina) se usa directamente por SAPI; la librería pyttsx3, que tenía ese fallo, queda solo de respaldo.
- `python probar_voz.py` ahora dice tres frases seguidas: si escuchas las tres, la voz funciona bien.

## Novedades v3.12: tu horario y tus horas libres
- 🗓 Anota tu horario fijo y Lancelot calcula tus horas libres de cada día.
- 🕒 Pregúntale «¿cuándo estoy libre?» o «tiempo libre mañana».
- **Horario fijo**: lo que te ocupa cada semana. Escríbelo en el panel (pestaña **🗓 Horario**) o dilo:
  «horario: de lunes a viernes de 9am a 6pm trabajo», «estoy ocupado martes y jueves de 7 a 10 de la noche
  clase de redes», «sábados de 8 a 12 inglés». Entiende «de lunes a viernes», «martes y jueves», «fines de semana»,
  «todos los días», horas con am/pm, «de la noche» y «8:30-17:30». Para borrar: ✕ en la lista o «borra el horario de trabajo».
- **Horas libres**: entre `HORA_DESPERTAR` y `HORA_DORMIR` (config.py), menos tu horario; huecos de 30 min o más.
  Se ven en la pestaña Horario (hoy y mañana) y en el saludo de la mañana («🕒 Libre hoy: …»).
- Un turno que pasa la medianoche se anota en dos partes («lunes de 10pm a 12am» y «martes de 12am a 6am»).
- Es la base de la próxima versión: que Lancelot te **recomiende** qué hacer en esos huecos.
- Solo en la laptop por ahora (el celular todavía no ve el horario).

## Novedades v3.11: frases en voz alta y Lancelot aprende
- 🗣 Las frases ahora también se dicen en voz alta (en la laptop y, al tocar la cara, en el celular).
- 🧠 Si corriges Tarea/Evento dos veces por lo mismo, Lancelot lo aprende.
- **Lista ordenada**: arriba **TAREAS VENCIDAS** (siempre a la vista: «Ninguna. Vas al día 👌» cuando no hay),
  luego **📅 PRÓXIMOS EVENTOS** y al final **PRÓXIMAS TAREAS**. Igual en el celular. Los eventos ya no
  cuentan como vencidos («pasa las vencidas a mañana» no los mueve).
- **Frases habladas**: además de la burbuja, la dice con su voz (salvo modo silencio; se apaga con
  `FRASES_HABLADAS = False` en config.py). En el celular: toca la cara y te dice una (⚙ → Voz para apagarla);
  también «motívame» o «dime una frase». Tus frases de `frases.txt` viajan al celular.
- **Hora de los avisos anticipados** configurable: `HORA_AVISO_PREVIO` en config.py (para el celular, ver `movil/LEEME.md`).
- **Sin avisos repetidos**: si la laptop ya te mostró «📅 falta 1 semana», el celular no te lo vuelve a mandar
  (espera 5 minutos para saberlo); y si te lo mandó el celular mientras la laptop estaba apagada, la laptop no lo repite.
- **Aprende de tus correcciones**: si cambias «Cita con el banco» de 📅 Evento a Tarea dos veces, deja de tomar
  «cita» como evento. Funciona al revés («Taller de pintura» → evento) y se desaprende corrigiendo en sentido
  contrario. Lo aprendido también lo usa el celular.
- Arreglo: la primera sincronización con muchas tareas viejas ahora va en lotes chicos (antes podía rechazarse).
- Celular: `npm run configurar` en `movil` (tabla nueva `0004` y servidor nuevo).

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
| `dime una frase` · `motívame` | Una frase, en voz alta (las tuyas incluidas) |
| `guarda esta frase: …` | La agrega a `frases.txt` para que te la diga de vez en cuando |
| `horario: de lunes a viernes de 9am a 6pm trabajo` | Anota un bloque fijo en tu horario |
| `mi horario` · `¿cuándo estoy libre?` · `tiempo libre mañana` | Tu horario y tus horas libres |
| `me despierto a las 6:30` · `me duermo a las 11` · `meta de estudio 2 horas` | Tu perfil |
| `actividad: gimnasio 1 hora 3 veces por semana en la tarde` · `mis actividades` | Lo que te gusta hacer |
| `al trabajo tardo 45 minutos` | Tiempo de traslado de un bloque del horario |
| `¿qué sabes de mí?` | Todo lo que Lancelot sabe de ti |

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
  aprendizaje.py         aprende de tus correcciones Tarea/Evento
  horario.py             tu horario fijo ("de lunes a viernes de 9 a 6 trabajo") y tus horas libres
  perfil.py              tu perfil: horas de sueño, meta de estudio y actividades
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
