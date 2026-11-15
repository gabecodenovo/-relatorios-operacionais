"""Regras de negocio do SmartOps CLI.

Aqui ficam a classificacao automatica de prioridade, o calculo de SLA e de
atraso e a montagem do resumo executivo usado pelo comando ``report``.
Nenhuma dependencia externa: apenas a biblioteca padrao.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

# SLA em dias corridos por prioridade
SLA_POR_PRIORIDADE = {"ALTA": 3, "MEDIA": 7, "BAIXA": 15}

# Categorias que puxam a prioridade para cima
CATEGORIAS_CRITICAS = {
    "suporte",
    "urgencia",
    "urgente",
    "manutencao",
    "sistema",
}

STATUS_CONCLUIDO = "CONCLUIDO"


def calcular_prioridade(valor: float, prazo_dias: int, categoria: str = "") -> str:
    """Classifica a prioridade de uma demanda por valor, prazo e categoria.

    A pontuacao soma:

    * valor: >= R$ 5.000 -> 2 pontos, >= R$ 2.000 -> 1 ponto;
    * prazo: <= 2 dias -> 3 pontos, <= 5 -> 2 pontos, <= 10 -> 1 ponto;
    * categoria critica (suporte, urgencia, sistema...) -> 2 pontos.

    ``ALTA`` a partir de 5 pontos, ``MEDIA`` a partir de 3, ``BAIXA`` abaixo.
    """
    pontos = 0

    if valor >= 5000:
        pontos += 2
    elif valor >= 2000:
        pontos += 1

    if prazo_dias <= 2:
        pontos += 3
    elif prazo_dias <= 5:
        pontos += 2
    elif prazo_dias <= 10:
        pontos += 1

    if (categoria or "").strip().lower() in CATEGORIAS_CRITICAS:
        pontos += 2

    if pontos >= 5:
        return "ALTA"
    if pontos >= 3:
        return "MEDIA"
    return "BAIXA"


def para_data(valor) -> date:
    """Converte texto ISO, ``date`` ou ``datetime`` em ``date``."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "")[:10]
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        return date.today()


def data_limite(registro: dict) -> date:
    """Data limite de entrega: criacao + prazo em dias."""
    prazo = int(registro.get("prazo_dias") or 0)
    return para_data(registro.get("criado_em")) + timedelta(days=prazo)


def esta_atrasado(registro: dict, hoje: date | None = None) -> bool:
    """Um registro esta atrasado quando o prazo passou e ele nao foi concluido."""
    hoje = hoje or date.today()
    if registro.get("status") == STATUS_CONCLUIDO:
        return False
    return hoje > data_limite(registro)


def enriquecer(registro: dict, hoje: date | None = None) -> dict:
    """Devolve uma copia do registro com campos calculados de SLA e atraso."""
    hoje = hoje or date.today()
    dados = dict(registro)
    limite = data_limite(registro)
    dados["data_limite"] = limite.isoformat()
    dados["dias_restantes"] = (limite - hoje).days
    dados["atrasado"] = esta_atrasado(registro, hoje)
    dados["sla_dias"] = SLA_POR_PRIORIDADE.get(registro.get("prioridade"), 0)
    return dados


def enriquecer_todos(registros: list[dict], hoje: date | None = None) -> list[dict]:
    """Aplica :func:`enriquecer` em uma lista de registros."""
    hoje = hoje or date.today()
    return [enriquecer(registro, hoje) for registro in registros]


def _agrupar(registros: list[dict], campo: str) -> dict:
    """Agrupa quantidade e valor total por um campo."""
    grupos: dict = {}
    for registro in registros:
        chave = registro.get(campo) or "NAO INFORMADO"
        grupo = grupos.setdefault(chave, {"quantidade": 0, "valor": 0.0})
        grupo["quantidade"] += 1
        grupo["valor"] += float(registro.get("valor") or 0)
    return dict(sorted(grupos.items()))


def gerar_resumo(registros: list[dict], hoje: date | None = None) -> dict:
    """Monta o resumo executivo (totais, distribuicoes, criticos e atrasados)."""
    hoje = hoje or date.today()
    registros = enriquecer_todos(registros, hoje)

    total = len(registros)
    valor_total = sum(float(r.get("valor") or 0) for r in registros)
    valor_aberto = sum(
        float(r.get("valor") or 0)
        for r in registros
        if r.get("status") != STATUS_CONCLUIDO
    )
    concluidos = sum(1 for r in registros if r.get("status") == STATUS_CONCLUIDO)
    atrasados = [r for r in registros if r.get("atrasado")]
    criticos = [
        r
        for r in registros
        if r.get("prioridade") == "ALTA" and r.get("status") != STATUS_CONCLUIDO
    ]

    return {
        "total": total,
        "valor_total": valor_total,
        "valor_aberto": valor_aberto,
        "ticket_medio": valor_total / total if total else 0.0,
        "taxa_conclusao": (concluidos / total * 100) if total else 0.0,
        "por_status": _agrupar(registros, "status"),
        "por_prioridade": _agrupar(registros, "prioridade"),
        "por_categoria": _agrupar(registros, "categoria"),
        "atrasados": atrasados,
        "criticos": criticos,
    }
