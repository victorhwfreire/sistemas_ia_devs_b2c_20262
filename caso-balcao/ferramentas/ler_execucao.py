"""Lê o registro de uma execução do Claude Code e mostra os passos, o custo e o tempo.

Gere o registro com:
  claude -p "..." --output-format stream-json --verbose > execucao.jsonl
Depois:
  python ler_execucao.py execucao.jsonl
  python ler_execucao.py execucao.jsonl --json      # uma linha de resumo, para comparar execuções
"""
import argparse
import json
import sys


def ler(caminho):
    """Aceita UTF-8 e também o UTF-16 que o '>' do Windows PowerShell 5 grava."""
    bruto = sys.stdin.buffer.read() if caminho == "-" else open(caminho, "rb").read()
    if bruto[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return bruto.decode("utf-16")
    return bruto.decode("utf-8-sig", "replace")


def eventos(caminho):
    for linha in ler(caminho).splitlines():
        linha = linha.strip()
        if linha.startswith("{"):
            try:
                yield json.loads(linha)
            except json.JSONDecodeError:
                pass


def texto_de(conteudo):
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return " ".join(b.get("text", "") for b in conteudo if isinstance(b, dict))
    return json.dumps(conteudo, ensure_ascii=False)


def resumir(evs):
    r = {"modelo": None, "passos": [], "final": {}}
    for ev in evs:
        tipo = ev.get("type")
        if tipo == "system" and ev.get("subtype") == "init":
            r["modelo"] = ev.get("model")
            r["ferramentas_disponiveis"] = len(ev.get("tools", []))
        elif tipo in ("assistant", "user"):
            for bloco in (ev.get("message") or {}).get("content") or []:
                if not isinstance(bloco, dict):
                    continue
                if bloco.get("type") == "tool_use":
                    r["passos"].append({"ferramenta": bloco.get("name"), "entrada": bloco.get("input"), "id": bloco.get("id")})
                elif bloco.get("type") == "tool_result":
                    passo = next((p for p in reversed(r["passos"]) if p.get("id") == bloco.get("tool_use_id")), None)
                    if passo is not None:
                        passo["erro"] = bool(bloco.get("is_error"))
                        passo["retorno"] = texto_de(bloco.get("content"))
                elif bloco.get("type") == "text" and tipo == "assistant" and bloco.get("text", "").strip():
                    r["passos"].append({"texto": bloco["text"].strip()})
        elif tipo == "result":
            r["final"] = ev
    return r


def resumo_curto(r):
    f, u = r["final"], r["final"].get("usage") or {}
    chamadas = [p for p in r["passos"] if "ferramenta" in p]
    return {"modelo": r["modelo"], "subtype": f.get("subtype"), "voltas": f.get("num_turns"),
            "ferramentas": [p["ferramenta"] for p in chamadas], "erros_de_ferramenta": sum(p.get("erro", False) for p in chamadas),
            "ms": f.get("duration_ms"), "ms_api": f.get("duration_api_ms"), "custo_usd": f.get("total_cost_usd"),
            "tokens_entrada": u.get("input_tokens"), "tokens_saida": u.get("output_tokens"),
            "cache_lido": u.get("cache_read_input_tokens"), "cache_criado": u.get("cache_creation_input_tokens")}


def corta(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    ap = argparse.ArgumentParser(description="Resumo de uma execução do Claude Code")
    ap.add_argument("arquivo", help="registro em stream-json; use - para ler da entrada padrão")
    ap.add_argument("--json", action="store_true", help="imprime só o resumo, em uma linha JSON")
    a = ap.parse_args()
    r = resumir(eventos(a.arquivo))
    curto = resumo_curto(r)
    if a.json:
        print(json.dumps(curto, ensure_ascii=False))
        return
    print(f"Modelo: {r['modelo']}")
    n = 0
    for p in r["passos"]:
        if "ferramenta" in p:
            n += 1
            print(f"\nPasso {n} · o modelo pede {p['ferramenta']} {corta(json.dumps(p['entrada'], ensure_ascii=False), 140)}")
            if "retorno" in p:
                print(f"         {'ERRO' if p.get('erro') else 'volta'}: {corta(p['retorno'], 160)}")
        else:
            print(f"\n  texto do modelo: {corta(p['texto'], 200)}")
    f = r["final"]
    print("\n--------")
    print(f"Fim: {curto['subtype']} · voltas: {curto['voltas']} · chamadas de ferramenta: {len(curto['ferramentas'])} · com erro: {curto['erros_de_ferramenta']}")
    if curto["ms"] is not None:
        print(f"Tempo total: {curto['ms'] / 1000:.1f}s · tempo esperando a API: {(curto['ms_api'] or 0) / 1000:.1f}s")
    print(f"Tokens: entrada {curto['tokens_entrada']} · saída {curto['tokens_saida']} · cache lido {curto['cache_lido']} · cache criado {curto['cache_criado']}")
    if curto["custo_usd"] is not None:
        print(f"Custo estimado: US$ {curto['custo_usd']:.4f}")
    if f.get("result"):
        print(f"\nResposta final: {corta(f['result'], 400)}")


if __name__ == "__main__":
    main()
