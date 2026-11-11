# Caso Balcão

O Balcão é uma plataforma fictícia de pagamentos para pequenos comércios: maquininha, link de pagamento e API. O suporte recebe tickets em texto livre e precisa triar, investigar e responder. O caso atravessa as seis aulas de M3 e M4 de Sistemas com IA para Devs (turma 2026.2-A). Nomes, valores e dados são inventados.

## O que tem aqui

| Arquivo | O que é | Aulas |
|---|---|---|
| `tickets.json` | 12 tickets com gabarito de categoria, prioridade e time | todas |
| `dados/clientes.json` | os 12 clientes | todas |
| `dados/cobrancas.json` | lançamentos de outubro e novembro de 2026, com duas cobranças duplicadas e tarifas sem contrato | todas |
| `dados/politica-atendimento.md` | categorias, prioridade e regras de estorno | todas |
| `ferramentas/workflow_triagem.py` | workflow de três passos: classificar, rotear, responder | M3.1, M4.2 |
| `ferramentas/rodar_agente.py` | roda o agente de suporte (Claude Code em modo `-p`) num ticket e grava o registro | M3.1, M3.2, M3.3, M4.2, M4.3 |
| `ferramentas/ler_execucao.py` | resume um registro: passos, ferramentas, tempo, tokens e custo | M3.1 em diante |
| `ferramentas/servidor_balcao.py` | servidor MCP com contrato fraco ou forte; estorno simulado | M3.2, M3.3, M4.3 |
| `ferramentas/guarda.py` | hook do Claude Code que registra cada chamada e aplica a política de estorno | M3.3, M4.3 |
| `ferramentas/eval_triagem.py` | eval da triagem contra o gabarito, com repetições | M4.1, M4.2 |
| `prompts/a.txt` e `prompts/b.txt` | duas instruções de classificação para comparar no eval | M4.1 |
| `estado/` | criada ao rodar: `chamadas.jsonl` (log do servidor), `auditoria.jsonl` (log do hook), `notas.jsonl`, `estornos.jsonl` e `config/` | — |

## Preparar

1. Claude Code com login feito. Teste: `claude -p "responda apenas: ok"` precisa responder `ok`.
2. Python 3.11 ou mais novo e o SDK do MCP: `pip install -r requirements.txt` (a aula 1 do M3 não precisa dele).
3. No Windows PowerShell, para os acentos no terminal e no hook: `[Console]::OutputEncoding = [Text.Encoding]::UTF8; $env:PYTHONUTF8 = "1"`.
4. Os comandos partem da pasta `ferramentas`.

## Comandos mais usados

```
python workflow_triagem.py TCK-001 TCK-002
python rodar_agente.py --ticket TCK-002 --modo arquivos --saida ag.jsonl
python rodar_agente.py --ticket TCK-002 --modo mcp --contrato fraco --saida fraco.jsonl
python rodar_agente.py --ticket TCK-012 --modo mcp --limites com --saida guarda.jsonl
python ler_execucao.py ag.jsonl
python eval_triagem.py --prompt ../prompts/b.txt --repeticoes 2
```

Cada execução usa o Claude da sua conta. O custo que aparece é a estimativa do Claude Code; em assinatura, não há cobrança por chamada. O `rodar_agente.py` tem teto de US$ 0,50 por execução (`--orcamento`).

## Segurança

O estorno do servidor é simulado: ele só grava uma linha em `estado/estornos.jsonl`. Os dados são fictícios. Mesmo assim, rode tudo numa pasta sua e não aponte as ferramentas para sistemas reais.
