"""Gera oportunidades de CRM 100% fictícias, sem acesso a dados corporativos.

A seed é fixa para reprodutibilidade. Probabilidades, valores e motivos foram
inventados para a demonstração; não estimam nem reproduzem métricas reais.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

PRODUTOS = ["Produto A", "Produto B", "Produto C"]
CICLOS = [f"Ciclo {i:02d}" for i in range(1, 6)]
MOTIVOS = ["Preço acima do orçamento", "Prazo incompatível",
           "Prioridade alterada", "Concorrência", "Escopo inadequado"]
FASES = ["Qualificação", "Diagnóstico", "Proposta", "Negociação"]


def gerar(seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    registros = []
    contador = 0
    for ci, ciclo in enumerate(CICLOS):
        for pi, produto in enumerate(PRODUTOS):
            for tipo in ["Novo", "Recompra"]:
                for _ in range(55):
                    contador += 1
                    recompra = tipo == "Recompra"
                    # Valores e probabilidades aleatórios e inventados.
                    chance = min(0.80, max(0.20, 0.39 + 0.055*pi - 0.020*ci + (0.12 if recompra else 0)))
                    sorteio = rng.random()
                    status = "OPEN" if sorteio < 0.09 else ("WON" if sorteio < 0.09 + 0.91*chance else "LOST")
                    motivo = str(rng.choice(MOTIVOS, p=[.30, .18, .20, .20, .12])) if status == "LOST" else ""
                    fase = str(rng.choice(FASES, p=[.12, .25, .41, .22]))
                    valor = round(float(rng.lognormal(mean=9.05+pi*.12, sigma=.52)), 2)
                    registros.append({
                        "ID": f"OP-{contador:06d}",
                        "Base": "Vendas",
                        "Período": ciclo,
                        "Produto": produto,
                        "Fase atual": fase,
                        "Motivo da perda": motivo,
                        "Valor": valor,
                        "Status": status,
                        "Cliente ativo?": "Sim" if recompra else "Não",
                        "subproduto": f"Linha {pi+1}-{'A' if rng.random()<.5 else 'B'}",
                    })
    return pd.DataFrame(registros)


if __name__ == "__main__":
    destino = Path(__file__).resolve().parents[1] / "data/synthetic/conversao_sintetica.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    gerados = gerar()
    gerados.to_csv(destino, index=False, encoding="utf-8-sig", lineterminator="\n")
    print(f"Base totalmente sintética: {len(gerados)} linhas em {destino}")
