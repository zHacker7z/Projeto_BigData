"""
Análise das leituras da estação meteorológica (DHT + BMP + sensor de chuva).

Perguntas respondidas, para cada dia presente na base:
  1 - Qual foi o período mais úmido do dia?
  2 - Qual foi o horário mais quente?
  3 - Qual foi a probabilidade de chuva nesse dia?

Uso:
    py analise_clima.py [caminho_do_csv]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ARQUIVO_PADRAO = Path(__file__).with_name("leituras_202611152221.csv")

# Sensor de chuva analógico (FC-37 / YL-83) lido por ADC de 12 bits (ESP32):
# 4095 = placa totalmente seca, perto de 0 = placa encharcada.
ADC_MAX = 4095
# Acima de 50% de molhamento da placa a leitura é considerada "chovendo".
LIMIAR_CHUVA_PCT = 50

PERIODOS = {
    "Madrugada (00h-06h)": range(0, 6),
    "Manhã (06h-12h)": range(6, 12),
    "Tarde (12h-18h)": range(12, 18),
    "Noite (18h-24h)": range(18, 24),
}


def carregar_dados(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, parse_dates=["data_hora"])

    # Limpeza: remove linhas duplicadas e leituras impossíveis do ADC
    df = df.drop_duplicates()
    df = df[df["chuva_bruta"].between(0, ADC_MAX)]
    df = df.sort_values("data_hora").reset_index(drop=True)

    df["dia"] = df["data_hora"].dt.date
    df["hora"] = df["data_hora"].dt.hour
    df["periodo"] = df["hora"].map(
        {h: nome for nome, horas in PERIODOS.items() for h in horas}
    )

    # Converte a leitura bruta em % de molhamento da placa (0 = seco, 100 = encharcado)
    df["chuva_pct"] = ((ADC_MAX - df["chuva_bruta"]) / ADC_MAX * 100).clip(0, 100)
    df["chovendo"] = df["chuva_pct"] >= LIMIAR_CHUVA_PCT
    return df


def periodo_mais_umido(dia: pd.DataFrame) -> pd.Series:
    return dia.groupby("periodo")["dht_umidade"].mean().sort_values(ascending=False)


def horario_mais_quente(dia: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    por_hora = dia.groupby("hora")["temperatura_media"].mean()
    leitura_max = dia.loc[dia["temperatura_media"].idxmax()]
    return por_hora, leitura_max


def probabilidade_chuva(dia: pd.DataFrame) -> tuple[float, float, pd.Series]:
    # Probabilidade = fração das leituras do dia em que o sensor indicou chuva
    prob_dia = dia["chovendo"].mean() * 100
    prob_por_periodo = dia.groupby("periodo")["chovendo"].mean() * 100
    molhamento_medio = dia["chuva_pct"].mean()
    return prob_dia, molhamento_medio, prob_por_periodo


def relatorio(df: pd.DataFrame) -> None:
    print(f"Leituras válidas: {len(df):,}".replace(",", "."))
    print(f"Intervalo: {df['data_hora'].min()}  ->  {df['data_hora'].max()}")

    for data, dia in df.groupby("dia"):
        horas_cobertas = dia["hora"].nunique()
        print("\n" + "=" * 64)
        leituras = f"{len(dia):,}".replace(",", ".")
        print(f"DIA {data:%d/%m/%Y}  ({leituras} leituras, {horas_cobertas}h de dados)")
        print("=" * 64)

        # 1 - Período mais úmido
        umidade = periodo_mais_umido(dia)
        print("\n1) Período mais úmido do dia")
        for periodo, valor in umidade.items():
            print(f"   {periodo:<22} {valor:6.2f} %")
        print(f"   >> Mais úmido: {umidade.index[0]} ({umidade.iloc[0]:.2f} % de umidade média)")

        # 2 - Horário mais quente
        por_hora, leitura_max = horario_mais_quente(dia)
        hora_quente = por_hora.idxmax()
        print("\n2) Horário mais quente")
        print(f"   >> Faixa horária: {hora_quente:02d}h-{hora_quente + 1:02d}h "
              f"(média de {por_hora.max():.2f} °C)")
        print(f"   >> Pico registrado: {leitura_max['data_hora']:%H:%M:%S} "
              f"com {leitura_max['temperatura_media']:.2f} °C")

        # 3 - Probabilidade de chuva
        prob_dia, molhamento, prob_periodo = probabilidade_chuva(dia)
        print("\n3) Probabilidade de chuva")
        for periodo, valor in prob_periodo.reindex(PERIODOS).dropna().items():
            print(f"   {periodo:<22} {valor:6.1f} %")
        print(f"   >> Probabilidade de chuva no dia: {prob_dia:.1f} %")
        print(f"      (molhamento médio do sensor: {molhamento:.1f} %)")


def main() -> None:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else ARQUIVO_PADRAO
    df = carregar_dados(caminho)
    pd.set_option("display.width", 120)
    relatorio(df)


if __name__ == "__main__":
    main()
