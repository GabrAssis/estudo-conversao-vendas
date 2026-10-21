"""Reproduz imagens e tabelas do README exclusivamente com o gerador fictício."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

from conversao_produto import preparar_dados, tabela_taxas
from scripts.gerar_dados_sinteticos import gerar
from scripts.relatorio_portfolio import artefatos_relatorio
from utilitarios import pareto

INICIO, FIM = "<!-- RESULTADOS:SINTETICOS:INICIO -->", "<!-- RESULTADOS:SINTETICOS:FIM -->"


def numero(v, casas=0):
    return f"{v:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def png(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160, facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def artefatos():
    """Não aceita arquivos externos: gráficos públicos usam somente gerar(2026)."""
    d, _ = preparar_dados(gerar(2026))
    taxas = tabela_taxas(d)
    resumo = tabela_taxas(d, ("Produto",))
    perdas = pareto(d[d.perdido], "motivo_perda")
    imagens = {}
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharey=True)
        periodos = list(d.Período.cat.categories)
        for ax, (produto, grupo) in zip(axes, taxas.groupby("Produto", observed=True)):
            for tipo, cor, marcador in [("Novo", "#2463A6", "o"), ("Recompra", "#B15A16", "s")]:
                h = grupo[grupo.tipo_cliente.eq(tipo)].set_index("Período").reindex(periodos)
                y = h.taxa_ganho_encerradas.to_numpy(float) * 100
                erro = np.vstack([y - h.ic95_wilson_inf.to_numpy(float)*100,
                                  h.ic95_wilson_sup.to_numpy(float)*100 - y])
                ax.errorbar(range(len(periodos)), y, yerr=erro, color=cor,
                            marker=marcador, capsize=3,
                            label="Cliente ativo" if tipo == "Recompra" else "Novo")
            ax.set(title=produto, ylim=(0, 100), xlabel="Período",
                   xticks=range(len(periodos)), xticklabels=[p.removeprefix("Ciclo ") for p in periodos])
            ax.yaxis.set_major_formatter(PercentFormatter(100))
            ax.grid(axis="y", alpha=.18)
        axes[0].set_ylabel("Taxa de ganho entre encerradas")
        axes[-1].legend(loc="upper right", frameon=False)
        fig.suptitle("Taxa de ganho por produto, período e perfil", fontsize=15, fontweight="bold")
        fig.text(.5, .02, "Dados 100% fictícios • IC de 95% de Wilson • WON / (WON + LOST); OPEN fora do denominador",
                 ha="center", fontsize=9, color="#555555")
        fig.tight_layout(rect=(0, .05, 1, .93))
        imagens["docs/assets/taxas_por_periodo.png"] = png(fig)

        fig, ax = plt.subplots(figsize=(10, 4.9))
        ax.barh(perdas.motivo_perda, perdas.medida, color="#2463A6")
        ax.invert_yaxis()
        ax.set(xlabel="Oportunidades perdidas (quantidade)",
               title="Motivos das perdas | todos os produtos e períodos")
        ax.set_xlim(0, perdas.medida.max()*1.25)
        for i, row in enumerate(perdas.itertuples()):
            ax.text(row.medida + 4, i, f"{int(row.medida)} ({numero(row.participacao*100, 1)}%)", va="center")
        ax.grid(axis="x", alpha=.15)
        ax.set_axisbelow(True)
        fig.text(.5, .02, "Dados 100% fictícios • participação calculada sobre todas as oportunidades LOST", ha="center", fontsize=9)
        fig.tight_layout(rect=(0, .05, 1, 1))
        imagens["docs/assets/motivos_perda.png"] = png(fig)

    linhas = ["## Resultados da demonstração", "",
              f"**{numero(len(d))} oportunidades fictícias · {numero(d.encerrado.sum())} encerradas · "
              f"{numero(d.ganho.sum())} ganhos · {numero((~d.encerrado).sum())} abertas.**", "",
              "### Conversão por produto", "",
              "| Produto | Encerradas | Ganhos | Abertas | Taxa de ganho | IC 95% | Valor ganho simulado (R$) |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for r in resumo.itertuples():
        linhas.append(f"| {r.Produto} | {numero(r.encerradas)} | {numero(r.ganhos)} | {numero(r.abertas)} | "
                      f"{numero(r.taxa_ganho_encerradas*100, 1)}% | "
                      f"{numero(r.ic95_wilson_inf*100, 1)}%–{numero(r.ic95_wilson_sup*100, 1)}% | {numero(r.valor_ganho, 2)} |")
    taxa = d.ganho.sum()/d.encerrado.sum()
    linhas += ["", f"Taxa geral: **{numero(taxa*100, 1)}%**, calculada pela soma dos ganhos dividida pela soma das encerradas.", "",
               "![Taxas de ganho por produto e período, com intervalos de 95%](docs/assets/taxas_por_periodo.png)", "",
               "O gráfico compara novos clientes e clientes ativos. O perfil interno `Recompra` é apresentado como "
               "**Cliente ativo** e mantém a definição original de atividade nos últimos dois anos.", "",
               "### Composição das perdas", "",
               "![Quantidade e participação dos motivos de perda na simulação](docs/assets/motivos_perda.png)", "",
               "| Motivo | Quantidade | Participação nas perdas | Acumulado |", "|---|---:|---:|---:|"]
    for r in perdas.itertuples():
        linhas.append(f"| {r.motivo_perda} | {numero(r.medida)} | {numero(r.participacao*100, 1)}% | {numero(r.participacao_acumulada*100, 1)}% |")
    lider = resumo.sort_values("taxa_ganho_encerradas", ascending=False).iloc[0]
    primeiro = perdas.iloc[0]
    linhas += ["", "### Leitura de negócio", "",
               f"- Na simulação, **{lider.Produto}** apresenta a maior taxa agregada de ganho ({numero(lider.taxa_ganho_encerradas*100, 1)}%).",
               f"- **{primeiro.motivo_perda}** concentra {numero(primeiro.participacao*100, 1)}% das perdas simuladas; esse recorte exemplifica como priorizar investigações comerciais.",
               "- A comparação por perfil e período ajuda a distinguir mudanças de composição de mudanças na taxa de ganho.", "",
               "Fonte: `scripts/gerar_dados_sinteticos.py`, seed `2026`; tabelas e imagens reproduzidas por "
               "`python scripts/gerar_portfolio.py`. Estes resultados demonstram o método e não representam desempenho de empresas reais."]
    imagens.update(artefatos_relatorio())
    return imagens, "\n".join(linhas)


def main():
    imagens, trecho = artefatos()
    for nome, conteudo in imagens.items():
        destino = ROOT/nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
    caminho = ROOT/"README.md"
    texto = caminho.read_text(encoding="utf-8")
    if texto.count(INICIO) != 1 or texto.count(FIM) != 1:
        raise ValueError("README precisa conter um par de marcadores de resultados.")
    antes, restante = texto.split(INICIO)
    _, depois = restante.split(FIM)
    caminho.write_text(antes+INICIO+"\n"+trecho+"\n"+FIM+depois, encoding="utf-8")
    print("README, relatório e imagens atualizados usando exclusivamente dados fictícios.")


if __name__ == "__main__":
    main()
