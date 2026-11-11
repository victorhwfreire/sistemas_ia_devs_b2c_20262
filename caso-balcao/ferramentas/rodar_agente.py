"""Roda o agente de suporte do Balcão (Claude Code em modo -p) num ticket e grava o registro da execução.

Modos:
  --modo arquivos                    o agente lê dados/ com Read, Glob e Grep (M3, aula 1)
  --modo mcp --contrato fraco|forte  o agente só tem as ferramentas do servidor MCP do Balcão (M3, aulas 2 e 3; M4)
  --limites com                      liga o hook guarda.py e deixa o estorno sob a política (M3, aula 3; M4, aula 3)

O pedido vai pela entrada padrão; o registro (stream-json) vai para o arquivo de --saida e é resumido no fim.
No modo mcp, a configuração usada fica em estado/config/ (mcp.json e settings.json) e o agente roda numa pasta vazia,
para não ler os dados direto do disco. Nada sai do computador além da chamada ao modelo: o estorno do servidor é simulado.

Exemplos:
  python rodar_agente.py --ticket TCK-002 --modo arquivos --saida a1-ato2.jsonl
  python rodar_agente.py --ticket TCK-002 --modo mcp --contrato fraco --saida a2-ato1.jsonl
  python rodar_agente.py --ticket TCK-012 --modo mcp --limites com --saida a3-ato2.jsonl
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from claude_cli import executavel
from ler_execucao import eventos, resumir, resumo_curto

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
TICKETS = {t["id"]: t for t in json.loads((RAIZ / "tickets.json").read_text(encoding="utf-8"))["tickets"]}

PEDIDO_ARQUIVOS = (
    "Você é o agente de suporte do Balcão. Resolva o ticket abaixo. Os dados do Balcão estão nesta pasta: "
    "clientes.json, cobrancas.json e politica-atendimento.md. Investigue o que for preciso e termine com: "
    "(1) categoria e prioridade, (2) o que você verificou, (3) a resposta ao cliente, (4) a recomendação ao time. "
    "Não altere nenhum arquivo.\n\nTicket {id} · {cliente}: {texto}"
)
PEDIDO_MCP = (
    "Você é o agente de suporte do Balcão. Resolva o ticket abaixo usando as ferramentas do Balcão. "
    "Estorno só para cobrança duplicada comprovada nos lançamentos, no valor do lançamento. "
    "Termine com o que você verificou, o que fez e a resposta ao cliente.\n\nTicket {id} · {cliente}: {texto}"
)
LEITURA = ["Read", "Glob", "Grep"]
LOCAIS = ["Read", "Glob", "Grep", "Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]


def configurar(contrato, limites):
    """Grava em estado/config/ o mcp.json e o settings.json desta execução, para mostrar e reaproveitar."""
    pasta = RAIZ / "estado" / "config"
    pasta.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    mcp = {"mcpServers": {"balcao": {"command": py, "args": [str(AQUI / "servidor_balcao.py"), "--contrato", contrato]}}}
    (pasta / "mcp.json").write_text(json.dumps(mcp, indent=2), encoding="utf-8")
    settings = {"permissions": {"allow": ["mcp__balcao__*"]}}
    if limites == "com":
        settings["hooks"] = {"PreToolUse": [{"matcher": "mcp__balcao__.*",
                                             "hooks": [{"type": "command", "command": f'"{py}" "{AQUI / "guarda.py"}"'}]}]}
    (pasta / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return ["--mcp-config", str(pasta / "mcp.json"), "--strict-mcp-config", "--settings", str(pasta / "settings.json"),
            "--disallowedTools", *LOCAIS]


def main():
    ap = argparse.ArgumentParser(description="Agente de suporte do Balcão")
    ap.add_argument("--ticket", default="TCK-002")
    ap.add_argument("--pedido", help="texto livre no lugar do pedido padrão")
    ap.add_argument("--modo", choices=["arquivos", "mcp"], default="arquivos")
    ap.add_argument("--contrato", choices=["fraco", "forte"], default="forte")
    ap.add_argument("--limites", choices=["sem", "com"], default="sem")
    ap.add_argument("--orcamento", type=float, default=0.50, help="teto de gasto da execução, em dólares (--max-budget-usd)")
    ap.add_argument("--modelo", help="ex.: sonnet, haiku, opus")
    ap.add_argument("--saida", default="execucao.jsonl")
    a = ap.parse_args()
    t = TICKETS[a.ticket]
    modelo_pedido = PEDIDO_ARQUIVOS if a.modo == "arquivos" else PEDIDO_MCP
    pedido = a.pedido or modelo_pedido.format(**t)
    cmd = [executavel(), "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk",
           "--max-budget-usd", str(a.orcamento), "--no-session-persistence"]
    if a.modelo:
        cmd += ["--model", a.modelo]
    with tempfile.TemporaryDirectory() as tmp:
        if a.modo == "arquivos":
            pasta = RAIZ / "dados"
            cmd += ["--allowedTools", *LEITURA]
        else:
            pasta = Path(tmp)
            cmd += configurar(a.contrato, a.limites)
        print(f"Pedido enviado:\n{pedido}\n\nRodando o agente ({a.modo}{', contrato ' + a.contrato if a.modo == 'mcp' else ''}"
              f"{', limites ' + a.limites if a.modo == 'mcp' else ''}, teto US$ {a.orcamento:.2f})...\n", flush=True)
        proc = subprocess.run(cmd, input=pedido.encode("utf-8"), capture_output=True, cwd=pasta)
    Path(a.saida).write_bytes(proc.stdout)
    if proc.returncode and not proc.stdout:
        print(proc.stderr.decode("utf-8", "replace")[:800])
        return proc.returncode
    subprocess.run([sys.executable, str(AQUI / "ler_execucao.py"), a.saida])
    print(f"\nRegistro completo em {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
