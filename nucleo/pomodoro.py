"""
Pomodoro como "máquina de estados" pura (sin Qt, sin reloj propio).

Quien la usa le pasa la hora actual (`ahora`) en cada llamada. Así se puede
probar sin esperar 25 minutos reales: en las pruebas se le pasa una hora inventada.

Fases y transiciones:

    enfoque ──(se acaba el tiempo)──► descanso  (o descanso_largo cada N ciclos)
    descanso ──(se acaba el tiempo)──► esperando   ← espera a que digas "seguir"
    esperando ──(seguir)──► enfoque

¿Por qué "esperando" y no arrancar el siguiente enfoque solo? Si te levantaste y
no volviste, el asistente contaría minutos de estudio falsos. Mejor que confirmes.
"""
from __future__ import annotations

from datetime import datetime, timedelta

ENFOQUE = "enfoque"
DESCANSO = "descanso"
DESCANSO_LARGO = "descanso_largo"
ESPERANDO = "esperando"


class Pomodoro:
    def __init__(self, minutos_enfoque: int = 25, minutos_descanso: int = 5,
                 minutos_descanso_largo: int = 15, ciclos_para_largo: int = 4):
        self.duraciones = {
            ENFOQUE: timedelta(minutes=minutos_enfoque),
            DESCANSO: timedelta(minutes=minutos_descanso),
            DESCANSO_LARGO: timedelta(minutes=minutos_descanso_largo),
        }
        self.ciclos_para_largo = ciclos_para_largo
        self.fase = ESPERANDO
        self.completados = 0                 # enfoques terminados completos
        self.pausado = False
        self._fin: datetime | None = None    # cuándo termina la fase actual
        self._restante_en_pausa = timedelta(0)
        self._enfoque_parcial = timedelta(0) # minutos de un enfoque cortado a la mitad

    # ------------------------------------------------------------- consultas
    @property
    def minutos_enfoque(self) -> int:
        return int(self.duraciones[ENFOQUE].total_seconds() // 60)

    def restante(self, ahora: datetime) -> timedelta:
        if self.fase == ESPERANDO or self._fin is None:
            return timedelta(0)
        if self.pausado:
            return self._restante_en_pausa
        return max(self._fin - ahora, timedelta(0))

    def progreso(self, ahora: datetime) -> float:
        """0.0 = recién empieza la fase, 1.0 = terminó."""
        if self.fase == ESPERANDO:
            return 1.0
        total = self.duraciones[self.fase].total_seconds()
        return 1.0 - self.restante(ahora).total_seconds() / total

    def minutos_enfocados(self, ahora: datetime) -> int:
        """Tiempo real de enfoque: ciclos completos + lo que lleva del actual."""
        total = self.duraciones[ENFOQUE] * self.completados + self._enfoque_parcial
        if self.fase == ENFOQUE:
            total += self.duraciones[ENFOQUE] - self.restante(ahora)
        return int(total.total_seconds() // 60)

    # --------------------------------------------------------------- acciones
    def iniciar_enfoque(self, ahora: datetime):
        self._entrar(ENFOQUE, ahora)

    def pausar(self, ahora: datetime):
        if self.fase != ESPERANDO and not self.pausado:
            self._restante_en_pausa = self.restante(ahora)
            self.pausado = True

    def reanudar(self, ahora: datetime):
        if self.pausado:
            self._fin = ahora + self._restante_en_pausa
            self.pausado = False

    def saltar_descanso(self, ahora: datetime):
        if self.fase in (DESCANSO, DESCANSO_LARGO, ESPERANDO):
            self._entrar(ENFOQUE, ahora)

    def cortar_enfoque(self, ahora: datetime):
        """Al terminar la sesión en medio de un enfoque, se guarda lo avanzado."""
        if self.fase == ENFOQUE:
            self._enfoque_parcial += self.duraciones[ENFOQUE] - self.restante(ahora)
        self.fase = ESPERANDO
        self.pausado = False

    def avanzar(self, ahora: datetime) -> list[str]:
        """
        Se llama cada segundo. Devuelve los eventos que ocurrieron:
          "fin_enfoque"  -> terminó un enfoque (ya empezó el descanso)
          "fin_descanso" -> terminó el descanso (ahora está esperando)
        """
        eventos = []
        if self.pausado or self.fase == ESPERANDO:
            return eventos
        if ahora >= self._fin:
            if self.fase == ENFOQUE:
                self.completados += 1
                largo = self.completados % self.ciclos_para_largo == 0
                # El descanso empieza cuando terminó el enfoque, no "ahora"
                # (por si la laptop estuvo suspendida un rato)
                self._entrar(DESCANSO_LARGO if largo else DESCANSO, self._fin)
                eventos.append("fin_enfoque")
            else:
                self.fase = ESPERANDO
                eventos.append("fin_descanso")
        return eventos

    # ---------------------------------------------------------------- privado
    def _entrar(self, fase: str, desde: datetime):
        self.fase = fase
        self.pausado = False
        self._fin = desde + self.duraciones[fase]
