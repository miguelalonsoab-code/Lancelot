-- v3.10: eventos (aniversario, examen, viaje…) que avisan con días de anticipación.
--   tipo          'tarea' | 'evento'
--   anticipacion  '7,1' = avisar una semana antes y un día antes (NULL = solo a su hora)
--   aviso_previo  cuándo salió el último aviso anticipado (como 'avisada': no se sincroniza)
ALTER TABLE tareas ADD COLUMN tipo TEXT NOT NULL DEFAULT 'tarea';
ALTER TABLE tareas ADD COLUMN anticipacion TEXT;
ALTER TABLE tareas ADD COLUMN aviso_previo TEXT;
