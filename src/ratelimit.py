"""Pacing global para chamadas OpenAI — respeita os limites do Tier 1.

Tier 1: gpt-4o = 30.000 TPM | gpt-4o-mini = 200.000 TPM.
Cada chamada de visão usa ~11-18K tokens, então mesmo o mini estoura se
várias threads disparam juntas. Este módulo força um intervalo mínimo entre
chamadas, separado por modelo, compartilhado entre todas as threads.

Se subir de tier, aumente os limites (Tier 2: gpt-4o 450K → pode quase zerar).
"""
import threading
import time

# Intervalo mínimo entre chamadas (segundos).
# Chamadas de visão são pesadas: mini ~18-20K tokens, gpt-4o ~14-18K.
# gpt-4o: 30K TPM ÷ ~16K/chamada ≈ 1.8/min → 38s de folga.
# mini:  200K TPM ÷ ~19K/chamada ≈ 10/min → 9s de folga.
INTERVALO_GPT4O = 38.0
INTERVALO_MINI = 13.0

_lock_4o = threading.Lock()
_lock_mini = threading.Lock()
_ultima_4o = 0.0
_ultima_mini = 0.0


def pace_gpt4o() -> None:
    """Bloqueia até ser seguro fazer outra chamada gpt-4o.
    Sleep FORA do lock pra não travar outras threads."""
    global _ultima_4o
    with _lock_4o:
        agora = time.monotonic()
        espera = INTERVALO_GPT4O - (agora - _ultima_4o)
        # reserva o slot adiantando o relógio — outras threads vão esperar a partir daqui
        _ultima_4o = agora + max(espera, 0)
    if espera > 0:
        time.sleep(espera)


def pace_mini() -> None:
    """Bloqueia até ser seguro fazer outra chamada gpt-4o-mini.
    Sleep FORA do lock pra não travar outras threads."""
    global _ultima_mini
    with _lock_mini:
        agora = time.monotonic()
        espera = INTERVALO_MINI - (agora - _ultima_mini)
        _ultima_mini = agora + max(espera, 0)
    if espera > 0:
        time.sleep(espera)
