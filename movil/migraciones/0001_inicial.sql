-- Base de datos de Lancelot en Cloudflare (D1, que es SQLite: lo mismo que tareas.db de la laptop).
-- Las migraciones se aplican en orden y una sola vez: para cambiar algo, se agrega 0002_..., nunca se edita esta.

CREATE TABLE tareas (
    id          TEXT    PRIMARY KEY,               -- identificador único (UUID): sirve igual en laptop y celular
    titulo      TEXT    NOT NULL,
    fecha       TEXT    NOT NULL,                  -- 'AAAA-MM-DD HH:MM' en hora de Lima (como en la laptop)
    repeticion  TEXT,                              -- diaria | laborables | semanal | mensual | NULL
    estado      TEXT    NOT NULL DEFAULT 'pendiente',   -- pendiente | hecha
    avisada     INTEGER NOT NULL DEFAULT 0,        -- 1 = ya se mandó la notificación de esta ocurrencia
    creada      TEXT    NOT NULL,
    completada  TEXT,
    actualizada INTEGER NOT NULL,                  -- milisegundos del último cambio (para sincronizar con la laptop)
    borrada     INTEGER NOT NULL DEFAULT 0         -- se marca en vez de borrar: la laptop tiene que enterarse
);
CREATE INDEX idx_tareas_aviso   ON tareas (estado, borrada, avisada, fecha);
CREATE INDEX idx_tareas_cambios ON tareas (actualizada);

-- Celulares (o navegadores) que aceptaron recibir notificaciones
CREATE TABLE suscripciones (
    endpoint    TEXT PRIMARY KEY,                  -- dirección del servicio de notificaciones (de Google en Android)
    p256dh      TEXT NOT NULL,                     -- clave pública del celular para cifrar el mensaje
    auth        TEXT NOT NULL,                     -- secreto compartido con el celular
    dispositivo TEXT,
    creada      TEXT NOT NULL
);
