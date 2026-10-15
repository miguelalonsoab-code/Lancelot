-- Etapa 3: sincronizar con la laptop.
-- 'actualizada' = cuándo se hizo el cambio (en el dispositivo donde se hizo): decide quién gana si chocan.
-- 'recibida'    = cuándo llegó al servidor: la laptop pregunta "¿qué llegó desde la última vez?".
ALTER TABLE tareas ADD COLUMN recibida INTEGER NOT NULL DEFAULT 0;
UPDATE tareas SET recibida = actualizada;
CREATE INDEX idx_tareas_recibida ON tareas (recibida);
