"""Validação, estatística e exportação compartilhadas pelos dois estudos."""
from __future__ import annotations

import hashlib
import math
import numbers
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


class ErroDados(ValueError):
    """Entrada incompatível com o contrato de dados do estudo."""


def texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return " ".join(str(valor).strip().split())


def chave(valor) -> str:
    s = unicodedata.normalize("NFKD", texto(valor).casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def ordem_natural(valores) -> list[str]:
    def partes(s):
        return tuple((0, int(x)) if x.isdigit() else (1, x.casefold())
                     for x in re.split(r"(\d+)", s))
    return sorted(set(valores), key=partes)


def moeda(valor, locale: str = "pt_BR") -> float:
    """Preserva números nativos; textos seguem o locale, sem adivinhação.

    pt_BR: '1.234,56', '1234,56', '1234'. en_US: '1,234.56', '1234.56'.
    Texto '1234.56' em pt_BR é rejeitado como formato incompatível.
    Ausência permanece NaN; texto inválido nunca vira zero silenciosamente.
    """
    if locale not in {"pt_BR", "en_US"}:
        raise ErroDados("Locale monetário deve ser pt_BR ou en_US.")
    if pd.isna(valor) or texto(valor) == "":
        return np.nan
    if isinstance(valor, (bool, np.bool_)):
        raise ErroDados("Booleano não é valor monetário.")
    if isinstance(valor, numbers.Real):
        out = float(valor)
    else:
        s = texto(valor).replace("R$", "").replace("$", "").strip()
        if locale == "pt_BR":
            padrao = r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?"
        else:
            padrao = r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?"
        if not re.fullmatch(padrao, s):
            raise ErroDados(f"Valor monetário incompatível com {locale}.")
        out = float(s.replace(".", "").replace(",", ".") if locale == "pt_BR"
                    else s.replace(",", ""))
    if not math.isfinite(out) or out < 0:
        raise ErroDados("Valor monetário deve ser finito e não negativo.")
    return out


def exigir_colunas(df: pd.DataFrame, colunas):
    if not df.columns.is_unique:
        raise ErroDados("Há nomes de colunas duplicados.")
    faltam = set(colunas) - set(df.columns)
    if faltam:
        raise ErroDados("Colunas obrigatórias ausentes: " + ", ".join(sorted(faltam)))


def ler_tabela(caminho: Path) -> pd.DataFrame:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroDados(f"Arquivo não encontrado: {caminho.name}")
    if caminho.suffix.lower() == ".xlsx":
        return pd.read_excel(caminho)
    if caminho.suffix.lower() == ".csv":
        return pd.read_csv(caminho, sep=None, engine="python", encoding="utf-8-sig")
    raise ErroDados("Use um arquivo .xlsx ou .csv (UTF-8).")


def wilson(ganhos: int, total: int, confianca: float = .95) -> tuple[float, float]:
    if total == 0:
        return np.nan, np.nan
    if not 0 <= ganhos <= total:
        raise ErroDados("Numerador fora do intervalo [0, denominador].")
    z = stats.norm.ppf((1 + confianca) / 2)
    p = ganhos / total
    centro = p + z*z/(2*total)
    raio = z*np.sqrt(p*(1-p)/total + z*z/(4*total*total))
    div = 1 + z*z/total
    return max(0., (centro-raio)/div), min(1., (centro+raio)/div)


def ajustar_bh(valores) -> np.ndarray:
    p = np.asarray(valores, dtype=float)
    if ((p[np.isfinite(p)] < 0) | (p[np.isfinite(p)] > 1)).any():
        raise ErroDados("P-valor fora de [0, 1].")
    out = np.full(p.shape, np.nan)
    validos = np.isfinite(p)
    if validos.any():
        out[validos] = stats.false_discovery_control(p[validos], method="bh")
    return out


def conclusao(p, alpha=.05) -> str:
    if not np.isfinite(p):
        return "Não calculado / não aplicável"
    return "Rejeita H0 (exploratório)" if p < alpha else "Não rejeita H0"


def comparar_proporcoes(x1: int, n1: int, x2: int, n2: int) -> dict:
    """Z quando todas as frequências esperadas >= 5; Fisher nas demais 2x2."""
    if not (0 <= x1 <= n1 and 0 <= x2 <= n2):
        raise ErroDados("Contagens binomiais inválidas.")
    if min(n1, n2) == 0:
        return {"teste": "Não aplicável", "estatistica": np.nan, "p_valor": np.nan}
    tab = np.array([[x1, n1-x1], [x2, n2-x2]])
    # Distribuição degenerada: os dois grupos têm exatamente o mesmo desfecho.
    # expected_freq falha quando uma coluna inteira é zero; Fisher aqui dá p=1.
    if tab[:, 0].sum() == 0 or tab[:, 1].sum() == 0:
        return {"teste": "Fisher exato bilateral (degenerado)",
                "estatistica": np.nan, "p_valor": 1.0}
    esperado = stats.contingency.expected_freq(tab)
    if (esperado >= 5).all():
        pool = (x1+x2)/(n1+n2)
        se = np.sqrt(pool*(1-pool)*(1/n1+1/n2))
        z = (x1/n1-x2/n2)/se
        return {"teste": "Z duas proporções", "estatistica": float(z),
                "p_valor": float(2*stats.norm.sf(abs(z)))}
    p = stats.fisher_exact(tab, alternative="two-sided").pvalue
    return {"teste": "Fisher exato bilateral", "estatistica": np.nan,
            "p_valor": float(p)}


def associacao(tab: pd.DataFrame, seed=90210, reamostragens=9999) -> dict:
    """Não reagrupa motivos com base no resultado; Monte Carlo se RxC esparsa."""
    a = np.asarray(tab, dtype=int)
    if a.ndim != 2 or (a < 0).any():
        raise ErroDados("Tabela de contingência inválida.")
    a = a[a.sum(axis=1) > 0]
    a = a[:, a.sum(axis=0) > 0]
    vazio = {"teste": "Não aplicável", "p_valor": np.nan,
             "cramer_v": np.nan, "menor_esperado": np.nan}
    if min(a.shape, default=0) < 2:
        return vazio
    exp = stats.contingency.expected_freq(a)
    chi = stats.chi2_contingency(a, correction=False).statistic
    v = float(np.sqrt(chi/(a.sum()*min(a.shape[0]-1, a.shape[1]-1))))
    if (exp >= 5).all():
        p = stats.chi2_contingency(a, correction=False).pvalue
        teste = "Qui-quadrado Pearson"
    elif a.shape == (2, 2):
        p = stats.fisher_exact(a, alternative="two-sided").pvalue
        teste = "Fisher exato bilateral"
    else:
        metodo = stats.MonteCarloMethod(n_resamples=reamostragens,
                                       rng=np.random.default_rng(seed))
        p = stats.chi2_contingency(a, correction=False, method=metodo).pvalue
        teste = f"Qui-quadrado Monte Carlo ({reamostragens})"
    return {"teste": teste, "p_valor": float(p), "cramer_v": v,
            "menor_esperado": float(exp.min())}


def pareto(df: pd.DataFrame, categoria: str, peso: str | None = None,
           limite=.8) -> pd.DataFrame:
    if not 0 < limite <= 1:
        raise ErroDados("Limite de Pareto deve estar em (0, 1].")
    g = df.groupby(categoria, dropna=False, observed=True)
    t = (g.size() if peso is None else g[peso].sum(min_count=1)).rename("medida").reset_index()
    if not t.empty and (t.medida.dropna() < 0).any():
        raise ErroDados("Pareto exige pesos não negativos.")
    t = t.sort_values(["medida", categoria], ascending=[False, True],
                      kind="stable").reset_index(drop=True)
    total = t.medida.sum(min_count=1)
    t["participacao"] = t.medida/total if total > 0 else np.nan
    t["participacao_acumulada"] = t.participacao.cumsum()
    t["selecionado_80"] = False
    if total > 0:
        # Inclui a categoria que atinge ou ultrapassa o limiar.
        n = int(np.searchsorted(t.participacao_acumulada.to_numpy(), limite,
                                side="left")) + 1
        t.loc[:min(n, len(t))-1, "selecionado_80"] = True
    return t


def nome_seguro(valor: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", chave(valor)).strip("_")[:45] or "grupo"
    return base + "_" + hashlib.sha256(str(valor).encode()).hexdigest()[:8]


def exportar_excel(caminho: Path, tabelas: dict[str, pd.DataFrame]):
    """Sem dados linha a linha; neutraliza fórmulas em rótulos externos."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        for nome, df in tabelas.items():
            out = df.copy()
            for col in out.select_dtypes(include=["category"]).columns:
                out[col] = out[col].astype("string")
            for col in out.select_dtypes(include=["object", "string"]).columns:
                out[col] = out[col].map(
                    lambda v: "'"+v if isinstance(v, str) and
                    v.lstrip().startswith(("=", "+", "-", "@")) else v)
            out.to_excel(writer, sheet_name=nome, index=False)
            ws = writer.sheets[nome]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                ws.column_dimensions[cell.column_letter].width = min(48, max(15, len(str(cell.value))+2))
