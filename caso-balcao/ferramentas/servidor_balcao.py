"""Servidor MCP do caso Balcão, usado em M3 (aulas 2 e 3) e M4 (aula 3).

Dois contratos para a mesma consulta:
  --contrato fraco   uma ferramenta espelhada da API interna: nome e descrição vagos, erro opaco
  --contrato forte   ferramentas pensadas para o agente: descrição, formato, exemplo, erro que ensina

O estorno é simulado: nada sai do arquivo estado/estornos.jsonl.
Toda chamada é registrada em estado/chamadas.jsonl.

Uso:
  python servidor_balcao.py --contrato forte            # stdio, para o Claude Code
  python servidor_balcao.py --contrato forte --http     # HTTP em 127.0.0.1:8765, sem autenticação
"""
import argparse
import inspect
import json
import re
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "estado"
CLIENTES = json.loads((RAIZ / "dados/clientes.json").read_text(encoding="utf-8"))["clientes"]
COBRANCAS = json.loads((RAIZ / "dados/cobrancas.json").read_text(encoding="utf-8"))["cobrancas"]

mcp = FastMCP("balcao")


def brl(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gravar(arquivo, registro):
    ESTADO.mkdir(exist_ok=True)
    with (ESTADO / arquivo).open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def registrada(fn):
    """Registra cada chamada (argumentos, resultado ou erro, duração) antes de devolver ao modelo."""
    assinatura = inspect.signature(fn)

    @wraps(fn)
    def envolvida(*args, **kwargs):
        inicio = time.perf_counter()
        argumentos = dict(assinatura.bind_partial(*args, **kwargs).arguments)
        registro = {"quando": datetime.now().isoformat(timespec="seconds"), "ferramenta": fn.__name__, "argumentos": argumentos}
        try:
            resultado = fn(*args, **kwargs)
            registro.update(ok=True, resultado=resultado)
            return resultado
        except Exception as erro:
            registro.update(ok=False, erro=str(erro))
            raise
        finally:
            registro["ms"] = round((time.perf_counter() - inicio) * 1000, 1)
            gravar("chamadas.jsonl", registro)
    return envolvida


def cliente_por_id(cliente_id):
    return next((c for c in CLIENTES if c["id"] == cliente_id), None)


# ------------------------------------------------------------------ contrato fraco

@registrada
def get_data(cliente: str, periodo: str) -> list:
    if not re.fullmatch(r"CLI-\d{3}", cliente) or not re.fullmatch(r"\d{4}-\d{2}", periodo):
        raise ValueError("invalid input")
    return [c for c in COBRANCAS if c["cliente_id"] == cliente and c["data"].startswith(periodo)]


# ------------------------------------------------------------------ contrato forte

@registrada
def buscar_cliente(
    nome: Annotated[str, Field(description="Nome do comércio como o cliente escreveu, ex.: 'Estúdio Pilates Vida'. Aceita parte do nome.")],
) -> dict:
    achados = [c for c in CLIENTES if nome.strip().lower() in c["nome"].lower()]
    if not achados:
        raise ValueError(f"Nenhum cliente com nome parecido com '{nome}'. Confira a grafia ou use um trecho menor do nome.")
    if len(achados) > 1:
        raise ValueError(f"'{nome}' bate com {len(achados)} clientes: {', '.join(c['nome'] for c in achados)}. Use um trecho que identifique um só.")
    c = achados[0]
    return {"cliente_id": c["id"], "nome": c["nome"], "plano": c["plano"], "mensalidade": c["mensalidade"]}


@registrada
def consultar_cobrancas(
    cliente_id: Annotated[str, Field(description="Id do cliente no formato CLI-123, ex.: 'CLI-102'. Se você só tem o nome, chame buscar_cliente antes.")],
    mes: Annotated[str, Field(description="Mês no formato AAAA-MM, ex.: '2026-10' para outubro de 2026.")],
) -> dict:
    if not re.fullmatch(r"CLI-\d{3}", cliente_id):
        raise ValueError(f"cliente_id deve ter o formato CLI-123. Recebido: '{cliente_id}'. Se você tem o nome do comércio, chame buscar_cliente para obter o id.")
    if not re.fullmatch(r"\d{4}-\d{2}", mes):
        raise ValueError(f"mes deve ter o formato AAAA-MM, por exemplo '2026-10'. Recebido: '{mes}'. Reenvie com o formato correto.")
    if not cliente_por_id(cliente_id):
        raise ValueError(f"Não existe cliente {cliente_id}. Confira o id com buscar_cliente.")
    itens = [{k: c[k] for k in ("id", "data", "tipo", "valor", "status") if k in c} | ({"contrato_antecipacao": c["contrato_antecipacao"]} if "contrato_antecipacao" in c else {})
             for c in COBRANCAS if c["cliente_id"] == cliente_id and c["data"].startswith(mes)]
    return {"cliente_id": cliente_id, "mes": mes, "cobrancas": itens, "total": round(sum(i["valor"] for i in itens), 2)}


@registrada
def registrar_nota(
    ticket_id: Annotated[str, Field(description="Id do ticket, ex.: 'TCK-002'.")],
    texto: Annotated[str, Field(description="O que foi verificado e decidido, em uma ou duas frases.")],
) -> str:
    gravar("notas.jsonl", {"quando": datetime.now().isoformat(timespec="seconds"), "ticket_id": ticket_id, "texto": texto})
    return f"Nota registrada no {ticket_id}. Cada chamada cria uma nota nova: não repita se esta deu certo."


@registrada
def emitir_estorno(
    cobranca_id: Annotated[str, Field(description="Id do lançamento a estornar, ex.: 'COB-5003'. Obtenha com consultar_cobrancas.")],
    valor: Annotated[float, Field(description="Valor do estorno em reais, ex.: 189.90.")],
    motivo: Annotated[str, Field(description="Motivo em uma frase, ex.: 'mensalidade cobrada em duplicidade'.")],
) -> str:
    cobranca = next((c for c in COBRANCAS if c["id"] == cobranca_id), None)
    if cobranca is None:
        raise ValueError(f"Não existe o lançamento {cobranca_id}. Use consultar_cobrancas para ver os ids do cliente.")
    if valor <= 0:
        raise ValueError(f"valor deve ser maior que zero. Recebido: {valor}.")
    gravar("estornos.jsonl", {"quando": datetime.now().isoformat(timespec="seconds"), "cobranca_id": cobranca_id,
                              "cliente_id": cobranca["cliente_id"], "valor": valor, "motivo": motivo, "simulado": True})
    return f"Estorno SIMULADO de {brl(valor)} no lançamento {cobranca_id} ({cobranca['cliente_id']}). Nenhum dinheiro foi movimentado."


LEITURA = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def registrar_ferramentas(contrato):
    if contrato == "fraco":
        mcp.tool(name="get_data", description="Consulta dados.", annotations=LEITURA)(get_data)
        return
    mcp.tool(description="Encontra o id de um cliente do Balcão a partir do nome do comércio. Use quando o ticket traz só o nome.",
             annotations=LEITURA)(buscar_cliente)
    mcp.tool(description="Lista os lançamentos que o Balcão cobrou de um cliente num mês: mensalidades e tarifas, com id, data, tipo, valor e status. "
                         "Use para conferir cobrança duplicada ou tarifa contestada.", annotations=LEITURA)(consultar_cobrancas)
    mcp.tool(description="Registra uma nota no ticket. Mutante e não idempotente: cada chamada cria uma nota nova.",
             annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))(registrar_nota)
    mcp.tool(description="Emite o estorno de um lançamento. Destrutiva: dinheiro que sai não volta. Nesta demonstração o estorno é simulado.",
             annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False))(emitir_estorno)


def main():
    ap = argparse.ArgumentParser(description="Servidor MCP do caso Balcão")
    ap.add_argument("--contrato", choices=["fraco", "forte"], default="forte")
    ap.add_argument("--http", action="store_true", help="expõe por HTTP em 127.0.0.1:8765, sem autenticação")
    args = ap.parse_args()
    registrar_ferramentas(args.contrato)
    if args.http:
        print("Balcão MCP por HTTP em http://127.0.0.1:8765/mcp, SEM autenticação: só para demonstração local.", file=sys.stderr)
        mcp.settings.host, mcp.settings.port = "127.0.0.1", 8765
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
