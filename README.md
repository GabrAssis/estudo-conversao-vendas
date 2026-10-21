# Estudo de Conversão por Produto (Python)

> Projeto de portfólio para análise exploratória de funil comercial. **Os dados públicos são integralmente sintéticos**, produzidos pelo gerador deste repositório. Não contêm oportunidades, clientes ou parâmetros extraídos de bases privadas.

## Perguntas de negócio
- Como evolui a taxa de ganho por produto, ciclo e perfil (`Novo` vs. `Recompra`)?
- Quais motivos de perda concentram quantidade e valor financeiro?
- Como varia o mix de produtos e a composição de ganhos e perdas?
- Quais diferenças podem ser descritas e quais, **sob premissas explícitas**, podem ser submetidas a testes exploratórios?

## Regras de cálculo

**Taxa de ganho entre oportunidades encerradas**: `WON / (WON + LOST)`; oportunidades `OPEN` são informadas separadamente e não entram no denominador. Essa métrica **não representa conversão de coorte por data de criação**.

Dados agrupados por `Produto`, `Ciclo`, `tipo_cliente`; intervalos de 95% de Wilson. `tipo_cliente=Recompra` sinaliza "cliente ativo" informado pelo CRM, **não comprova recompra do mesmo produto**. IDs duplicados, status inválidos e valores monetários mal formatados geram erro explícito. Valores ausentes nunca são convertidos automaticamente em zero.

## Resultados
- `qualidade`: indicadores de completude e integridade.
- `resumo_ciclo`, `mix_produtos`, `taxas_produto`, `valores_subproduto`.
- `novo_vs_recompra`: diferenças de taxas e intervalos de confiança de Newcombe.
- `perdas_motivos`, `fase_final`, `pareto_quantidade`, `pareto_valor`.
- `associacao_motivos`, `valores_testes`: comparações exploratórias opcionais.
- `tendencias_descritivas`, `panorama_ultimo_ciclo`.
- Gráficos de taxa de ganho com intervalos de confiança e Pareto; `metadados.json` e `LEIA_RESULTADOS.md` com limitações.

Por padrão, **inferência está desativada**. A opção `--inferir` realiza testes exploratórios (teste Z ou exato de Fisher; qui-quadrado com simulação de Monte Carlo, quando necessário; Kruskal–Wallis), com correção Benjamini–Hochberg dentro das famílias indicadas nos metadados. Os testes exigem justificativa para independência amostral, comparabilidade dos grupos e critérios de seleção dos dados; **não demonstram causalidade**. Registros do mesmo cliente bloqueiam o modo inferencial se a coluna `Cliente_ID` estiver preenchida.

## Estrutura
```text
conversao_produto.py
utilitarios.py
scripts/gerar_dados_sinteticos.py
data/synthetic/conversao_sintetica.csv  # 100% fictício
requirements.txt
tests/test_conversao.py
.gitignore
```

## Executar no VS Code (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/gerar_dados_sinteticos.py
python conversao_produto.py --entrada data/synthetic/conversao_sintetica.csv
python -m pytest -q
```

Para rodar testes estatísticos exploratórios na simulação:
```powershell
python conversao_produto.py --entrada data/synthetic/conversao_sintetica.csv --inferir
```

Relatórios e gráficos ficam em `outputs/conversao/` (**não versionados**).

## Uso em dados privados (somente no computador local)
Grave uma cópia da base em `private_data/entrada.xlsx` e execute:
```powershell
python conversao_produto.py --entrada private_data/entrada.xlsx
```

Campos necessários: `ID`, `Funil`, `Ciclo`, `Produto`, `Fase atual`, `Motivo da perda`, `Valor`, `Status` e `Ja e cliente? (cliente ativo 2 anos)`. `subproduto` e `Cliente_ID` são opcionais. `Valor` aceita número nativo ou texto com pontuação `pt_BR` (use `--locale en_US` se necessário).

**Não compartilhe dados originais nem relatórios/gráficos produzidos com dados reais.** Antes de publicar, confira `git status` e `git diff --cached --name-only`; não use `git add -f` para forçar arquivos ignorados. O arquivo sintético é independente de qualquer dado interno.

## Limitações
- Taxas não controlam variação do tempo disponível para fechamento, tamanho de coortes ou mudanças no cadastro.
- Motivo e fase informados representam o **estado final**, não o histórico completo de transições.
- Dados podem ter dependência entre oportunidades, efeito do vendedor, produto, campanha ou cliente.
- Valor das oportunidades perdidas **não é receita perdida comprovada**; pipeline e resultado são conceitos distintos.
- Resultados sintéticos são apenas demonstrações de funcionamento, **não revelam desempenho real** de nenhuma organização.

## Publicação segura no GitHub

Na pasta do projeto, use este fluxo (substitua o endereço remoto pelo seu repositório vazio):

```powershell
git init
git branch -M main
git add .
python scripts/verificar_publicacao.py
git diff --cached --stat
git diff --cached --name-only
git commit -m "Publica estudo com dados sinteticos e testes"
git remote add origin https://github.com/SEU-USUARIO/NOME-DO-REPOSITORIO.git
git push -u origin main
```

**Se a verificação bloquear, não faça o commit/push.** Ela compara a versão staged
(o índice do Git) do CSV com os bytes esperados do gerador e impede arquivos fora
da lista aprovada. Ainda assim, auditoria humana do código/documentação é necessária:
detecção automática não garante identificar todo tipo de informação confidencial.
