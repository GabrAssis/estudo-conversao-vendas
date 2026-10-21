import pandas as pd
import pytest

from conversao_produto import preparar_dados, tabela_taxas
from scripts.gerar_dados_sinteticos import gerar
from utilitarios import ErroDados


def atual():
    return gerar().rename(columns={
        "Funil": "Base", "Ciclo": "Período",
        "Ja e cliente? (cliente ativo 2 anos)": "Cliente ativo?",
    }).replace({"Base": {"Funil de Vendas": "Vendas"}})


def test_cabecalhos_atuais_e_legados_preservam_taxas():
    novo, q1 = preparar_dados(atual())
    antigo = atual().rename(columns={
        "Base": "Funil", "Período": "Ciclo",
        "Cliente ativo?": "Já é cliente? (cliente ativo 2 anos)",
    }).replace({"Funil": {"Vendas": "Funil de Vendas"}})
    legado, q2 = preparar_dados(antigo, funil="Funil de Vendas")
    pd.testing.assert_frame_equal(tabela_taxas(novo), tabela_taxas(legado))
    pd.testing.assert_frame_equal(q1, q2)
    assert len(novo) == 1650
    assert "Período" in tabela_taxas(novo)
    assert set(novo.Base) == {"Vendas"}


@pytest.mark.parametrize("legado,novo", [
    ("Ciclo", "Período"), ("Funil", "Base"),
    ("Ja e cliente? (cliente ativo 2 anos)", "Cliente ativo?"),
])
def test_rejeita_colunas_ambiguas(legado, novo):
    df = atual()
    df[legado] = df[novo]
    with pytest.raises(ErroDados, match="duplicad"):
        preparar_dados(df)


def test_filtro_base_preserva_exclusoes():
    df = atual()
    df.loc[0, "Base"] = "Atendimento"
    d, q = preparar_dados(df, base="Vendas")
    assert len(d) == 1649
    assert q.set_index("controle").loc["excluidos_outras_bases", "quantidade"] == 1
