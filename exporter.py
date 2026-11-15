"""Exportacao dos relatorios do SmartOps CLI para CSV e JSON."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

PASTA_PADRAO = Path(__file__).resolve().parent / "exports"

# Ordem das colunas no CSV exportado
COLUNAS = (
    "id",
    "cliente",
    "titulo",
    "categoria",
    "valor",
    "prazo_dias",
    "prioridade",
    "status",
    "observacao",
    "criado_em",
    "data_limite",
    "dias_restantes",
    "atrasado",
)


def pasta_de_saida(pasta=None) -> Path:
    """Garante que a pasta de exportacao exista e devolve o caminho."""
    destino = Path(pasta) if pasta else PASTA_PADRAO
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _caminho_arquivo(pasta: Path, extensao: str) -> Path:
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    return pasta / f"smartops_{carimbo}.{extensao}"


def exportar_csv(registros: list[dict], pasta=None) -> Path:
    """Exporta os registros para um CSV com data/hora no nome."""
    arquivo = _caminho_arquivo(pasta_de_saida(pasta), "csv")
    with arquivo.open("w", newline="", encoding="utf-8") as saida:
        escritor = csv.DictWriter(saida, fieldnames=COLUNAS)
        escritor.writeheader()
        for registro in registros:
            escritor.writerow({coluna: registro.get(coluna, "") for coluna in COLUNAS})
    return arquivo


def exportar_json(registros: list[dict], pasta=None) -> Path:
    """Exporta os registros para um JSON identado com data/hora no nome."""
    arquivo = _caminho_arquivo(pasta_de_saida(pasta), "json")
    with arquivo.open("w", encoding="utf-8") as saida:
        json.dump(registros, saida, ensure_ascii=False, indent=2, default=str)
    return arquivo


def exportar(registros: list[dict], formato: str = "ambos", pasta=None) -> list[Path]:
    """Exporta no formato pedido (``csv``, ``json`` ou ``ambos``)."""
    formato = (formato or "ambos").lower()
    arquivos: list[Path] = []

    if formato in ("csv", "ambos"):
        arquivos.append(exportar_csv(registros, pasta))
    if formato in ("json", "ambos"):
        arquivos.append(exportar_json(registros, pasta))

    if not arquivos:
        raise ValueError("Formato invalido. Use csv, json ou ambos.")
    return arquivos
