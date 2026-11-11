# Sistemas com IA para Devs · Turma 2026.2-A

Material de apoio dos módulos M3 (Workflows, agentes, tool use e MCPs) e M4 (Evals, logs e guardrails na prática). CESAR School.

## O que tem aqui

A pasta [`caso-balcao`](caso-balcao/README.md) traz o caso usado nas seis aulas: o suporte do Balcão, uma plataforma fictícia de pagamentos para pequenos comércios. Ela tem os tickets, os dados, o servidor MCP, o hook de guarda e os scripts das demonstrações. As práticas dos estudos dirigidos partem desta pasta.

O estudo dirigido de cada aula, em PDF, sai no canal da turma ao fim da aula.

## Como começar

Você precisa do Claude Code com login feito e do Python 3.11 ou mais novo.

```
git clone https://github.com/victorhwfreire/sistemas_ia_devs_b2c_20262.git
cd sistemas_ia_devs_b2c_20262/caso-balcao
pip install -r requirements.txt
cd ferramentas
python workflow_triagem.py TCK-002
```

No Windows PowerShell, rode antes `[Console]::OutputEncoding = [Text.Encoding]::UTF8; $env:PYTHONUTF8 = "1"` para os acentos saírem certos. O [README do caso](caso-balcao/README.md) explica cada arquivo e os comandos mais usados.

Para receber atualizações entre as aulas, rode `git pull` na pasta do repositório. As práticas que alteram arquivos do caso pedem que você trabalhe numa cópia; assim o `git pull` não conflita com as suas mudanças.

## As aulas

| Aula | Data | Tema |
|---|---|---|
| M3 · 1 | Qua, 11/11 | Workflow ou agente: quem decide o próximo passo |
| M3 · 2 | Seg, 16/11 | Tool use: o modelo pede, o seu código executa |
| M3 · 3 | Qua, 18/11 | MCP: plugar ferramentas sem perder o controle |
| M4 · 1 | Seg, 23/11 | Evals: sem medir, não dá para dizer que melhorou |
| M4 · 2 | Qua, 25/11 | Logs e custo: explicar o que aconteceu e quanto custou |
| M4 · 3 | Seg, 30/11 | Guardrails: o controle não pode depender do modelo |

Todas on-line, das 19h às 22h.

## Segurança

Os dados são fictícios e o estorno do servidor é simulado: ele só grava uma linha em `caso-balcao/estado/estornos.jsonl`. Não aponte as ferramentas para sistemas reais.
