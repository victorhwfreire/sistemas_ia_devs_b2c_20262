"""Eval da triagem do Balcão: o mesmo classificador em todos os tickets, comparado com o gabarito.

Mostra o acerto por ticket e por campo, a variação entre repetições (pass@k e pass^k), o tempo e o custo.

Uso:
  python eval_triagem.py --prompt ../prompts/a.txt
  python eval_triagem.py --prompt ../prompts/b.txt --repeticoes 2 --saida b.csv
  python eval_triagem.py --prompt ../prompts/b.txt --casos meus-casos.json
"""
import argparse
import csv
import json
from pathlib import Path

from claude_cli import chamar, percentil
from workflow_triagem import SCHEMA, TICKETS

LARGURA = 34


def main():
    ap = argparse.ArgumentParser(description="Eval da triagem do Balcão")
    ap.add_argument("--prompt", required=True, help="arquivo com a instrução do classificador")
    ap.add_argument("--repeticoes", type=int, default=1)
    ap.add_argument("--tickets", nargs="*", help="ids; padrão: todos")
    ap.add_argument("--casos", help="outro arquivo de casos no formato de tickets.json; padrão: o tickets.json do caso")
    ap.add_argument("--modelo", help="ex.: sonnet, haiku, opus")
    ap.add_argument("--saida", help="CSV com uma linha por execução")
    a = ap.parse_args()
    sistema = Path(a.prompt).read_text(encoding="utf-8")
    base = json.loads(Path(a.casos).read_text(encoding="utf-8")) if a.casos else TICKETS
    casos = [t for t in base["tickets"] if not a.tickets or t["id"] in a.tickets]
    linhas, tempos, custo = [], [], 0.0
    print(f"Prompt: {a.prompt} · {len(casos)} tickets · {a.repeticoes} repetição(ões)\n")
    print(f"{'ticket':8} {'gabarito':22} " + " ".join(f"{'execução ' + str(k + 1):{LARGURA}}" for k in range(a.repeticoes)))
    for t in casos:
        g = t["gabarito"]
        celulas = []
        for k in range(a.repeticoes):
            r = chamar(t["texto"], sistema=sistema, schema=SCHEMA, modelo=a.modelo)
            s = r.get("structured_output") or {}
            ok_cat, ok_pri = s.get("categoria") == g["categoria"], s.get("prioridade") == g["prioridade"]
            tempos.append(r.get("duration_ms", r["relogio_ms"]) / 1000)
            custo += r.get("total_cost_usd", 0) or 0
            linhas.append({"ticket": t["id"], "repeticao": k + 1, "categoria": s.get("categoria"), "prioridade": s.get("prioridade"),
                           "gab_categoria": g["categoria"], "gab_prioridade": g["prioridade"], "acerto_categoria": ok_cat,
                           "acerto_prioridade": ok_pri, "acerto": ok_cat and ok_pri, "segundos": tempos[-1], "custo_usd": r.get("total_cost_usd")})
            marca = "ok" if ok_cat and ok_pri else ("categoria" if not ok_cat else "prioridade") + " difere"
            celulas.append(f"{str(s.get('categoria'))[:17]}/{s.get('prioridade')} {marca}")
        print(f"{t['id']:8} {g['categoria'][:17] + '/' + g['prioridade']:22} " + " ".join(f"{c:{LARGURA}}" for c in celulas))
    n = len(linhas)
    por_ticket = {}
    for l in linhas:
        por_ticket.setdefault(l["ticket"], []).append(l["acerto"])
    acertos = sum(l["acerto"] for l in linhas)
    print(f"\nAcerto da categoria: {sum(l['acerto_categoria'] for l in linhas)}/{n} · da prioridade: {sum(l['acerto_prioridade'] for l in linhas)}/{n}"
          f" · dos dois: {acertos}/{n}")
    if a.repeticoes > 1:
        k = a.repeticoes
        print(f"pass@{k} (acertou em pelo menos uma): {sum(any(v) for v in por_ticket.values())}/{len(por_ticket)} tickets"
              f" · pass^{k} (acertou em todas): {sum(all(v) for v in por_ticket.values())}/{len(por_ticket)} tickets")
    print(f"Tempo por chamada: p50 {percentil(tempos, 50):.1f}s · p95 {percentil(tempos, 95):.1f}s · custo total US$ {custo:.4f}"
          f" · custo por acerto US$ {custo / acertos if acertos else float('nan'):.4f}")
    if a.saida:
        with open(a.saida, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)
        print(f"Execuções gravadas em {a.saida}")


if __name__ == "__main__":
    main()
