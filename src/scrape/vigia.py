"""Teto de tempo por anúncio na coleta (24/11/2026).

Em 21 a 23/11 a coleta congelou algumas vezes abrindo um único anúncio (ex.: Sundek 22/11 09h05,
Ville 22/11 16h08). O `page.evaluate` e o `page.content()` do extract_item não têm timeout, então
o passo ficava parado até o teto de 10 min dele e a rodada com falha ainda esperava 5 min antes de
disparar a próxima: 15 a 20 min sem olhar o Vinted.

Agora cada anúncio tem um teto (config.TETO_ANUNCIO_S). Passou dele, uma thread mata o processo
principal do Chromium desta coleta, achado por uma marca única posta na linha de comando dele (o
Chromium ignora opção desconhecida). A chamada travada levanta erro na hora, o anúncio fica de fora
desta rodada (entra na seguinte, como qualquer anúncio que deu erro) e a coleta reabre o navegador.

A thread não chama nada do Playwright (a API síncrona não é segura entre threads): só acha o PID
pela marca e manda SIGKILL.
"""
import os
import signal
import subprocess
import threading
import uuid
from pathlib import Path


def nova_marca() -> str:
    """Opção única para a linha de comando de um Chromium desta coleta."""
    return f"--didi-coleta={os.getpid()}-{uuid.uuid4().hex[:10]}"


def _pids_com(marca: str) -> list[int]:
    """PIDs dos processos cuja linha de comando tem a marca (Linux: /proc; macOS: ps)."""
    pids: list[int] = []
    proc = Path("/proc")
    if (proc / "self" / "cmdline").exists():
        alvo = marca.encode()
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            try:
                if alvo in (d / "cmdline").read_bytes():
                    pids.append(int(d.name))
            except OSError:
                continue
    else:
        try:
            saida = subprocess.run(["ps", "-ww", "-eo", "pid=,args="], capture_output=True,
                                   text=True, timeout=10).stdout
        except Exception:  # noqa: BLE001
            return []
        for linha in saida.splitlines():
            if marca in linha:
                try:
                    pids.append(int(linha.split(None, 1)[0]))
                except ValueError:
                    continue
    return [p for p in pids if p != os.getpid()]


def matar(marca: str) -> int:
    """Mata (SIGKILL) os processos com a marca. Devolve quantos."""
    n = 0
    for pid in _pids_com(marca):
        try:
            os.kill(pid, signal.SIGKILL)
            n += 1
        except OSError:
            continue
    return n


class Teto:
    """`with Teto(60, marca) as t:` — se o bloco passar de `segundos`, mata o navegador da `marca`
    e a chamada do Playwright que estava travada levanta erro. Depois do bloco, `t.estourou` diz se
    foi isso (aí o navegador morreu e precisa ser reaberto). Sem marca ou com segundos <= 0, não faz
    nada."""

    def __init__(self, segundos: float, marca: str | None):
        self.segundos = segundos
        self.marca = marca
        self.estourou = False
        self.mortos = 0
        self._lock = threading.Lock()
        self._ativo = False
        self._timer: threading.Timer | None = None

    def _estoura(self) -> None:
        # O lock garante que, depois do __exit__, a thread não mata mais nada: um navegador
        # reaberto em seguida (marca nova) nunca é atingido por um teto velho.
        with self._lock:
            if not self._ativo:
                return
            self.estourou = True
            self.mortos = matar(self.marca)

    def __enter__(self) -> "Teto":
        if self.marca and self.segundos > 0:
            self._ativo = True
            self._timer = threading.Timer(self.segundos, self._estoura)
            self._timer.daemon = True
            self._timer.start()
        return self

    def __exit__(self, *exc) -> bool:
        with self._lock:
            self._ativo = False
        if self._timer is not None:
            self._timer.cancel()
        return False
