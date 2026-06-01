"""Pacing global para chamadas OpenAI — respeita os limites do Tier 1.

Tier 1: gpt-4o = 30.000 TPM | gpt-4o-mini = 200.000 TPM.
Cada chamada de visão usa ~11-18K tokens, então mesmo o mini estoura se
várias threads disparam juntas. Este módulo força um intervalo mínimo entre
chamadas, separado por modelo, compartilhado entre todas as threads.

Se subir de tier, aumente os limites (Tier 2: gpt-4o 450K → pode quase zerar).
"""
import threading
import time

# Intervalo mínimo entre chamadas (segundos). Calibrado pelos limites REAIS da
# conta (confirmados por header e por teste de rajada: 45 chamadas concorrentes,
# 0x 429). NÃO é Tier 1.
#   gpt-4o-mini: 2.000.000 TPM, 5000 req/min
#   gpt-4o:        450.000 TPM, 5000 req/min
# Chamadas de visão: mini ~18-20K tokens, gpt-4o ~14-20K.
#   gpt-4o: p/ não estourar 450K TPM com ~20K/chamada → 22/min (2.7s). Usamos 4s
#           de margem (~15/min, ~300K TPM).
#   mini:   2M TPM dá folga enorme; 1.5s (~40/min) fica muito longe do teto.
INTERVALO_GPT4O = 4.0
INTERVALO_MINI = 1.5

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
