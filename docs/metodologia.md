# Metodologia da análise de conversão de vendas

O estudo descreve o resultado das oportunidades comerciais por produto, período e perfil. Cada decisão abaixo conecta uma pergunta de negócio à técnica implementada, ao motivo da escolha e à evidência produzida pelo código.

## Objetivo e unidade de análise

Uma linha de entrada representa uma oportunidade com ID único na base selecionada. O desfecho é `WON`, `LOST` ou `OPEN`. As agregações mantêm produto, período e perfil como dimensões; uma comparação agregada é identificada explicitamente.

A demonstração usa 1.650 oportunidades inventadas por `scripts/gerar_dados_sinteticos.py`, seed 2026. Probabilidades, valores e motivos são parâmetros fictícios, sem estimação em dados empresariais. O gerador de portfólio usa esse gerador diretamente, sem receber caminhos para bases externas.

## Técnicas utilizadas e por que foram escolhidas

| Técnica | Aplicação no estudo | Motivo da escolha |
|---|---|---|
| Contrato de dados e reconciliação | Valida colunas, IDs, status e valores; separa abertas de encerradas | Estabelece grão e denominador verificáveis antes das métricas |
| Taxa de ganho entre encerradas | `WON / (WON + LOST)` | Compara desfechos conhecidos; abertas ficam visíveis em separado |
| Razão entre totais | Soma de ganhos / soma de encerradas | Preserva o peso dos grupos; evita média simples de taxas |
| Wilson de 95% | Intervalo de cada taxa | Mostra incerteza binomial e produz limites dentro de 0 a 1, inclusive nas bordas |
| Newcombe de 95% | Intervalo de Novo − Cliente ativo | Quantifica a diferença em pontos percentuais com os intervalos dos dois grupos |
| Teste Z ou Fisher | Comparação exploratória de duas proporções | Escolhe o teste pela frequência esperada; Fisher atende tabelas 2×2 esparsas |
| Pareto por quantidade ou valor | Participação e acumulado por motivo | Ordena prioridades de investigação sem impor a regra 80/20 aos dados |
| Qui-quadrado, Fisher ou Monte Carlo | Associação de motivos com perfil ou fase | Adequa o cálculo do p-valor ao formato e à esparsidade da tabela |
| V de Cramér | Magnitude da associação categórica | Acrescenta tamanho de efeito à leitura de p e q |
| Média, mediana e quartis | Distribuição dos valores ganhos | Expõe centro e dispersão de valores assimétricos |
| Kruskal–Wallis e epsilon² | Valores perdidos por fase ou motivo | Compara grupos sem pressupor normalidade e acompanha a magnitude do efeito |
| Benjamini–Hochberg | Famílias completas de testes | Controla descobertas falsas nas condições de dependência do procedimento |
| Ajuste linear descritivo ponderado | Taxa ao longo da posição dos períodos | Resume direção observada, dando mais peso a grupos com mais encerradas |

## Fórmulas e interpretação

### Taxas e intervalos

`taxa = ganhos / (ganhos + perdas)`; `abertas = total − encerradas`.

Para proporção `p = x/n`, o intervalo de Wilson usa `z = 1,95996`, centro `(p + z²/2n)/(1 + z²/n)` e semi-amplitude `z × sqrt[p(1−p)/n + z²/(4n²)]/(1 + z²/n)`. Sem encerradas, taxa e intervalo permanecem ausentes.

A diferença é `100 × (taxa_novo − taxa_ativo)`. Newcombe combina os limites de Wilson dos dois grupos para obter um intervalo assimétrico da diferença. Os ICs apresentados são individuais, sem ajuste múltiplo. Sobreposição de ICs separados não substitui o teste da diferença. IC de 95% descreve a cobertura do procedimento sob suas premissas; não é probabilidade posterior sobre a taxa.

### Escolha dos testes

`comparar_proporcoes` usa teste Z bilateral se todas as frequências esperadas forem pelo menos cinco; caso contrário usa Fisher bilateral. Grupos sem encerradas são não aplicáveis. Desfechos degenerados recebem tratamento explícito.

`associacao` usa Pearson sem correção de Yates quando as frequências esperadas são pelo menos cinco. Para esparsidade, usa Fisher em 2×2 ou Monte Carlo em tabelas maiores, com 9.999 reamostragens e seed 90210. `V = sqrt[χ² / (n × min(linhas−1, colunas−1))]` acompanha o p-valor.

`testes_valores` usa Kruskal–Wallis se houver ao menos dois grupos e cinco valores conhecidos por grupo. O código mantém comparações não identificáveis como ausentes. Epsilon² usa `max(0, (H−k+1)/(n−k))`, com `k` grupos. O teste compara distribuições; uma leitura específica de medianas exige formas de distribuição comparáveis. O teste global não localiza os pares diferentes, e este projeto não executa pós-testes de Dunn.

### Múltiplas comparações

O p ajustado BH aparece como q no relatório. As famílias são definidas pela pergunta, antes de observar os resultados:

| Família | Escopo da simulação | Ajuste |
|---|---|---|
| Novo versus cliente ativo | 3 produtos × 5 períodos = 15 comparações | BH sobre os p-valores calculáveis da família |
| Associação de motivos | 3 produtos × 5 períodos × 2 dimensões = 30 | BH próprio para essa família |
| Distribuição dos valores | 3 produtos × 5 períodos × 2 perfis × 2 dimensões = 60 | BH próprio para essa família |

O relatório mostra todas as combinações, incluindo testes não calculados; valores ausentes não são convertidos em p = 1. A garantia de FDR depende de p-valores válidos e de condições de independência ou dependência positiva apropriadas. O ajuste não corrige viés de seleção nem dependência entre oportunidades.

### Tendência descritiva

O ajuste minimiza desvios quadráticos com peso efetivo igual ao número de encerradas; `numpy.polyfit` recebe a raiz desse peso. O eixo é a posição ordinal dos períodos observados, sem afirmar distância anual quando houver lacunas. A inclinação é uma síntese descritiva, sem previsão ou teste causal.

## Boas práticas e evidências verificáveis

| Prática | Por que importa | Evidência no projeto |
|---|---|---|
| Grão explícito e IDs únicos | Evita multiplicar oportunidades em agregações | `preparar_dados` e teste de ID duplicado |
| Ausências preservadas | Evita inventar receita zero | `moeda`, `soma_completa` e teste de valores desconhecidos |
| Abertas separadas | Torna o denominador auditável | Tabelas com total, encerradas, ganhos, perdas e abertas |
| Tamanho de amostra e IC | Dá contexto às diferenças de taxas | Relatório com n, taxas, diferença e IC |
| Métodos condicionados aos dados | Evita aproximações escolhidas sem checar contagens | Frequências esperadas, Fisher e Monte Carlo |
| Famílias de testes explícitas | Evita selecionar apenas resultados favoráveis | Tabelas completas com p e q BH |
| Reprodutibilidade | Permite refazer tabelas e gráficos | Seeds fixas, geradores e scripts versionados |
| Proteção da publicação | Confere a origem da demonstração | Verificador do índice, CSV, imagens, relatório e README |
| Proteção do Excel | Evita executar rótulos como fórmulas | `exportar_excel` neutraliza prefixos de fórmula |

## Condições de uso e leitura comercial

Os métodos binomiais e os testes pressupõem oportunidades independentes, grupos comparáveis e um modelo amostral apropriado. `Cliente_ID` repetido bloqueia a inferência independente quando esse campo existe; a ausência do campo não comprova independência. No portfólio, as observações vêm da simulação.

A taxa descreve encerradas, sem representar conversão de coorte por data de criação. Fase e motivo são o estado final informado, sem histórico de transições. Cliente ativo não comprova compra anterior do mesmo produto. Valor de oportunidades perdidas representa exposição comercial; não é receita perdida comprovada.

As recomendações são hipóteses de uso dos indicadores, acompanhadas das validações necessárias. Não são apresentadas como ROI, impacto financeiro realizado ou efeito causal.

## Dicionário e compatibilidade

Uma linha representa uma oportunidade. Campos obrigatórios: `ID`, `Base`, `Período`, `Produto`, `Fase atual`, `Motivo da perda`, `Valor`, `Status` e `Cliente ativo?`. `subproduto` e `Cliente_ID` são opcionais.

| Nome anterior | Nome atual |
|---|---|
| `Funil` | `Base` |
| `Funil de Vendas` (valor) | `Vendas` |
| `Ciclo` | `Período` |
| `Ja e cliente? (cliente ativo 2 anos)` | `Cliente ativo?` |

As variantes acentuadas do campo de cliente também são aceitas. Colunas antigas e atuais que se convertam no mesmo campo são rejeitadas se presentes juntas. `--funil "Funil de Vendas"` permanece equivalente a `--base Vendas`. As chamadas Python legadas com `funil=` continuam aceitas.

`Cliente ativo?` mantém a definição original de atividade nos últimos dois anos: `Sim` corresponde ao segmento interno `Recompra`, `Não` a `Novo`, demais valores a `Desconhecido`. Não comprova recompra do mesmo produto.

Os identificadores `Ciclo 01` a `Ciclo 05` foram preservados para manter as chaves. Nos gráficos do README, aparecem como `01` a `05`, sob o eixo **Período**. A janela não é reinterpretada como ano civil.

As saídas usam `resumo_periodo`, `panorama_ultimo_periodo`, `participacao_no_periodo`, `periodos_observados` e `inclinacao_descritiva_pp_por_periodo`. Consumidores das tabelas devem atualizar esses nomes. Registros, ordem, fórmulas e resultados numéricos são preservados.


## Reproduzir e revisar

```powershell
python scripts/gerar_dados_sinteticos.py
python scripts/gerar_portfolio.py
python conversao_produto.py --base Vendas --inferir
python -m pytest -q
git add .
python scripts/verificar_publicacao.py
```

O script analítico gera saídas locais em `outputs/`; o gerador de portfólio atualiza README, relatório e imagens públicas exclusivamente com a simulação. O verificador compara esses artefatos no índice Git com sua reprodução. Bases e saídas privadas permanecem nas pastas ignoradas; não use `git add -f` para publicá-las.

## Referências técnicas

- [SciPy — controle de falsas descobertas](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.false_discovery_control.html)
- [statsmodels — intervalo de proporção e Wilson](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html)
- [statsmodels — diferenças entre proporções e Newcombe](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html)
- [SciPy — qui-quadrado e Monte Carlo](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.contingency.chi2_contingency.html)
- [SciPy — Kruskal–Wallis](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.kruskal.html)

As referências documentam os métodos. As funções implementadas e os resultados deste projeto podem ser conferidos no código, nos testes e no [relatório reproduzível](relatorio.md).
