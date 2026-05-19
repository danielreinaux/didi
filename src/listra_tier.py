"""Avalia a combinação cor do short + cores das listras e retorna um tier de combo.

Baseado no histórico de 380 compras e no feedback de votação do dono.

Regras:
- Cores sempre ruins independente das listras: amarelo, vermelho, roxo, verde-limão, neon
- Listras neutras (azul, branco, cinza, preto) salvam cores "ok" como laranja, verde, coral
- Listras monocromáticas (mesma cor do short) são seguras quando a cor base já é boa
"""

# Cores de short que listras NEUTRAS conseguem salvar (de "ok" para "boa")
_CORES_SALVAVEIS = {"laranja", "coral", "salmão", "verde", "verde médio", "fucsia"}

# Listras consideradas neutras/valorizadas
_LISTRAS_NEUTRAS = {"azul", "branco", "cinza", "preto", "azul escuro", "azul marinho"}

# Listras top do histórico (azul 108x, laranja 70x, verde 38x, amarela 35x, salmão 34x)
_LISTRAS_TOP = {"azul", "laranja", "verde", "amarela", "salmão", "azul escuro"}

# Cores que listras não salvam — ruim absoluto
_CORES_RUIM_ABSOLUTO = {"amarelo", "amarelo discreto", "vermelho", "vermelho médio", "roxo",
                         "verde-limão", "verde limão", "rosa", "rosa suave"}


def avaliar_combo(cor_short: str, cores_listras: list[str], tier_cor: str) -> dict:
    """
    Retorna dict com:
      - listra_tier: "salva" | "neutra" | "penaliza" | "sem_listra"
      - tier_final: tier ajustado considerando a combinação
      - motivo: string explicativa
    """
    cor = (cor_short or "").lower().strip()
    listras = [c.lower().strip() for c in (cores_listras or [])]

    # Sem listras
    if not listras:
        return {
            "listra_tier": "sem_listra",
            "tier_final": tier_cor,
            "motivo": "sem listras laterais",
        }

    # Cor ruim absoluto — listras não salvam
    for ruim in _CORES_RUIM_ABSOLUTO:
        if ruim in cor:
            return {
                "listra_tier": "penaliza",
                "tier_final": "ruim",
                "motivo": f"cor '{cor_short}' é ruim independente das listras",
            }

    # Cor salvável + listras neutras → sobe um nível
    eh_salvavel = any(s in cor for s in _CORES_SALVAVEIS)
    tem_listra_neutra = any(ln in listras for ln in _LISTRAS_NEUTRAS)

    if eh_salvavel and tem_listra_neutra:
        tier_upgrades = {
            "ruim": "ok",
            "ok": "boa",
            "boa": "boa",
            "muito_boa": "muito_boa",
            "maravilhoso": "maravilhoso",
        }
        tier_novo = tier_upgrades.get(tier_cor, tier_cor)
        return {
            "listra_tier": "salva",
            "tier_final": tier_novo,
            "motivo": f"listras {listras} neutras salvam '{cor_short}': {tier_cor}→{tier_novo}",
        }

    # Listras top do histórico em cor já boa → confirma
    tem_listra_top = any(lt in listras for lt in _LISTRAS_TOP)
    if tem_listra_top:
        return {
            "listra_tier": "neutra",
            "tier_final": tier_cor,
            "motivo": f"listras {listras} confirmam tier '{tier_cor}'",
        }

    # Listras raras (roxa, dourada, rosa) em cor ok → penaliza levemente
    _LISTRAS_RARAS = {"roxa", "roxo", "dourado", "dourada", "rosa"}
    tem_listra_rara = all(lr in _LISTRAS_RARAS for lr in listras)
    if tem_listra_rara and tier_cor in ("ok", "boa"):
        tier_downs = {"boa": "ok", "ok": "ruim"}
        tier_novo = tier_downs.get(tier_cor, tier_cor)
        return {
            "listra_tier": "penaliza",
            "tier_final": tier_novo,
            "motivo": f"listras raras {listras}: {tier_cor}→{tier_novo}",
        }

    return {
        "listra_tier": "neutra",
        "tier_final": tier_cor,
        "motivo": f"listras {listras} sem impacto no tier '{tier_cor}'",
    }
