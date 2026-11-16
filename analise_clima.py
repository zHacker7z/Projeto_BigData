"""
Análise das leituras da estação meteorológica (Raspberry Pi Pico W + DHT11 + BMP280 +
sensor de chuva).

Perguntas respondidas, para cada dia presente na base:
  1 - Qual foi o período mais úmido do dia?
  2 - Qual foi o horário mais quente?
  3 - Qual foi a probabilidade de chuva nesse dia?

Uso:
    py analise_clima.py [caminho_do_csv]
"""

import sys
from pathlib import Path

import pandas as pd

ARQUIVO_PADRAO = Path(__file__).with_name("leituras_202611152221.csv")

# Faixas de operação de cada sensor, conforme a especificação do projeto.
# Leituras fora dessas faixas não são fisicamente possíveis para o sensor.
FAIXAS_SENSORES = {
    "dht_umidade": (20, 95),          # DHT11, %
    "dht_temp": (0, 50),              # DHT11, °C
    "bmp_temp": (-40, 85),            # BMP280, °C
    "bmp_pressao": (30_000, 110_000), # BMP280, Pa
    "chuva_bruta": (0, 65_535),       # ADC do Pico (GP28), read_u16()
}
COLUNAS_ANALISADAS = ["dht_umidade", "dht_temp", "bmp_temp", "chuva_bruta"]

# Sensor de chuva no ADC2 (GP28): 0 V (~300 contagens, ruído do ADC) = placa seca,
# 3,3 V (65535) = placa submersa.
CHUVA_SECO = 300
CHUVA_SUBMERSO = 65_535
# O ruído do ADC com a placa seca fica entre ~250 e ~470 contagens na base. Acima de
# 500 a placa tem água, e a leitura é considerada "chovendo".
LIMIAR_AGUA = 500

PERIODOS = {
    "Madrugada (00h-06h)": range(0, 6),
    "Manhã (06h-12h)": range(6, 12),
    "Tarde (12h-18h)": range(12, 18),
    "Noite (18h-24h)": range(18, 24),
}


def validar_faixas(df: pd.DataFrame) -> pd.DataFrame:
    """Conta as leituras fora da faixa de cada sensor e remove as das colunas usadas."""
    print("\nValidação das faixas dos sensores:")
    fora_total = pd.Series(False, index=df.index)
    for coluna, (minimo, maximo) in FAIXAS_SENSORES.items():
        fora = ~df[coluna].between(minimo, maximo)
        situacao = "usada" if coluna in COLUNAS_ANALISADAS else "desconsiderada"
        print(f"   {coluna:<12} faixa {minimo:>7,} a {maximo:>7,}  ->  "
              f"{fora.mean() * 100:5.1f} % fora ({situacao})".replace(",", "."))
        if coluna in COLUNAS_ANALISADAS:
            fora_total |= fora
    return df[~fora_total]


def carregar_dados(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, parse_dates=["data_hora"])

    # Limpeza: remove linhas duplicadas e leituras fora da faixa dos sensores
    df = df.drop_duplicates()
    df = validar_faixas(df)
    df = df.sort_values("data_hora").reset_index(drop=True)

    df["dia"] = df["data_hora"].dt.date
    df["hora"] = df["data_hora"].dt.hour
    df["periodo"] = df["hora"].map(
        {h: nome for nome, horas in PERIODOS.items() for h in horas}
    )

    # Intensidade = % da escala do sensor (0 = seco, 100 = submerso)
    df["chuva_pct"] = ((df["chuva_bruta"] - CHUVA_SECO)
                       / (CHUVA_SUBMERSO - CHUVA_SECO) * 100).clip(0, 100)
    df["chovendo"] = df["chuva_bruta"] > LIMIAR_AGUA
    return df


def periodo_mais_umido(dia: pd.DataFrame) -> pd.Series:
    return dia.groupby("periodo")["dht_umidade"].mean().sort_values(ascending=False)


def horario_mais_quente(dia: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    por_hora = dia.groupby("hora")["temperatura_media"].mean()
    leitura_max = dia.loc[dia["temperatura_media"].idxmax()]
    return por_hora, leitura_max


def probabilidade_chuva(dia: pd.DataFrame) -> tuple[float, pd.Series, pd.Series]:
    # Probabilidade = fração das leituras do dia em que havia água na placa
    prob_dia = dia["chovendo"].mean() * 100
    prob_por_periodo = dia.groupby("periodo")["chovendo"].mean() * 100
    leitura_max = dia.loc[dia["chuva_bruta"].idxmax()]
    return prob_dia, prob_por_periodo, leitura_max


def relatorio(df: pd.DataFrame) -> None:
    print(f"\nLeituras válidas: {len(df):,}".replace(",", "."))
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
        prob_dia, prob_periodo, chuva_max = probabilidade_chuva(dia)
        com_agua = dia.loc[dia["chovendo"], "chuva_pct"]
        print("\n3) Probabilidade de chuva (água detectada na placa)")
        for periodo, valor in prob_periodo.reindex(PERIODOS).dropna().items():
            print(f"   {periodo:<22} {valor:6.1f} %")
        print(f"   >> Probabilidade de chuva no dia: {prob_dia:.1f} %")
        if not com_agua.empty:
            print(f"      (intensidade mediana com água: {com_agua.median():.1f} % da escala; "
                  f"pico de {chuva_max['chuva_pct']:.1f} % às {chuva_max['data_hora']:%H:%M:%S})")


def main() -> None:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else ARQUIVO_PADRAO
    df = carregar_dados(caminho)
    relatorio(df)


if __name__ == "__main__":
    main()
