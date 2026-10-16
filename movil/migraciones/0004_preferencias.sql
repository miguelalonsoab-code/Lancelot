-- v3.11: preferencias que la laptop comparte con el celular (no son tareas):
--   'frases'      tus frases (de frases.txt) para que la cara del celular también las diga
--   'vocabulario' lo que Lancelot aprendió de tus correcciones Tarea/Evento
CREATE TABLE IF NOT EXISTS ajustes (
  clave       TEXT PRIMARY KEY,
  valor       TEXT NOT NULL,            -- JSON
  actualizada INTEGER NOT NULL
);
