import numpy as np
import pandas as pd
import pytest

from conversao_produto import preparar_dados, tabela_taxas, comparar_tipos, executar
from utilitarios import ErroDados, moeda, wilson, comparar_proporcoes, pareto
from scripts.gerar_dados_sinteticos import gerar


def test_gerador_reproduz_e_nao_usa_dados_reais():
    a = gerar(2026)
    b = gerar(2026)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 1650
    assert a["Produto"].nunique() == 3


def test_taxa_exclui_abertas():
    d, controles = preparar_dados(gerar())
    t = tabela_taxas(d)
    assert (t["encerradas"] == t["ganhos"] + t["perdas"]).all()
    assert (t["oportunidades_total"] == t["encerradas"] + t["abertas"]).all()
    assert t["taxa_ganho_encerradas"].between(0, 1).all()


def test_rejeita_identificadores_duplicados():
    df = gerar().head(4).copy()
    df.loc[df.index[1], "ID"] = df.loc[df.index[0], "ID"]
    with pytest.raises(ErroDados, match="duplicados"):
        preparar_dados(df)


def test_valores_desconhecidos_nao_viram_zero():
    df = gerar().head(25).copy()
    df.loc[df.index[0], "Valor"] = np.nan
    dados, _ = preparar_dados(df)
    assert dados["valor_num"].isna().sum() == 1
    assert np.isnan(moeda(None))
    with pytest.raises(ErroDados):
        moeda("3,123.45", "pt_BR")


def test_sem_encerradas_nao_quebra():
    df = gerar().head(5).copy()
    df["Status"] = "OPEN"
    dados, _ = preparar_dados(df)
    taxas = tabela_taxas(dados)
    assert (taxas["encerradas"] == 0).all()
    assert taxas["taxa_ganho_encerradas"].isna().all()
    assert comparar_tipos(taxas).empty


def test_intervalo_wilson():
    lo, hi = wilson(5, 10)
    assert 0 <= lo < 0.5 < hi <= 1


def test_proporcoes_extremos():
    resultado = comparar_proporcoes(5, 5, 5, 5)
    assert resultado["p_valor"] == 1


def test_pareto_seleciona_ate_o_limite():
    df = pd.DataFrame({"motivo": ["a"]*8+["b"]*2})
    t = pareto(df, "motivo")
    assert t.loc[0, "selecionado_80"]
    assert not t.loc[1, "selecionado_80"]


def test_end_to_end(tmp_path):
    entrada = tmp_path / "demo.csv"
    gerar().to_csv(entrada, index=False)
    saida = tmp_path / "resultado"
    meta = executar(entrada=entrada, saida=saida, inferir=False)
    assert meta["registros"] == 1650
    assert (saida/"conversao_resultados.xlsx").is_file()
    assert (saida/"metadados.json").is_file()
    assert len(list(saida.glob("taxas_*.png"))) == 3
