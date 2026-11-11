"""Hook PreToolUse do Claude Code para as ferramentas do Balcão.

Registra toda chamada em estado/auditoria.jsonl e aplica a política de estorno fora do modelo:
o lançamento precisa existir, o valor é o do lançamento e, acima de R$ 200,00, só com aprovação humana.
Sem violação, o hook não decide nada e o fluxo normal de permissões segue.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LIMITE = 200.00
COBRANCAS = {c["id"]: c for c in json.loads((RAIZ / "dados/cobrancas.json").read_text(encoding="utf-8"))["cobrancas"]}


def brl(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def motivo_para_negar(ferramenta, args):
    if not ferramenta.endswith("__emitir_estorno"):
        return None
    cobranca = COBRANCAS.get(args.get("cobranca_id"))
    if cobranca is None:
        return f"Lançamento {args.get('cobranca_id')} não existe. Consulte as cobranças do cliente antes."
    valor = float(args.get("valor") or 0)
    if abs(valor - cobranca["valor"]) > 0.005:
        return f"Política: o estorno é do valor do lançamento ({brl(cobranca['valor'])}), não {brl(valor)}."
    if valor > LIMITE:
        return f"Política: estorno acima de {brl(LIMITE)} exige aprovação do financeiro. Registre uma nota e encaminhe."
    return None


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    evento = json.loads(sys.stdin.read() or "{}")
    ferramenta, args = evento.get("tool_name", ""), evento.get("tool_input") or {}
    motivo = motivo_para_negar(ferramenta, args)
    (RAIZ / "estado").mkdir(exist_ok=True)
    with (RAIZ / "estado/auditoria.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"quando": datetime.now().isoformat(timespec="seconds"), "sessao": evento.get("session_id"),
                            "ferramenta": ferramenta, "argumentos": args, "decisao": "negada" if motivo else "segue", "motivo": motivo},
                           ensure_ascii=False) + "\n")
    if motivo:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": motivo}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
