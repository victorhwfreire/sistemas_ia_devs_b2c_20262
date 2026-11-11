"""Workflow de triagem do Balcão: três passos fixos, e quem decide o caminho é o código.

  1. classificar   uma chamada ao modelo, com saída estruturada (categoria e prioridade)
  2. rotear        código puro: a categoria escolhe o time, sem modelo
  3. responder     uma chamada ao modelo, que redige a primeira resposta ao cliente

Uso:
  python workflow_triagem.py TCK-001 TCK-002
  python workflow_triagem.py --todos --sem-resposta --saida lote.jsonl
"""
import argparse
import json
from pathlib import Path

from claude_cli import chamar, percentil

RAIZ = Path(__file__).resolve().parent.parent
TICKETS = json.loads((RAIZ / "tickets.json").read_text(encoding="utf-8"))
POLITICA = (RAIZ / "dados/politica-atendimento.md").read_text(encoding="utf-8")
ROTA = {"falha_transacao": "pagamentos", "cobranca_indevida": "financeiro", "integracao_api": "plataforma",
        "acesso_conta": "seguranca", "duvida_produto": "atendimento"}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["categoria", "prioridade"],
          "properties": {"categoria": {"type": "string", "enum": TICKETS["categorias"]},
                         "prioridade": {"type": "string", "enum": ["P1", "P2", "P3"]}}}
SISTEMA_CLASSIFICAR = ("Você classifica tickets de suporte do Balcão, uma plataforma de pagamentos para pequenos comércios. "
                       "Use só a política abaixo. Responda apenas com a categoria e a prioridade.\n\n" + POLITICA)
SISTEMA_RESPONDER = ("Você escreve a primeira resposta do suporte do Balcão a um cliente. Três frases, tom cordial, em português. "
                     "Diga o que vai ser verificado e por qual time. Não prometa estorno nem prazo.")


def triar(ticket, modelo=None, responder=True):
    passos = []
    c = chamar(ticket["texto"], sistema=SISTEMA_CLASSIFICAR, schema=SCHEMA, modelo=modelo)
    saida = c.get("structured_output") or {}
    passos.append({"passo": "classificar", "ms": c.get("duration_ms", c["relogio_ms"]), "custo": c.get("total_cost_usd", 0), "erro": c.get("is_error", False)})
    time_destino = ROTA.get(saida.get("categoria"), "atendimento")
    passos.append({"passo": "rotear", "ms": 0, "custo": 0, "erro": False})
    resposta = ""
    if responder:
        r = chamar(f"Ticket de {ticket['cliente']}: {ticket['texto']}\nTime responsável: {time_destino}.", sistema=SISTEMA_RESPONDER, modelo=modelo)
        resposta = r.get("result", "")
        passos.append({"passo": "responder", "ms": r.get("duration_ms", r["relogio_ms"]), "custo": r.get("total_cost_usd", 0), "erro": r.get("is_error", False)})
    g = ticket["gabarito"]
    return {"ticket": ticket["id"], "categoria": saida.get("categoria"), "prioridade": saida.get("prioridade"), "time": time_destino,
            "acertou": saida.get("categoria") == g["categoria"] and saida.get("prioridade") == g["prioridade"],
            "chamadas_ao_modelo": sum(p["passo"] != "rotear" for p in passos),
            "ms": sum(p["ms"] for p in passos), "custo": round(sum(p["custo"] for p in passos), 5), "passos": passos, "resposta": resposta}


def main():
    ap = argparse.ArgumentParser(description="Workflow de triagem do Balcão")
    ap.add_argument("tickets", nargs="*", help="ids, ex.: TCK-001 TCK-002")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--sem-resposta", action="store_true", help="pula o passo 3")
    ap.add_argument("--modelo", help="ex.: sonnet, haiku, opus")
    ap.add_argument("--saida", help="grava um JSON por ticket neste arquivo")
    a = ap.parse_args()
    escolhidos = [t for t in TICKETS["tickets"] if a.todos or t["id"] in a.tickets]
    resultados = []
    print(f"{'ticket':8} {'categoria':18} {'prior.':6} {'time':12} {'gabarito':8} {'chamadas':>8} {'tempo':>8} {'custo US$':>10}")
    for t in escolhidos:
        r = triar(t, a.modelo, not a.sem_resposta)
        resultados.append(r)
        print(f"{r['ticket']:8} {str(r['categoria']):18} {str(r['prioridade']):6} {r['time']:12} {'confere' if r['acertou'] else 'difere':8} "
              f"{r['chamadas_ao_modelo']:>8} {r['ms'] / 1000:>7.1f}s {r['custo']:>10.4f}")
        if r["resposta"]:
            print(f"         resposta: {r['resposta'][:220]}")
    if a.saida:
        Path(a.saida).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in resultados), encoding="utf-8")
    if resultados:
        tempos = [r["ms"] / 1000 for r in resultados]
        acertos = sum(r["acertou"] for r in resultados)
        custo = sum(r["custo"] for r in resultados)
        print(f"\n{len(resultados)} tickets · {acertos} conferem com o gabarito · tempo p50 {percentil(tempos, 50):.1f}s, p95 {percentil(tempos, 95):.1f}s"
              f" · custo total US$ {custo:.4f} · custo por acerto US$ {custo / acertos if acertos else float('nan'):.4f}")


if __name__ == "__main__":
    main()
