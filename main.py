#!/usr/bin/env python3
"""SmartOps CLI - triagem, registro e relatorios operacionais.

Exemplos:
    python main.py seed
    python main.py add --cliente "Padaria Pao Dourado" --titulo "Automacao do estoque" \
        --categoria Automacao --valor 3500 --prazo 5 --obs "Planilha com 3 abas duplicadas"
    python main.py list --status ABERTO --prioridade ALTA
    python main.py update 3 --status CONCLUIDO --obs "Entrega validada pelo cliente"
    python main.py report
    python main.py export --formato ambos
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

import database
import exporter
import processor


# ---------------------------------------------------------------------------
# Formatacao de saida
# ---------------------------------------------------------------------------
def formatar_moeda(valor) -> str:
    texto = "{:,.2f}".format(float(valor or 0))
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data(valor) -> str:
    return processor.para_data(valor).strftime("%d/%m/%Y")


CABECALHO = "{:>4}  {:<18} {:<30} {:<12} {:>12} {:<8} {:<13} {:>8}".format(
    "ID", "CLIENTE", "TITULO", "CATEGORIA", "VALOR", "PRIOR.", "STATUS", "SLA"
)
SEPARADOR = "-" * len(CABECALHO)


def linha_tabela(registro: dict) -> str:
    dias = registro.get("dias_restantes")
    if not isinstance(dias, int):
        dias = 0
    if registro.get("status") == "CONCLUIDO":
        sla = "-"
    elif registro.get("atrasado"):
        sla = f"{abs(dias)}d atras"
    else:
        sla = f"{dias}d"
    return "{:>4}  {:<18} {:<30} {:<12} {:>12} {:<8} {:<13} {:>8}".format(
        registro["id"],
        str(registro["cliente"])[:18],
        str(registro["titulo"])[:30],
        str(registro["categoria"])[:12],
        formatar_moeda(registro["valor"]),
        str(registro["prioridade"]),
        str(registro["status"]),
        sla,
    )


def imprimir_distribuicao(titulo: str, grupos: dict) -> None:
    print(titulo)
    for chave, dados in grupos.items():
        print(
            "  {:<14} {:>3} registro(s)  {}".format(
                chave, dados["quantidade"], formatar_moeda(dados["valor"])
            )
        )


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def cmd_add(conexao, args) -> int:
    cliente = args.cliente.strip()
    titulo = args.titulo.strip()
    categoria = args.categoria.strip()

    if not cliente or not titulo or not categoria:
        print("Erro: --cliente, --titulo e --categoria nao podem ficar vazios.")
        return 1
    if args.valor < 0:
        print("Erro: --valor nao pode ser negativo.")
        return 1
    if args.prazo < 0:
        print("Erro: --prazo nao pode ser negativo.")
        return 1

    prioridade = processor.calcular_prioridade(args.valor, args.prazo, categoria)
    registro_id = database.inserir(
        conexao,
        cliente=cliente,
        titulo=titulo,
        categoria=categoria,
        valor=args.valor,
        prazo_dias=args.prazo,
        prioridade=prioridade,
        observacao=args.obs or "",
    )

    print(f"Registro #{registro_id} criado com sucesso.")
    print(f"  Cliente ....: {cliente}")
    print(f"  Titulo .....: {titulo}")
    print(f"  Categoria ..: {categoria}")
    print(f"  Valor ......: {formatar_moeda(args.valor)}")
    print(f"  Prazo ......: {args.prazo} dia(s)")
    print(f"  Prioridade .: {prioridade} (calculada automaticamente)")
    print(f"  SLA ........: {processor.SLA_POR_PRIORIDADE.get(prioridade, 0)} dia(s)")
    return 0


def cmd_list(conexao, args) -> int:
    registros = processor.enriquecer_todos(
        database.listar(
            conexao,
            status=args.status,
            prioridade=args.prioridade,
            categoria=args.categoria,
        )
    )

    if not registros:
        print("Nenhum registro encontrado com esses filtros.")
        return 0

    print(CABECALHO)
    print(SEPARADOR)
    for registro in registros:
        print(linha_tabela(registro))
    print(SEPARADOR)
    print(f"{len(registros)} registro(s) listado(s).")
    return 0


def cmd_update(conexao, args) -> int:
    registro = database.obter(conexao, args.id)
    if registro is None:
        print(f"Erro: registro #{args.id} nao encontrado.")
        return 1

    campos = {}
    if args.status:
        campos["status"] = args.status
    if args.obs is not None:
        campos["observacao"] = args.obs.strip()

    if not campos:
        print("Nada a atualizar. Informe --status e/ou --obs.")
        return 1

    database.atualizar(conexao, args.id, **campos)

    print(f"Registro #{args.id} atualizado.")
    print(
        "  Status ......: {} -> {}".format(
            registro["status"], campos.get("status", registro["status"])
        )
    )
    print(
        "  Observacao ..: {}".format(
            campos.get("observacao", registro["observacao"]) or "(vazia)"
        )
    )
    if campos.get("status") == "CONCLUIDO":
        print("  Registro marcado como concluido; nao entra mais nos atrasados.")
    return 0


def cmd_report(conexao, args) -> int:
    registros = processor.enriquecer_todos(database.listar(conexao))
    if not registros:
        print("Banco vazio. Rode 'python main.py seed' para popular a demonstracao.")
        return 1

    resumo = processor.gerar_resumo(registros)

    print("=" * 66)
    print("SMARTOPS - RESUMO EXECUTIVO".center(66))
    print("=" * 66)
    print(f"Registros .........: {resumo['total']}")
    print(f"Valor total .......: {formatar_moeda(resumo['valor_total'])}")
    print(f"Valor em aberto ...: {formatar_moeda(resumo['valor_aberto'])}")
    print(f"Ticket medio ......: {formatar_moeda(resumo['ticket_medio'])}")
    print(f"Taxa de conclusao .: {resumo['taxa_conclusao']:.1f}%")
    print()
    imprimir_distribuicao("Distribuicao por status", resumo["por_status"])
    print()
    imprimir_distribuicao("Distribuicao por prioridade", resumo["por_prioridade"])
    print()
    imprimir_distribuicao("Distribuicao por categoria", resumo["por_categoria"])
    print()

    print(f"Itens criticos (prioridade ALTA ainda abertos): {len(resumo['criticos'])}")
    if resumo["criticos"]:
        for registro in resumo["criticos"]:
            print(
                "  #{} {} - {} ({})".format(
                    registro["id"],
                    registro["cliente"],
                    registro["titulo"],
                    registro["status"],
                )
            )
    else:
        print("  (nenhum)")

    print()
    print(f"Itens atrasados: {len(resumo['atrasados'])}")
    if resumo["atrasados"]:
        for registro in resumo["atrasados"]:
            print(
                "  #{} {} - {} | limite {} | {} dia(s) de atraso".format(
                    registro["id"],
                    registro["cliente"],
                    registro["titulo"],
                    formatar_data(registro["data_limite"]),
                    abs(int(registro["dias_restantes"])),
                )
            )
    else:
        print("  (nenhum)")
    print()
    return 0


def cmd_export(conexao, args) -> int:
    registros = processor.enriquecer_todos(
        database.listar(
            conexao,
            status=args.status,
            prioridade=args.prioridade,
            categoria=args.categoria,
        )
    )
    if not registros:
        print("Nenhum registro encontrado para exportar.")
        return 1

    try:
        arquivos = exporter.exportar(registros, formato=args.formato, pasta=args.pasta)
    except (ValueError, OSError) as erro:
        print(f"Erro ao exportar: {erro}")
        return 1

    print(f"{len(registros)} registro(s) exportado(s):")
    for arquivo in arquivos:
        print(f"  - {arquivo}")
    return 0


# Dados ficticios realistas para demonstracao em entrevistas/testes de cliente
DADOS_SEED = [
    {
        "cliente": "Clinica VidaBem",
        "titulo": "Integracao da agenda com WhatsApp",
        "categoria": "Integracao",
        "valor": 6200,
        "prazo": 5,
        "dias_atras": 12,
        "status": "ABERTO",
        "obs": "Recepcionista confirma consultas manualmente todos os dias.",
    },
    {
        "cliente": "Transportes Rota Sul",
        "titulo": "Bot de triagem de chamados",
        "categoria": "Suporte",
        "valor": 7800,
        "prazo": 3,
        "dias_atras": 10,
        "status": "ABERTO",
        "obs": "Chamados urgentes se perdem no e-mail compartilhado.",
    },
    {
        "cliente": "Distribuidora Norte",
        "titulo": "Alerta automatico de estoque critico",
        "categoria": "Integracao",
        "valor": 8800,
        "prazo": 4,
        "dias_atras": 14,
        "status": "ABERTO",
        "obs": "Ruptura de estoque gerou perda de vendas no mes passado.",
    },
    {
        "cliente": "Padaria Pao Dourado",
        "titulo": "Automacao do controle de estoque",
        "categoria": "Automacao",
        "valor": 3500,
        "prazo": 10,
        "dias_atras": 8,
        "status": "EM_ANDAMENTO",
        "obs": "Planilha atual tem tres abas duplicadas.",
    },
    {
        "cliente": "Colegio Saber",
        "titulo": "Automacao de boletos e recibos",
        "categoria": "Automacao",
        "valor": 4700,
        "prazo": 6,
        "dias_atras": 7,
        "status": "ABERTO",
        "obs": "Secretaria emite recibos um por um.",
    },
    {
        "cliente": "Escritorio Contabil Alfa",
        "titulo": "Limpeza e cruzamento de planilhas",
        "categoria": "Dados",
        "valor": 2400,
        "prazo": 7,
        "dias_atras": 6,
        "status": "EM_ANDAMENTO",
        "obs": "Conferencia mensal leva dois dias inteiros.",
    },
    {
        "cliente": "Pet Shop Amigo Fiel",
        "titulo": "Cadastro unico de clientes e pets",
        "categoria": "Dados",
        "valor": 3100,
        "prazo": 9,
        "dias_atras": 5,
        "status": "EM_ANDAMENTO",
        "obs": "Mesmo cliente aparece com nomes diferentes em duas bases.",
    },
    {
        "cliente": "Academia Forca Max",
        "titulo": "Dashboard de inadimplencia",
        "categoria": "Relatorios",
        "valor": 4300,
        "prazo": 12,
        "dias_atras": 4,
        "status": "ABERTO",
        "obs": "Cobranca feita sem visao consolidada dos vencidos.",
    },
    {
        "cliente": "Advocacia Silva & Reis",
        "titulo": "Triagem de prazos processuais",
        "categoria": "Suporte",
        "valor": 6900,
        "prazo": 2,
        "dias_atras": 3,
        "status": "EM_ANDAMENTO",
        "obs": "Prazos controlados em agenda de papel.",
    },
    {
        "cliente": "Mercado Bom Preco",
        "titulo": "Conferencia automatica de notas",
        "categoria": "Automacao",
        "valor": 5600,
        "prazo": 2,
        "dias_atras": 20,
        "status": "CONCLUIDO",
        "obs": "Entrega validada; economia de 12 horas por semana.",
    },
    {
        "cliente": "Restaurante Sabor Caseiro",
        "titulo": "Controle de pedidos e entregas",
        "categoria": "Sistema",
        "valor": 5200,
        "prazo": 18,
        "dias_atras": 40,
        "status": "CONCLUIDO",
        "obs": "Pedidos deixaram de ser anotados em papel.",
    },
    {
        "cliente": "Loja Verde Casa",
        "titulo": "Relatorio mensal de vendas em CSV",
        "categoria": "Relatorios",
        "valor": 1800,
        "prazo": 15,
        "dias_atras": 30,
        "status": "CONCLUIDO",
        "obs": "Relatorio agora e gerado em um comando.",
    },
    {
        "cliente": "Studio Foto Luz",
        "titulo": "Exportacao de orcamentos em lote",
        "categoria": "Relatorios",
        "valor": 900,
        "prazo": 10,
        "dias_atras": 25,
        "status": "CONCLUIDO",
        "obs": "Orcamentos eram copiados manualmente um a um.",
    },
    {
        "cliente": "Oficina Carro Novo",
        "titulo": "Lembretes automaticos de revisao",
        "categoria": "Automacao",
        "valor": 2200,
        "prazo": 20,
        "dias_atras": 2,
        "status": "ABERTO",
        "obs": "Clientes esquecem a revisao e a oficina perde receita.",
    },
]


def cmd_seed(conexao, args) -> int:
    existentes = database.total(conexao)
    if existentes and not args.reset:
        print(
            f"O banco ja possui {existentes} registro(s). "
            "Use 'seed --reset' para recriar a demonstracao."
        )
        return 1

    if existentes:
        database.limpar(conexao)
        print(f"Banco limpo ({existentes} registro(s) removido(s)).")

    hoje = date.today()
    criados = 0
    for item in DADOS_SEED:
        criado_em = datetime.combine(
            hoje - timedelta(days=item["dias_atras"]), datetime.min.time()
        )
        prioridade = processor.calcular_prioridade(
            item["valor"], item["prazo"], item["categoria"]
        )
        database.inserir(
            conexao,
            cliente=item["cliente"],
            titulo=item["titulo"],
            categoria=item["categoria"],
            valor=item["valor"],
            prazo_dias=item["prazo"],
            prioridade=prioridade,
            status=item.get("status", "ABERTO"),
            observacao=item.get("obs", ""),
            criado_em=criado_em.isoformat(timespec="seconds"),
        )
        criados += 1

    print(f"{criados} registro(s) de demonstracao inserido(s) em smartops.db.")
    print("Agora rode: python main.py report")
    return 0


# ---------------------------------------------------------------------------
# Parser da CLI
# ---------------------------------------------------------------------------
def _adicionar_filtros(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--status", choices=database.STATUS_VALIDOS, help="Filtra por status.")
    parser.add_argument(
        "--prioridade", choices=database.PRIORIDADES_VALIDAS, help="Filtra por prioridade."
    )
    parser.add_argument("--categoria", help="Filtra por categoria (busca parcial).")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smartops",
        description="SmartOps CLI - triagem, registro e relatorios operacionais.",
    )
    subparsers = parser.add_subparsers(dest="comando", metavar="comando")

    p_add = subparsers.add_parser("add", help="Adiciona um registro e calcula a prioridade.")
    p_add.add_argument("--cliente", required=True, help="Cliente ou area responsavel.")
    p_add.add_argument("--titulo", required=True, help="Titulo curto da demanda.")
    p_add.add_argument(
        "--categoria", required=True, help="Ex.: Automacao, Suporte, Relatorios, Dados."
    )
    p_add.add_argument("--valor", type=float, default=0.0, help="Valor estimado em reais.")
    p_add.add_argument("--prazo", type=int, default=7, help="Prazo em dias.")
    p_add.add_argument("--obs", default="", help="Observacao livre.")
    p_add.set_defaults(func=cmd_add)

    p_list = subparsers.add_parser("list", help="Lista registros com filtros opcionais.")
    _adicionar_filtros(p_list)
    p_list.set_defaults(func=cmd_list)

    p_update = subparsers.add_parser(
        "update", help="Atualiza status e/ou observacao de um registro pelo ID."
    )
    p_update.add_argument("id", type=int, help="ID do registro.")
    p_update.add_argument("--status", choices=database.STATUS_VALIDOS, help="Novo status.")
    p_update.add_argument("--obs", default=None, help="Nova observacao.")
    p_update.set_defaults(func=cmd_update)

    p_report = subparsers.add_parser("report", help="Mostra o resumo executivo no terminal.")
    p_report.set_defaults(func=cmd_report)

    p_export = subparsers.add_parser("export", help="Exporta registros para CSV e/ou JSON.")
    p_export.add_argument(
        "--formato", choices=("csv", "json", "ambos"), default="ambos", help="Formato de saida."
    )
    p_export.add_argument(
        "--pasta", default=None, help="Pasta de destino (padrao: exports/ do projeto)."
    )
    _adicionar_filtros(p_export)
    p_export.set_defaults(func=cmd_export)

    p_seed = subparsers.add_parser("seed", help="Popula o banco com dados ficticios.")
    p_seed.add_argument(
        "--reset", action="store_true", help="Apaga os registros atuais antes de inserir."
    )
    p_seed.set_defaults(func=cmd_seed)

    return parser


def main(argv=None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "comando", None):
        parser.print_help()
        return 0

    conexao = database.conectar()
    database.inicializar(conexao)
    try:
        return args.func(conexao, args)
    finally:
        conexao.close()


if __name__ == "__main__":
    sys.exit(main())
