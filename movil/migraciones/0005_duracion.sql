-- v3.14: cuánto dura una tarea o evento ("examen de 8 a 10" = 120 minutos). NULL = no se dijo.
ALTER TABLE tareas ADD COLUMN duracion INTEGER;
