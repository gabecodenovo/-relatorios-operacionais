"""Camada de persistencia do SmartOps CLI.

Responsavel por abrir a conexao SQLite, criar a tabela ``records`` e executar
o CRUD usado pela interface de linha de comando. Apenas biblioteca padrao.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PADRAO = Path(__file__).resolve().parent / "smartops.db"

STATUS_VALIDOS = ("ABERTO", "EM_ANDAMENTO", "CONCLUIDO")
PRIORIDADES_VALIDAS = ("ALTA", "MEDIA", "BAIXA")

# Colunas que a camada de CLI pode atualizar em um registro existente.
CAMPOS_ATUALIZAVEIS = {
    "status",
    "observacao",
    "prioridade",
    "valor",
    "prazo_dias",
    "categoria",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente TEXT NOT NULL,
    titulo TEXT NOT NULL,
    categoria TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0,
    prazo_dias INTEGER NOT NULL DEFAULT 0,
    prioridade TEXT NOT NULL DEFAULT 'BAIXA',
    status TEXT NOT NULL DEFAULT 'ABERTO',
    observacao TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_status ON records (status);
CREATE INDEX IF NOT EXISTS idx_records_prioridade ON records (prioridade);
"""


def conectar(caminho=None) -> sqlite3.Connection:
    """Abre a conexao com o banco (padrao: ``smartops.db`` ao lado dos modulos)."""
    destino = Path(caminho) if caminho else DB_PADRAO
    conexao = sqlite3.connect(str(destino))
    conexao.row_factory = sqlite3.Row
    return conexao


def inicializar(conexao: sqlite3.Connection) -> None:
    """Cria a tabela e os indices caso ainda nao existam."""
    conexao.executescript(SCHEMA)
    conexao.commit()


def agora() -> str:
    """Data/hora atual no formato ISO (segundos), usada nas colunas de tempo."""
    return datetime.now().isoformat(timespec="seconds")


def inserir(
    conexao: sqlite3.Connection,
    cliente: str,
    titulo: str,
    categoria: str,
    valor: float,
    prazo_dias: int,
    prioridade: str,
    status: str = "ABERTO",
    observacao: str = "",
    criado_em: str | None = None,
) -> int:
    """Insere um registro e devolve o ID gerado."""
    criado = criado_em or agora()
    cursor = conexao.execute(
        """
        INSERT INTO records
            (cliente, titulo, categoria, valor, prazo_dias, prioridade,
             status, observacao, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cliente.strip(),
            titulo.strip(),
            categoria.strip(),
            float(valor),
            int(prazo_dias),
            prioridade,
            status,
            observacao.strip(),
            criado,
            criado,
        ),
    )
    conexao.commit()
    return int(cursor.lastrowid)


def listar(
    conexao: sqlite3.Connection,
    status: str | None = None,
    prioridade: str | None = None,
    categoria: str | None = None,
) -> list[dict]:
    """Lista registros com filtros opcionais, priorizando os mais urgentes."""
    sql = "SELECT * FROM records WHERE 1 = 1"
    parametros: list = []

    if status:
        sql += " AND status = ?"
        parametros.append(status)
    if prioridade:
        sql += " AND prioridade = ?"
        parametros.append(prioridade)
    if categoria:
        sql += " AND categoria LIKE ?"
        parametros.append(f"%{categoria}%")

    sql += (
        " ORDER BY"
        " CASE prioridade WHEN 'ALTA' THEN 0 WHEN 'MEDIA' THEN 1 ELSE 2 END,"
        " CASE status WHEN 'ABERTO' THEN 0 WHEN 'EM_ANDAMENTO' THEN 1 ELSE 2 END,"
        " id"
    )
    return [dict(linha) for linha in conexao.execute(sql, parametros)]


def obter(conexao: sqlite3.Connection, registro_id: int) -> dict | None:
    """Busca um registro pelo ID (ou ``None`` se nao existir)."""
    linha = conexao.execute(
        "SELECT * FROM records WHERE id = ?", (registro_id,)
    ).fetchone()
    return dict(linha) if linha else None


def atualizar(conexao: sqlite3.Connection, registro_id: int, **campos) -> bool:
    """Atualiza colunas permitidas de um registro. Devolve True se alterou."""
    invalidos = set(campos) - CAMPOS_ATUALIZAVEIS
    if invalidos:
        raise ValueError(
            "Campos nao permitidos na atualizacao: " + ", ".join(sorted(invalidos))
        )
    if not campos:
        return False

    campos["atualizado_em"] = agora()
    atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
    valores = list(campos.values()) + [registro_id]
    cursor = conexao.execute(
        f"UPDATE records SET {atribuicoes} WHERE id = ?", valores
    )
    conexao.commit()
    return cursor.rowcount > 0


def limpar(conexao: sqlite3.Connection) -> None:
    """Remove todos os registros e reinicia o contador de IDs."""
    conexao.execute("DELETE FROM records")
    conexao.execute("DELETE FROM sqlite_sequence WHERE name = 'records'")
    conexao.commit()


def total(conexao: sqlite3.Connection) -> int:
    """Quantidade de registros no banco."""
    return int(conexao.execute("SELECT COUNT(*) FROM records").fetchone()[0])
