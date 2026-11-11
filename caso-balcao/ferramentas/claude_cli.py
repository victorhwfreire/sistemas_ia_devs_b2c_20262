"""Chama o Claude Code em modo não interativo (claude -p) como se fosse uma chamada de API.

O pedido vai pela entrada padrão, a instrução de sistema vai por arquivo e a resposta volta em JSON, com custo e tempo.
A chamada roda numa pasta vazia e sem permissão para ferramentas: é uma chamada ao modelo, não um agente.
Para usar outro executável, defina a variável CLAUDE_BIN.
"""
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def executavel():
    """Prefere o claude.exe: o claude.cmd do npm passa os argumentos pelo cmd.exe, que estraga textos com | e aspas."""
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    exe = shutil.which("claude.exe")
    if exe:
        return exe
    cmd = shutil.which("claude")
    if cmd and cmd.lower().endswith(".cmd"):
        nativo = Path(cmd).parent / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
        if nativo.exists():
            return str(nativo)
    return cmd or "claude"


def chamar(pedido, sistema=None, schema=None, modelo=None, extras=(), pasta=None):
    """Devolve o JSON de resultado do claude -p, acrescido de 'relogio_ms' (tempo de parede)."""
    cmd = [executavel(), "-p", "--output-format", "json", "--permission-mode", "dontAsk", "--no-session-persistence"]
    if schema:
        cmd += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    if modelo:
        cmd += ["--model", modelo]
    cmd += list(extras)
    with tempfile.TemporaryDirectory() as vazia:
        if sistema:
            arquivo = Path(vazia) / "sistema.txt"
            arquivo.write_text(sistema, encoding="utf-8")
            cmd += ["--system-prompt-file", str(arquivo)]
        inicio = time.perf_counter()
        proc = subprocess.run(cmd, input=pedido, capture_output=True, text=True, encoding="utf-8", cwd=pasta or vazia)
        relogio = round((time.perf_counter() - inicio) * 1000)
    try:
        resultado = json.loads(proc.stdout)
    except json.JSONDecodeError:
        resultado = {"is_error": True, "result": (proc.stdout or proc.stderr).strip()[:500]}
    resultado["relogio_ms"] = relogio
    return resultado


def percentil(valores, p):
    """Percentil pelo método do posto mais próximo: com poucos valores, é um dos valores medidos."""
    if not valores:
        return 0
    ordenados = sorted(valores)
    k = max(0, min(len(ordenados) - 1, math.ceil(p / 100 * len(ordenados)) - 1))
    return ordenados[k]
