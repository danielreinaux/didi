"""Ponto único das chamadas de visão: roteia CADA agente para um provedor/modelo.

Por quê: o gpt-4o e o gpt-4o-mini saem da API da OpenAI em 14/01/2027, e os agentes
baratos que empatam com eles no gabarito (bench modelos2, out/2026) são de outros
provedores (Gemini, Seed, Qwen) servidos pelo OpenRouter.

Uso nos módulos (drop-in de client.chat.completions.create):
    from ..utils import llm
    resp = llm.create("sundek:marca", model=IA["model"], messages=..., max_tokens=200,
                      temperature=0.1, response_format={"type": "json_object"})
    resp.model  → o modelo REALMENTE usado (p/ o cost_tracker)

Roteamento: config.IA_ROTAS[agente] = "openrouter:<modelo>" ou {"to": ..., opções}
  (env IA_ROTAS_JSON sobrepõe agentes sem deploy; IA_ROTAS_DESLIGADAS=1 desliga tudo).
  Sem rota (ou sem OPENROUTER_API_KEY) → chamada legada na OpenAI com o `model` recebido.
  Se o OpenRouter falhar depois dos retries → cai na chamada legada (se ainda existir)
  e loga. Opções: detail ("low"/"high"), reasoning (dict do OpenRouter), provider
  (roteamento do OpenRouter, ex.: {"order": ["google-vertex"], "allow_fallbacks": False}),
  min_tokens, reserva (outra rota do OpenRouter tentada antes da OpenAI).
"""
from __future__ import annotations

import json
import os
import re
import threading

from openai import OpenAI

from ..config import IA_ROTAS

_lock = threading.Lock()
_clients: dict[str, OpenAI] = {}
_BASES = {"openai": None, "openrouter": "https://openrouter.ai/api/v1"}
_KEYS = {"openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


def _client(prov: str) -> OpenAI:
    with _lock:
        if prov not in _clients:
            kw = {"api_key": os.environ[_KEYS[prov]].strip(), "max_retries": 4, "timeout": 120}
            if _BASES[prov]:
                kw["base_url"] = _BASES[prov]
            _clients[prov] = OpenAI(**kw)
        return _clients[prov]


def _rotas() -> dict:
    """config.IA_ROTAS + override opcional em JSON na env IA_ROTAS_JSON (troca/desliga um agente
    sem deploy de código; valor null remove a rota → OpenAI)."""
    extra = os.environ.get("IA_ROTAS_JSON")
    if not extra:
        return IA_ROTAS
    try:
        return {**IA_ROTAS, **json.loads(extra)}
    except Exception:
        return IA_ROTAS


def _rota(agente: str) -> tuple[str | None, dict]:
    spec = (os.environ.get("IA_ROTAS_DESLIGADAS") != "1") and _rotas().get(agente)
    if not spec:
        return None, {}
    opts = dict(spec) if isinstance(spec, dict) else {"to": spec}
    to = opts.pop("to")
    prov = to.split(":", 1)[0]
    if prov == "openrouter" and not os.environ.get("OPENROUTER_API_KEY", "").strip():
        return None, {}  # secret ainda não existe → produção segue na OpenAI
    return to, opts


def _limpa_json(txt: str) -> str:
    """Alguns modelos embrulham o JSON em ```json ... ``` ou põem texto em volta."""
    t = (txt or "").strip()
    try:
        json.loads(t)
        return t
    except Exception:
        pass
    t2 = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    try:
        json.loads(t2)
        return t2
    except Exception:
        pass
    i = t.find("{")
    if i != -1:
        # 1º objeto completo: o gemini-2.5-flash-lite às vezes emite o JSON certo seguido de
        # lixo com '}' (ex.: '{...}\n"}'), que o corte até o último '}' não salva
        try:
            _, fim = json.JSONDecoder().raw_decode(t, i)
            return t[i:fim]
        except Exception:
            pass
    j = t.rfind("}")
    return t[i:j + 1] if i != -1 and j > i else t


def _chamar_rota(to: str, opts: dict, kw: dict):
    prov, modelo = to.split(":", 1)
    kw = dict(kw)
    kw["model"] = modelo
    if opts.get("detail"):
        msgs = []
        for m in kw["messages"]:
            if isinstance(m.get("content"), list):
                m = {**m, "content": [
                    {**p, "image_url": {**p["image_url"], "detail": opts["detail"]}}
                    if p.get("type") == "image_url" else p for p in m["content"]]}
            msgs.append(m)
        kw["messages"] = msgs
    mt = kw.pop("max_tokens", None) or kw.pop("max_completion_tokens", None) or 800
    kw["max_tokens"] = max(mt, opts.get("min_tokens") or 0)
    extra = {}
    if "reasoning" in opts:
        extra["reasoning"] = opts["reasoning"]
    if opts.get("provider"):
        extra["provider"] = opts["provider"]
    if extra:
        kw["extra_body"] = extra
    resp = _client(prov).chat.completions.create(**kw)
    if resp.choices:
        resp.choices[0].message.content = _limpa_json(resp.choices[0].message.content or "")
    if (kw.get("response_format") or {}).get("type") == "json_object":
        # JSON inválido conta como falha da rota → tenta a reserva / a OpenAI
        try:
            json.loads(resp.choices[0].message.content or "")
        except Exception as e:
            raise ValueError(f"JSON inválido de {modelo}") from e
    resp.model = modelo  # nome da rota (o cost_tracker precifica por ele)
    return resp


def tem_rota(agente: str) -> bool:
    """True se o agente vai para uma rota (configurada e com a chave do provedor)."""
    return _rota(agente)[0] is not None


def opcao(agente: str, chave: str, default=None):
    """Opção extra da rota ATIVA do agente (ex.: "colagem", "max_fotos"); default se não há rota."""
    to, opts = _rota(agente)
    return opts.get(chave, default) if to else default


_OPCOES_MODULO = {"colagem", "max_fotos"}  # lidas pelos módulos, não vão para a API


def create(agente: str, fallback: bool = True, **kw):
    """Mesma assinatura do chat.completions.create + o nome do agente ('sundek:marca').
    fallback=False: se a rota falhar (ou não existir), propaga o erro em vez de chamar a OpenAI."""
    to, opts = _rota(agente)
    if to:
        opts = {k: v for k, v in opts.items() if k not in _OPCOES_MODULO}
        reserva = opts.pop("reserva", None)
        try:
            return _chamar_rota(to, opts, kw)
        except Exception as e:  # noqa: BLE001
            erro = e
        auth = getattr(erro, "status_code", None) in (401, 403)  # chave inválida: reserva usa a mesma
        if reserva and not auth:  # 2º modelo (também medido no gabarito) antes de cair na OpenAI
            ropts = dict(reserva) if isinstance(reserva, dict) else {"to": reserva}
            rto = ropts.pop("to")
            print(f"  [llm] {agente} via {to} falhou ({str(erro)[:100]}) → reserva {rto}")
            try:
                return _chamar_rota(rto, ropts, kw)
            except Exception as e:  # noqa: BLE001
                erro = e
        if not fallback:
            raise erro
        print(f"  [llm] {agente} via {to} falhou ({str(erro)[:120]}) → fallback OpenAI {kw.get('model')}")
    elif not fallback:
        raise RuntimeError(f"{agente}: sem rota ativa (OPENROUTER_API_KEY?)")
    resp = _client("openai").chat.completions.create(**kw)
    resp.model = kw.get("model") or resp.model
    return resp
