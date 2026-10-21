"""Relatório público reproduzível; entrada exclusivamente sintética e fixa."""
from __future__ import annotations

import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from conversao_produto import (preparar_dados, tabela_taxas, comparar_tipos,
                               tabelas_perdas, testes_valores, tendencias)
from scripts.gerar_dados_sinteticos import gerar
from utilitarios import pareto


def fmt(v, casas=2):
    if pd.isna(v):
        return "—"
    return f"{v:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def tabela(cabecalhos, linhas):
    return "\n".join(["| " + " | ".join(cabecalhos) + " |",
                      "|" + "---|"*len(cabecalhos)] +
                     ["| " + " | ".join(map(str, linha)) + " |" for linha in linhas])


def artefatos_relatorio():
    dados, qualidade = preparar_dados(gerar(2026))
    taxas = tabela_taxas(dados)
    periodos = tabela_taxas(dados, ("Período",))
    comparacoes = comparar_tipos(taxas, inferir=True)
    perdas = tabelas_perdas(dados, inferir=True, seed=90210, reamostragens=9999)
    valores = testes_valores(dados, inferir=True)
    motivos = pareto(dados[dados.perdido], "motivo_perda")
    tendencia = tendencias(taxas, list(dados.Período.cat.categories))
    arquivos = {}

    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False}):
        fig, ax = plt.subplots(figsize=(10.5, 8))
        cores = {"Produto A": "#2463A6", "Produto B": "#B15A16", "Produto C": "#667C32"}
        for i, (_, r) in enumerate(comparacoes.iterrows()):
            delta = r.diferenca_novo_menos_recompra_pp
            erro = np.array([[delta-r.ic95_diferenca_inf_pp], [r.ic95_diferenca_sup_pp-delta]])
            ax.errorbar(delta, i, xerr=erro, fmt="o", color=cores[r.Produto], capsize=3)
        ax.set(yticks=range(len(comparacoes)),
               yticklabels=[f"{r.Produto} | {str(r['Período']).removeprefix('Ciclo ')}" for _, r in comparacoes.iterrows()],
               xlabel="Taxa de novos − taxa de clientes ativos (p.p.)",
               ylabel="Produto | Período", title="Diferenças de taxas e IC de 95% de Newcombe")
        ax.invert_yaxis()
        ax.axvline(0, color="#555555", linestyle="--", linewidth=1)
        ax.grid(axis="x", alpha=.18)
        fig.text(.5, .02, "Dados fictícios • ICs individuais, sem ajuste múltiplo • taxas entre oportunidades encerradas", ha="center", fontsize=9)
        fig.tight_layout(rect=(0, .05, 1, 1))
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=160, facecolor="white")
        plt.close(fig)
        arquivos["docs/assets/diferencas_perfis.png"] = buffer.getvalue()

    wins, closed = int(dados.ganho.sum()), int(dados.encerrado.sum())
    selecionados = motivos[motivos.selecionado_80]
    linhas = ["# Relatório de conversão de vendas com dados fictícios", "",
              "Relatório gerado por código, com leitura executiva, evidências e decisões metodológicas. "
              "Todos os registros, categorias e valores foram inventados pelo gerador deste projeto (seed 2026).", "",
              "## Resumo executivo", "",
              f"A simulação contém **{fmt(len(dados), 0)} oportunidades**, das quais **{fmt(closed, 0)} encerradas** e "
              f"**{fmt(wins, 0)} ganhas**. A taxa geral de ganho é **{fmt(100*wins/closed, 1)}%**. "
              "A leitura combina taxa, volume, perfil e composição das perdas para orientar investigações comerciais.", "",
              "Os indicadores descrevem oportunidades encerradas. A relação de atividade nos últimos dois anos "
              "define o perfil de cliente ativo; o segmento interno `Recompra` mantém essa mesma regra.", "",
              "## Evolução por período", "",
              tabela(["Período", "Oportunidades", "Encerradas", "Ganhos", "Perdas", "Abertas", "Taxa de ganho"],
                     [[r['Período'], fmt(r.oportunidades_total,0), fmt(r.encerradas,0), fmt(r.ganhos,0),
                       fmt(r.perdas,0), fmt(r.abertas,0), fmt(r.taxa_ganho_encerradas*100,1)+"%"] for _,r in periodos.iterrows()]), "",
              "**Método e motivo:** `WON / (WON + LOST)` usa apenas desfechos encerrados. As abertas são mostradas "
              "separadamente para dar visibilidade ao volume ainda sem desfecho. O total é calculado como razão entre "
              "as somas, preservando o peso dos grupos. Diferenças de prazo para fechamento exigiriam análise de coorte específica.", "",
              "![Taxas de ganho por produto, período e perfil](assets/taxas_por_periodo.png)", "",
              "## Comparação entre novos clientes e clientes ativos", "",
              "![Diferenças de taxas com intervalos de Newcombe](assets/diferencas_perfis.png)", "",
              "A diferença segue **Novo − Cliente ativo**, em pontos percentuais. Valores negativos indicam taxa menor "
              "para novos naquela combinação de produto e período. Cada intervalo de 95% é individual, sem ajuste "
              "para múltiplas comparações; a coluna q ajusta os testes da família completa de 15 comparações.", "",
              tabela(["Produto", "Período", "n novo", "n ativo", "Novo", "Ativo", "Diferença (p.p.)", "IC 95% (p.p.)", "Teste", "p", "q BH"],
                     [[r.Produto, r['Período'], fmt(r.n_novo,0), fmt(r.n_recompra,0), fmt(r.taxa_novo*100,1)+"%",
                       fmt(r.taxa_recompra*100,1)+"%", fmt(r.diferenca_novo_menos_recompra_pp,1),
                       fmt(r.ic95_diferenca_inf_pp,1)+" a "+fmt(r.ic95_diferenca_sup_pp,1), r.teste,
                       fmt(r.p_valor,6), fmt(r.p_ajustado_bh,6)] for _,r in comparacoes.iterrows()]), "",
              "**Métodos e motivos:** Wilson descreve a incerteza de cada proporção; Newcombe combina os intervalos "
              "de Wilson para estimar a diferença entre dois grupos independentes. O teste Z compara proporções quando "
              "todas as frequências esperadas são pelo menos cinco; em tabelas 2×2 esparsas, o código usa Fisher bilateral. "
              "A implementação trata explicitamente grupos sem encerradas e desfechos degenerados.", "",
              "## Concentração dos motivos de perda", "",
              "![Motivos das perdas simuladas](assets/motivos_perda.png)", "",
              f"O conjunto que alcança ou ultrapassa 80% reúne **{len(selecionados)} motivos**, com "
              f"**{fmt(selecionados.participacao.sum()*100,1)}%** das perdas da simulação. "
              "A análise de Pareto é uma regra de priorização; a proporção 80/20 não é imposta aos dados.", "",
              "**Método e motivo:** ordenar contagens e participações acumuladas permite dimensionar quais motivos "
              "merecem investigação primeiro. A mesma lógica pode usar valores completos das oportunidades; "
              "esses valores representam exposição comercial, sem equivaler a receita perdida comprovada.", "",
              "## Associação entre motivos e perfis ou fases", "",
              tabela(["Produto", "Período", "Comparação", "Perdas", "Teste aplicado", "Menor esperado", "V de Cramér", "p", "q BH"],
                     [[r.Produto,r['Período'],r.comparacao,fmt(r.n_perdas,0),r.teste,fmt(r.menor_esperado),
                       fmt(r.cramer_v,3),fmt(r.p_valor,6),fmt(r.p_ajustado_bh,6)] for _,r in perdas['associacao_motivos'].iterrows()]), "",
              "**Métodos e motivos:** qui-quadrado avalia associação em tabelas categóricas; Fisher é usado para "
              "tabelas 2×2 esparsas e Monte Carlo para tabelas maiores com frequências esperadas pequenas. "
              "São 9.999 reamostragens, com seed 90210. V de Cramér informa a magnitude da associação. "
              "As 30 comparações formam uma família BH própria, sem selecionar apenas p-valores favoráveis.", "",
              "## Distribuição dos valores ganhos", "",
              tabela(["Produto", "Ganhos", "Média (R$)", "Mediana (R$)", "P25 (R$)", "P75 (R$)"],
                     [[produto,fmt(len(g),0),fmt(g.valor_num.mean()),fmt(g.valor_num.median()),
                       fmt(g.valor_num.quantile(.25)),fmt(g.valor_num.quantile(.75))]
                      for produto,g in dados[dados.ganho].groupby('Produto',observed=True)]), "",
              "**Método e motivo:** média e mediana são apresentadas com quartis para descrever valores assimétricos. "
              "A mediana informa o centro da distribuição; a dispersão é examinada pelos quartis. "
              "Os valores são preservados, sem remoção automática de extremos ou preenchimento de ausências com zero.", "",
              "### Comparações de valores por fase ou motivo", "",
              f"**{int(valores.p_valor.notna().sum())} comparações atendem aos critérios de cálculo** da simulação. "
              "A tabela principal mostra essas comparações; o registro integral das 60 combinações fica disponível abaixo para auditoria.", "",
              tabela(["Produto", "Período", "Perfil interno", "Comparação", "Grupos", "H", "Epsilon²", "p", "q BH"],
                     [[r.Produto,r['Período'],r.tipo_cliente,r.comparacao,fmt(r.grupos,0),
                       fmt(r.H,3),fmt(r.epsilon_quadrado,3),fmt(r.p_valor,6),fmt(r.p_ajustado_bh,6)]
                      for _,r in valores[valores.p_valor.notna()].iterrows()]), "",
              "<details>", "<summary>Consultar o registro completo das 60 combinações</summary>", "",
              tabela(["Produto", "Período", "Perfil interno", "Comparação", "Grupos", "Situação / método", "H", "Epsilon²", "p", "q BH"],
                     [[r.Produto,r['Período'],r.tipo_cliente,r.comparacao,fmt(r.grupos,0),r.teste,
                       fmt(r.H,3),fmt(r.epsilon_quadrado,3),fmt(r.p_valor,6),fmt(r.p_ajustado_bh,6)] for _,r in valores.iterrows()]), "",
              "</details>", "",
              "**Método e motivo:** Kruskal–Wallis compara distribuições de valores de oportunidades perdidas "
              "entre categorias, sem pressupor normalidade. Requer ao menos dois grupos e cinco valores conhecidos "
              "em cada um na regra implementada. Categorias pequenas não são descartadas para fabricar um teste. "
              "Epsilon² acompanha H como medida descritiva de efeito. As 60 comparações compõem outra família BH; "
              "resultados não calculáveis permanecem ausentes. O teste global não identifica quais pares diferem.", "",
              "## Tendências descritivas", "",
              tabela(["Produto", "Perfil interno", "Períodos", "Inclinação (p.p./posição)", "Primeiro → último (p.p.)"],
                     [[r.Produto,r.tipo_cliente,fmt(r.periodos_observados,0),fmt(r.inclinacao_descritiva_pp_por_periodo),
                       fmt(r.variacao_primeiro_ultimo_pp)] for _,r in tendencia.iterrows()]), "",
              "**Método e motivo:** ajuste linear descritivo ponderado pelo número de encerradas dá mais peso "
              "a grupos com mais observações. O eixo é a posição ordinal dos períodos; a inclinação não é "
              "previsão nem crescimento anual e não vem acompanhada de teste inferencial de tendência.", "",
              "## Qualidade e reconciliação", "",
              tabela(["Controle executado", "Quantidade"],[[r.controle,fmt(r.quantidade,0)] for r in qualidade.itertuples()]), "",
              f"Reconciliação: **{fmt(wins,0)} ganhos + {fmt(dados.perdido.sum(),0)} perdas = {fmt(closed,0)} encerradas**; "
              f"encerradas + {fmt((~dados.encerrado).sum(),0)} abertas = {fmt(len(dados),0)} oportunidades.", "",
              "A validação também rejeita ID duplicado, status desconhecido, valor monetário inválido e "
              "cabeçalhos ambíguos. Valores ausentes permanecem desconhecidos. Exportações Excel neutralizam "
              "rótulos iniciados por caracteres de fórmula.", "",
              "## Recomendações demonstrativas", "",
              "| Evidência examinada | Aplicação comercial possível | Validação antes de agir |",
              "|---|---|---|",
              "| Motivos com maior participação acumulada | Priorizar entrevistas comerciais e revisão de propostas | Conferir preenchimento, amostras e contexto dos motivos |",
              "| Diferenças de taxas por perfil e período | Investigar ações específicas de aquisição e relacionamento | Controlar produto, canal, maturidade e composição das oportunidades |",
              "| Valores e volume por produto | Dimensionar o impacto potencial de uma iniciativa | Confirmar completude e distinguir valor de oportunidade de receita reconhecida |",
              "| Variação entre períodos | Acompanhar mudanças de execução e cadastro | Conferir janelas de fechamento e testar hipóteses de negócio |", "",
              "As ações são exemplos de uso dos indicadores. Não foram implantadas nem representam ganho financeiro realizado.", "",
              "## Reprodutibilidade e interpretação", "",
              "```powershell", "python scripts/gerar_dados_sinteticos.py", "python scripts/gerar_portfolio.py",
              "python conversao_produto.py --base Vendas --inferir", "python -m pytest -q", "```", "",
              "O relatório público executa as comparações exploratórias exclusivamente sobre a simulação. "
              "O comando principal mantém inferência desativada até receber `--inferir`. Os intervalos e testes "
              "pressupõem oportunidades independentes, grupos comparáveis e um modelo de amostragem apropriado. "
              "Em dados reais, IDs de cliente repetidos bloqueiam o modo independente quando identificáveis. "
              "q BH controla descobertas falsas sob as condições do procedimento, sem transformar p em probabilidade "
              "de a hipótese ser verdadeira nem conferir interpretação causal.", "",
              "[Metodologia e justificativas](metodologia.md) · [Voltar ao README](../README.md)"]
    arquivos['docs/relatorio.md'] = ('\n'.join(linhas)+'\n').encode('utf-8')
    return arquivos
