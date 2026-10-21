"""Conversão por produto: dados validados, taxas, perdas e inferência opcional.

Execução: python conversao_produto.py
Ajuda: python conversao_produto.py --help
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import fill

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from utilitarios import (ErroDados, ajustar_bh, associacao, chave, comparar_proporcoes,
                         conclusao, exigir_colunas, exportar_excel, ler_tabela,
                         moeda, nome_seguro, ordem_natural, pareto, texto, wilson)

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "data/synthetic/conversao_sintetica.csv"
COLUNAS = ["ID", "Base", "Período", "Produto", "Fase atual", "Motivo da perda",
           "Valor", "Status", "Cliente ativo?"]
ALIAS = {"Ciclo": "Período", "Funil": "Base",
         "Ja e cliente? (cliente ativo 2 anos)": COLUNAS[-1], "Já e cliente? (cliente ativo 2 anos)": COLUNAS[-1],
         "Já é cliente? (cliente ativo 2 anos)": COLUNAS[-1]}
SIM = {"sim", "s", "true", "1", "1.0"}
NAO = {"nao", "n", "false", "0", "0.0"}
STATUS = {"won": "WON", "ganho": "WON", "ganha": "WON",
          "lost": "LOST", "perdido": "LOST", "perdida": "LOST",
          "open": "OPEN", "aberto": "OPEN", "aberta": "OPEN"}


def preparar_dados(df: pd.DataFrame, locale="pt_BR", funil=None, *, base="Vendas") -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.rename(columns=ALIAS).copy()
    exigir_colunas(d, COLUNAS)
    n_original = len(d)
    # Compatibilidade com arquivos/argumentos anteriores, sem alterar a seleção.
    normalizar_base = lambda v: "Vendas" if chave(v) == "funil de vendas" else texto(v)
    d["Base"] = d.Base.map(normalizar_base)
    selecionada = normalizar_base(funil if funil is not None else base)
    d = d[d.Base.map(chave).eq(chave(selecionada))].copy()
    if d.empty:
        raise ErroDados("Nenhuma oportunidade na base informada.")
    for col in ["ID", "Período", "Produto"]:
        d[col] = d[col].map(texto)
        if d[col].eq("").any():
            raise ErroDados(f"{col} não pode estar vazio na base selecionada.")
    if d.ID.duplicated().any():
        raise ErroDados("IDs de oportunidade duplicados. Resolva o grão antes de analisar.")
    d["status"] = d.Status.map(chave).map(STATUS)
    if d.status.isna().any():
        raise ErroDados("Status desconhecido. Mapeie explicitamente para WON, LOST ou OPEN.")
    d["tipo_cliente"] = d[COLUNAS[-1]].map(chave).map(
        lambda v: "Recompra" if v in SIM else "Novo" if v in NAO else "Desconhecido")
    valores = []
    for linha, valor in enumerate(d.Valor, start=2):
        try:
            valores.append(moeda(valor, locale))
        except ErroDados as exc:
            raise ErroDados(f"Valor inválido no registro selecionado {linha}: {exc}") from exc
    d["valor_num"] = valores
    d["fase"] = d["Fase atual"].map(texto).replace("", "Não informado")
    d["motivo_perda"] = d["Motivo da perda"].map(texto).replace("", "Não informado")
    if "subproduto" not in d:
        d["subproduto"] = "Não informado"
    d["subproduto"] = d.subproduto.map(texto).replace("", "Não informado")
    d["ganho"] = d.status.eq("WON")
    d["perdido"] = d.status.eq("LOST")
    d["encerrado"] = d.status.isin(["WON", "LOST"])
    ciclos = ordem_natural(d.Período)
    d["Período"] = pd.Categorical(d.Período, categories=ciclos, ordered=True)
    controles = [
        ("registros_entrada", n_original), ("registros_na_base", len(d)),
        ("excluidos_outras_bases", n_original-len(d)),
        ("IDs_unicos", d.ID.nunique()),
        ("tipo_cliente_desconhecido", int(d.tipo_cliente.eq("Desconhecido").sum())),
        ("valores_ausentes", int(d.valor_num.isna().sum())),
        ("abertas", int(d.status.eq("OPEN").sum())),
        ("perdas_sem_motivo", int((d.perdido & d.motivo_perda.eq("Não informado")).sum())),
    ]
    if "Cliente_ID" in d:
        n_repetidos = d.Cliente_ID.map(texto).replace("", pd.NA).dropna().duplicated().sum()
        controles.append(("oportunidades_adicionais_mesmo_cliente", int(n_repetidos)))
    return d, pd.DataFrame(controles, columns=["controle", "quantidade"])


def soma_completa(s: pd.Series) -> float:
    """Ausências não são implicitamente tratadas como receita zero."""
    return np.nan if s.isna().any() else float(s.sum())


def tabela_taxas(d: pd.DataFrame, chaves=("Produto", "Período", "tipo_cliente")) -> pd.DataFrame:
    rows = []
    for key, g in d.groupby(list(chaves), observed=True, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        wins, losses = g[g.ganho], g[g.perdido]
        n, x = len(wins)+len(losses), len(wins)
        lo, hi = wilson(x, n)
        vg, vp = soma_completa(wins.valor_num), soma_completa(losses.valor_num)
        rows.append(dict(zip(chaves, key)) | {
            "oportunidades_total": len(g), "encerradas": n,
            "ganhos": x, "perdas": len(losses), "abertas": int(g.status.eq("OPEN").sum()),
            "share_abertas": float(g.status.eq("OPEN").mean()),
            "taxa_ganho_encerradas": x/n if n else np.nan,
            "ic95_wilson_inf": lo, "ic95_wilson_sup": hi,
            "valor_ganho": vg, "valor_oportunidades_perdidas": vp,
            "valores_ausentes_ganhos": int(wins.valor_num.isna().sum()),
            "valores_ausentes_perdas": int(losses.valor_num.isna().sum()),
            "valor_ganho_por_encerrada": vg/n if n else np.nan,
            "ticket_ganho": vg/x if x else np.nan,
        })
    return pd.DataFrame(rows)


def adicionar_fdr(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    if "p_valor" not in t:
        t["p_valor"] = pd.Series(dtype=float)
    t["p_ajustado_bh"] = ajustar_bh(t.p_valor)
    t["decisao_bh_5pct"] = t.p_ajustado_bh.map(conclusao)
    return t


def comparar_tipos(taxas: pd.DataFrame, inferir=False) -> pd.DataFrame:
    rows = []
    for (prod, ciclo), g in taxas.groupby(["Produto", "Período"], observed=True):
        g = g.set_index("tipo_cliente")
        if not {"Novo", "Recompra"} <= set(g.index):
            continue
        a, b = g.loc["Novo"], g.loc["Recompra"]
        n1, n2, x1, x2 = map(int, [a.encerradas, b.encerradas, a.ganhos, b.ganhos])
        delta = x1/n1-x2/n2 if min(n1, n2) else np.nan
        # Newcombe: combina intervalos de Wilson dos dois grupos independentes.
        lo = delta-np.sqrt((x1/n1-a.ic95_wilson_inf)**2 +
                          (b.ic95_wilson_sup-x2/n2)**2) if min(n1, n2) else np.nan
        hi = delta+np.sqrt((a.ic95_wilson_sup-x1/n1)**2 +
                          (x2/n2-b.ic95_wilson_inf)**2) if min(n1, n2) else np.nan
        teste = comparar_proporcoes(x1, n1, x2, n2) if inferir else {
            "teste": "Inferência desativada", "estatistica": np.nan, "p_valor": np.nan}
        rows.append({"Produto": prod, "Período": ciclo, "n_novo": n1, "n_recompra": n2,
                     "taxa_novo": x1/n1 if n1 else np.nan,
                     "taxa_recompra": x2/n2 if n2 else np.nan,
                     "diferenca_novo_menos_recompra_pp": 100*delta,
                     "ic95_diferenca_inf_pp": 100*max(-1., lo) if np.isfinite(lo) else np.nan,
                     "ic95_diferenca_sup_pp": 100*min(1., hi) if np.isfinite(hi) else np.nan,
                     **teste})
    return adicionar_fdr(pd.DataFrame(rows))


def tabelas_perdas(d: pd.DataFrame, inferir=False, seed=90210, reamostragens=9999):
    perdas = d[d.perdido].copy()
    agregadas, fases, par_q, par_v, testes = [], [], [], [], []
    # Mostra também fases de oportunidades ganhas: denominador = encerradas na fase final.
    for key, g in d[d.encerrado].groupby(["Produto", "Período", "tipo_cliente", "fase"], observed=True):
        fases.append(dict(zip(["Produto", "Período", "tipo_cliente", "fase_final"], key)) | {
            "encerradas_na_fase": len(g), "perdidas_na_fase": int(g.perdido.sum()),
            "fracao_perdida_na_fase_final": float(g.perdido.mean())})
    for key, g in perdas.groupby(["Produto", "Período", "tipo_cliente", "motivo_perda"], observed=True):
        agregadas.append(dict(zip(["Produto", "Período", "tipo_cliente", "motivo_perda"], key)) | {
            "quantidade": len(g), "valor_perdido": soma_completa(g.valor_num),
            "valores_ausentes": int(g.valor_num.isna().sum())})
    for (prod, ciclo), g in perdas.groupby(["Produto", "Período"], observed=True):
        q = pareto(g, "motivo_perda").assign(
            Produto=prod, Período=ciclo,
            pareto_financeiro_disponivel=bool(g.valor_num.notna().all()))
        par_q.append(q)
        # Não fornece Pareto financeiro parcial sem deixar a incompletude visível.
        if g.valor_num.notna().all():
            par_v.append(pareto(g, "motivo_perda", "valor_num").assign(Produto=prod, Período=ciclo))
        for dimensao in ["tipo_cliente", "fase"]:
            sub = g[g.tipo_cliente.isin(["Novo", "Recompra"])] if dimensao == "tipo_cliente" else g
            tab = pd.crosstab(sub[dimensao], sub.motivo_perda)
            resultado = associacao(tab, seed, reamostragens) if inferir else {
                "teste": "Inferência desativada", "p_valor": np.nan,
                "cramer_v": np.nan, "menor_esperado": np.nan}
            testes.append({"Produto": prod, "Período": ciclo, "comparacao": dimensao+" x motivo",
                           "n_perdas": len(sub), **resultado})
    juntar = lambda itens: pd.concat(itens, ignore_index=True) if itens else pd.DataFrame()
    return {"perdas_motivos": pd.DataFrame(agregadas), "fase_final": pd.DataFrame(fases),
            "pareto_quantidade": juntar(par_q), "pareto_valor": juntar(par_v),
            "associacao_motivos": adicionar_fdr(pd.DataFrame(testes))}


def testes_valores(d: pd.DataFrame, inferir=False) -> pd.DataFrame:
    rows = []
    for (prod, ciclo, tipo), g in d[d.perdido].groupby(["Produto", "Período", "tipo_cliente"], observed=True):
        for dimensao in ["fase", "motivo_perda"]:
            grupos = [v.valor_num.dropna().to_numpy() for _, v in g.groupby(dimensao, observed=True)]
            # Não descarta silenciosamente categorias pequenas de uma comparação.
            valido = len(grupos) >= 2 and min(map(len, grupos)) >= 5
            p, h, efeito = np.nan, np.nan, np.nan
            estado = "Inferência desativada" if not inferir else "Grupos insuficientes (mínimo 5 valores/grupo)"
            if inferir and valido:
                todos = np.concatenate(grupos)
                if np.ptp(todos) == 0:
                    h, p = 0., 1.
                else:
                    h, p = stats.kruskal(*grupos)
                k, n = len(grupos), len(todos)
                efeito = max(0., (h-k+1)/(n-k)) if n > k else np.nan
                estado = "Kruskal-Wallis (distribuições; sem interpretação causal)"
            rows.append({"Produto": prod, "Período": ciclo, "tipo_cliente": tipo,
                         "comparacao": "valor x "+dimensao, "teste": estado,
                         "grupos": len(grupos), "H": h, "p_valor": p,
                         "epsilon_quadrado": efeito})
    return adicionar_fdr(pd.DataFrame(rows))


def tendencias(taxas: pd.DataFrame, ciclos: list[str]) -> pd.DataFrame:
    rows = []
    mapa = {c: i for i, c in enumerate(ciclos)}
    for (prod, tipo), g in taxas.groupby(["Produto", "tipo_cliente"], observed=True):
        g = g[g.encerradas > 0].copy()
        g["x"] = g.Período.astype(str).map(mapa)
        g = g.sort_values("x")
        if len(g) < 3:
            continue
        coef = np.polyfit(g.x, g.taxa_ganho_encerradas, 1, w=np.sqrt(g.encerradas))[0]
        rows.append({"Produto": prod, "tipo_cliente": tipo, "periodos_observados": len(g),
                     "inclinacao_descritiva_pp_por_periodo": 100*coef,
                     "variacao_primeiro_ultimo_pp": 100*(g.taxa_ganho_encerradas.iloc[-1]-g.taxa_ganho_encerradas.iloc[0])})
    return pd.DataFrame(rows)


def panorama(d: pd.DataFrame, motivo_alvo: str) -> pd.DataFrame:
    ultimo = d.Período.cat.categories[-1]
    rows = []
    for prod, g in d[d.Período.eq(ultimo)].groupby("Produto", observed=True):
        wins = g[g.ganho]
        losses = g[g.perdido]
        completo = wins.valor_num.notna().all() and not wins.tipo_cliente.eq("Desconhecido").any()
        total = wins.valor_num.sum() if completo else np.nan
        share = wins.loc[wins.tipo_cliente.eq("Recompra"), "valor_num"].sum()/total if total > 0 else np.nan
        rows.append({"Produto": prod, "Período": str(ultimo),
                     "taxa_ganho_encerradas": float(g.ganho.sum()/g.encerrado.sum()) if g.encerrado.any() else np.nan,
                     "participacao_recompra_valor_ganho": share,
                     "participacao_motivo_alvo_nas_perdas": float(losses.motivo_perda.map(chave).eq(chave(motivo_alvo)).mean()) if len(losses) else np.nan,
                     "perdas_sem_motivo": int(losses.motivo_perda.eq("Não informado").sum())})
    return pd.DataFrame(rows)


def executar(entrada=DEMO, saida=ROOT/"outputs/conversao", locale="pt_BR",
             funil=None, inferir=False, seed=90210,
             reamostragens=9999, motivo_alvo="Preço acima do orçamento", base="Vendas") -> dict:
    entrada, saida = Path(entrada), Path(saida)
    d, controles = preparar_dados(ler_tabela(entrada), locale, funil, base=base)
    if inferir and "Cliente_ID" in d:
        ids = d.Cliente_ID.map(texto).replace("", pd.NA).dropna()
        if ids.duplicated().any():
            raise ErroDados("Clientes repetidos: a inferência independente foi bloqueada; use análise descritiva ou modelo por cliente.")
    taxas = tabela_taxas(d)
    total = tabela_taxas(d, ("Período",))
    mix = d.groupby(["Período", "Produto"], observed=True).size().rename("oportunidades").reset_index()
    mix["participacao_no_periodo"] = mix.oportunidades / mix.groupby("Período", observed=True).oportunidades.transform("sum")
    rankings = tabela_taxas(d, ("Período", "tipo_cliente", "subproduto"))
    tabelas = {"qualidade": controles, "resumo_periodo": total, "mix_produtos": mix,
               "taxas_produto": taxas, "novo_vs_recompra": comparar_tipos(taxas, inferir),
               **tabelas_perdas(d, inferir, seed, reamostragens),
               "valores_testes": testes_valores(d, inferir), "valores_subproduto": rankings,
               "tendencias_descritivas": tendencias(taxas, list(d.Período.cat.categories)),
               "panorama_ultimo_periodo": panorama(d, motivo_alvo)}
    saida.mkdir(parents=True, exist_ok=True)
    exportar_excel(saida/"conversao_resultados.xlsx", tabelas)
    for prod, g in taxas.groupby("Produto", observed=True):
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ciclos = list(d.Período.cat.categories)
        for tipo, h in g.groupby("tipo_cliente", observed=True):
            h = h.set_index("Período").reindex(ciclos)
            y = h.taxa_ganho_encerradas.to_numpy(dtype=float)
            erro = np.vstack([y-h.ic95_wilson_inf, h.ic95_wilson_sup-y])*100
            validos = np.isfinite(y) & np.isfinite(erro).all(axis=0)
            if validos.any():
                xx = np.arange(len(ciclos))[validos]
                ax.errorbar(xx, 100*y[validos], yerr=np.maximum(erro[:, validos], 0),
                            marker="o", capsize=3, label=tipo)
        ax.set(xticks=range(len(ciclos)), xticklabels=ciclos, ylim=(-2, 102),
               ylabel="Taxa de ganho entre encerradas (%)",
               title=f"{prod} — taxas e intervalos de Wilson de 95%")
        if ax.has_data():
            ax.legend()
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(saida/f"taxas_{nome_seguro(prod)}.png", dpi=160); plt.close(fig)
    pq = tabelas["pareto_quantidade"]
    if not pq.empty:
        ultimo = str(d.Período.cat.categories[-1])
        for prod, g in pq[pq.Período.astype(str).eq(ultimo)].groupby("Produto", observed=True):
            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(g))
            ax.bar(x, g.medida, color=np.where(g.selecionado_80, "#2878b5", "#b5bec7"))
            ax.set(xticks=x, xticklabels=[fill(str(v), 18) for v in g.motivo_perda],
                   ylabel="Oportunidades perdidas",
                   title=f"{prod} — Pareto de motivos, {ultimo}")
            acumulado = ax.twinx()
            acumulado.plot(x, 100*g.participacao_acumulada, color="#c75d24", marker="o")
            acumulado.axhline(80, color="gray", linestyle="--")
            acumulado.set(ylim=(0, 105), ylabel="Participação acumulada (%)")
            fig.tight_layout()
            fig.savefig(saida/f"pareto_{nome_seguro(prod)}.png", dpi=160); plt.close(fig)
    dados_demo = entrada.resolve() == DEMO.resolve()
    metadata = {"estudo": "conversao", "dados": "sintéticos de demonstração" if dados_demo else "fornecidos pelo usuário; origem não verificada",
                "registros": len(d), "inferir": inferir, "seed": seed,
                "reamostragens_monte_carlo": reamostragens,
                "familias_bh": ["Novo vs Recompra: todos os produtos/períodos",
                                 "Associação entre motivos: todos os produtos/períodos/dimensões",
                                 "Valores perdidos: todos os produtos/períodos/tipos/dimensões"],
                "limitacoes": ["Win rate de encerradas; não é conversão de uma coorte madura por data de criação.",
                                "ICs binomiais pressupõem independência; não representam erro de cadastro ou viés de seleção.",
                                "Inferência opcional pressupõe oportunidades independentes, amostragem/modelo apropriado e categorias comparáveis.",
                                "Cliente ativo não comprova recompra do mesmo produto.",
                                "Fase final não mede transição de funil; tendências são descritivas; não há score preditivo.",
                                "A inclinação usa a posição ordinal dos períodos observados e não equivale a uma taxa por ano quando há lacunas.",
                                "Valores financeiros ficam ausentes quando a agregação pertinente contém valores desconhecidos."]}
    (saida/"metadados.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = ["# Conversão por produto", "", f"Dados: {metadata['dados']}.", "",
              f"Foram analisadas {len(d):,} oportunidades, das quais {int(d.encerrado.sum()):,} encerradas.",
              "A taxa usa WON / (WON + LOST); abertas são reportadas separadamente.", "",
              "## Limitações", ""] + ["- "+s for s in metadata["limitacoes"]]
    (saida/"LEIA_RESULTADOS.md").write_text("\n".join(linhas)+"\n", encoding="utf-8")
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entrada", type=Path, default=DEMO)
    p.add_argument("--saida", type=Path, default=ROOT/"outputs/conversao")
    p.add_argument("--locale", choices=["pt_BR", "en_US"], default="pt_BR")
    p.add_argument("--base", "--funil", dest="base", default="Vendas",
                   help="Base selecionada; --funil permanece como alias legado.")
    p.add_argument("--motivo-alvo", default="Preço acima do orçamento")
    p.add_argument("--inferir", action="store_true", help="Assume independência das oportunidades e condições inferenciais descritas no README.")
    p.add_argument("--seed", type=int, default=90210)
    p.add_argument("--reamostragens", type=int, default=9999)
    args = p.parse_args()
    if args.reamostragens < 999:
        p.error("Use pelo menos 999 reamostragens.")
    try:
        result = executar(**vars(args))
    except ErroDados as exc:
        p.exit(2, f"Erro de dados: {exc}\n")
    print(f"Concluído: {result['registros']} oportunidades. Resultados em {args.saida}")


if __name__ == "__main__":
    main()
