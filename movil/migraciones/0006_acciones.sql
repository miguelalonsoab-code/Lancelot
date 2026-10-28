-- v3.19: lo que haces en el celular y debe llegar a la laptop (que es la que guarda tu horario y perfil):
--   'hecha'      { actividad_id, dia }                     "ya fui al gimnasio"
--   'excepcion'  { desde, hasta, filtro, titulo }          "mañana no trabajo"
--   'sugerida'   { tarea, actividad_id }                   una tarea agendada desde una sugerencia
--   (v3.20) 'quitar_excepcion' { desde, hasta, filtro } · 'actividad' { nombre, minutos, veces_semana, momento }
--           'quitar_actividad' { id }
--   (v3.21) 'bloque' { dias, inicio, fin, titulo, traslado } · 'quitar_bloque' { id }
--           'perfil' { despertar?, dormir?, meta_estudio? }
-- La laptop las aplica en su próxima sincronización y avisa cuáles ya aplicó (se borran de aquí).
-- El "contexto" que sube la laptop (horario, perfil, actividades…) se guarda en 'ajustes' (clave 'contexto').
CREATE TABLE IF NOT EXISTS acciones (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo    TEXT NOT NULL,
  datos   TEXT NOT NULL,                -- JSON
  creada  INTEGER NOT NULL              -- milisegundos
);
