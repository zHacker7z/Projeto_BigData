# Estação Meteorológica com Raspberry Pi Pico W — Análise de Dados

Projeto acadêmico de **Big Data / Análise de Dados**. Uma estação meteorológica montada com
Raspberry Pi Pico W coletou leituras de temperatura, umidade, pressão e chuva durante alguns
dias. Os dados foram exportados para CSV e analisados em Python com a biblioteca **pandas**.

> **Instituição:** `ESTACIO` · **Disciplina:** `<Tópicos de Bigdata em Python>` ·
> **Integrantes:** `<Gustavo Hacker, Kaique Barbosa, Flavio Lima>` · **Professor(a):** `<Vinicius>`

---

## Objetivo

Responder, para cada dia monitorado, três perguntas:

1. **Qual foi o período mais úmido do dia?**
2. **Qual foi o horário mais quente?**
3. **Qual foi a probabilidade de chuva nesse dia?**

---

## Estrutura do projeto

```
Projeto_BIGDATA/
├── leituras_202611152221.csv   # dados brutos exportados da estação
├── analise_clima.py            # script de análise
├── requirements.txt            # dependências Python
└── README.md
```

---

## Hardware

| Sensor / Origem    | Pino / Interface | Variável      | Faixa                           | Unidade                 | Descrição                                           |
| ------------------ | ---------------- | ------------- | ------------------------------- | ----------------------- | --------------------------------------------------- |
| DHT11              | GP18 (1-Wire)    | `dht_umidade` | 20 a 90 (máx. 95)               | %                       | Umidade relativa do ar (passo de 1%)                |
| DHT11              | GP18 (1-Wire)    | `dht_temp`    | 0 a 50                          | °C                      | Temperatura ambiente                                |
| BMP280             | GP16/17 (I2C0)   | `bmp_pressao` | 30.000 a 110.000                | Pa                      | Pressão barométrica absoluta                        |
| BMP280             | GP16/17 (I2C0)   | `bmp_temp`    | −40 a +85                       | °C                      | Temperatura (resolução de 0,01 °C)                  |
| BMP280 (calculado) | Barômetro        | `altitude`    | −500 a +9.000                   | m                       | Estimativa em relação a 1013,25 hPa (só no display) |
| Sensor de chuva    | GP28 (ADC2)      | `chuva_bruta` | ~300 (seco) a 65.535 (submerso) | contagens ADC (16 bits) | Tensão de 0 V (~300) a 3,3 V (65.535)               |
| Fusão térmica      | Software         | `temperatura` | 0 a 50                          | °C                      | (T<sub>DHT</sub> + T<sub>BMP</sub>) / 2             |
| Relógio NTP        | Wi-Fi / UDP 123  | `horario`     | —                               | data/hora ISO           | Horário sincronizado em UTC−3                       |
| Fila em RAM        | Software         | `fila_tam`    | 0 a 30 (ou 300)                 | registros               | Pacotes guardados na RAM enquanto offline           |

O sensor de chuva é lido com `read_u16()` do MicroPython. O ADC do RP2040 tem 12 bits, e o
valor é convertido para a escala de 16 bits (0 a 65.535) pela fórmula `raw << 4 | raw >> 8`.
Todas as leituras do CSV seguem essa fórmula, o que confirma a origem dos dados.

---

## Dados coletados

| Item       | Descrição                                           |
| ---------- | --------------------------------------------------- |
| Período    | 14/11/2026 00:00:00 → 15/11/2026 21:33:12 (~45,5 h) |
| Frequência | uma leitura a cada ~1,3 s (mediana de 1 s)          |
| Volume     | 122.341 leituras                                    |

### Colunas do CSV

| Coluna              | Tipo       | Descrição                                                            |
| ------------------- | ---------- | -------------------------------------------------------------------- |
| `data_hora`         | datetime   | Data e hora da leitura (`horario` na especificação)                  |
| `temperatura_media` | float (°C) | Média entre `dht_temp` e `bmp_temp` (`temperatura` na especificação) |
| `dht_temp`          | float (°C) | Temperatura do DHT11                                                 |
| `dht_umidade`       | float (%)  | Umidade relativa do ar do DHT11                                      |
| `bmp_temp`          | float (°C) | Temperatura do BMP280                                                |
| `bmp_pressao`       | float (Pa) | Pressão atmosférica do BMP280                                        |
| `chuva_bruta`       | int        | Leitura do sensor de chuva. **Valor alto = placa molhada**           |

`altitude` e `fila_tam` aparecem só no display e na transmissão, e não estão no CSV.

---

## Como executar

Requisitos: Python 3.10 ou superior.

```bash
pip install -r requirements.txt
python analise_clima.py
```

Para analisar outro arquivo exportado pela estação:

```bash
python analise_clima.py caminho/para/outro_arquivo.csv
```

> No Windows, use `py` no lugar de `python`. Se os acentos aparecerem errados no terminal,
> rode antes `set PYTHONIOENCODING=utf-8`.

---

## Metodologia

### 1. Limpeza e validação

- Remoção de **198 linhas duplicadas**.
- Comparação de cada coluna com a faixa de operação do sensor (tabela de hardware):

| Coluna        | Faixa válida        | Leituras fora | Uso                |
| ------------- | ------------------- | ------------- | ------------------ |
| `dht_umidade` | 20 a 95 %           | 0%            | usada              |
| `dht_temp`    | 0 a 50 °C           | 0%            | usada              |
| `bmp_temp`    | −40 a 85 °C         | 0%            | usada              |
| `chuva_bruta` | 0 a 65.535          | 0%            | usada              |
| `bmp_pressao` | 30.000 a 110.000 Pa | **100%**      | **desconsiderada** |

Restam **122.143 leituras válidas**.

### 2. Período mais úmido

O dia foi dividido em quatro períodos e foi calculada a média de `dht_umidade` em cada um:

| Período   | Horas     |
| --------- | --------- |
| Madrugada | 00h – 06h |
| Manhã     | 06h – 12h |
| Tarde     | 12h – 18h |
| Noite     | 18h – 24h |

### 3. Horário mais quente

Foi calculada a média de `temperatura_media` em cada hora do dia. A hora com a maior média é
a resposta principal. Também é mostrado o maior valor medido num instante, que é mais
sensível a oscilações momentâneas.

### 4. Probabilidade de chuva

Com a placa seca, a entrada do ADC fica em 0 V e a leitura mostra só o ruído do conversor:
entre ~250 e ~470 contagens nesta base. Uma leitura **acima de 500** indica água na placa e é
classificada como **chovendo**. A probabilidade de chuva do dia é a **fração das leituras com
água na placa**.

O resultado praticamente não depende do limiar exato. Com limiares de 400, 450, 500 ou 600, a
probabilidade de 14/11 fica entre 90,6% e 91,7%, e a de 15/11 fica em 3,8%.

A **intensidade** é a posição da leitura na escala do sensor:

```
intensidade (%) = (chuva_bruta − 300) / (65535 − 300) × 100
```

---

## Resultados

| Pergunta                   | 14/11/2026                                          | 15/11/2026\*                                        |
| -------------------------- | --------------------------------------------------- | --------------------------------------------------- |
| **Período mais úmido**     | Madrugada — 68,0%                                   | Tarde — 71,9%                                       |
| **Horário mais quente**    | 15h–16h (média 29,6 °C) · pico às 15:20 com 29,8 °C | 10h–11h (média 31,1 °C) · pico às 09:45 com 32,0 °C |
| **Probabilidade de chuva** | **91,0%**                                           | **3,8%**                                            |

\* O dia 15/11 tem dados somente até 21:33.

### Probabilidade de chuva por período

| Período   | 14/11 | 15/11 |
| --------- | ----- | ----- |
| Madrugada | 100%  | 13,6% |
| Manhã     | 64,0% | 0%    |
| Tarde     | 100%  | 0%    |
| Noite     | 100%  | 0%    |

### Interpretação

- **14/11:** a placa ficou com água quase o dia todo. Ficou seca só entre 08:11 e 10:20. A
  intensidade foi baixa: mediana de 1,5% da escala, com o maior nível estável à tarde (~5%).
  O pico de 50,6% às 00:12 é a chegada de água na placa, que escorre em cerca de 90 segundos.
- **15/11:** a placa secou às 00:40 e ficou seca até o fim da coleta. Foi também o dia com o
  horário mais quente (32,0 °C às 09:45).
- **Umidade e temperatura:** em 14/11 o ar ficou mais úmido de madrugada e menos úmido à
  tarde, o horário mais quente. Em 15/11 a umidade subiu a partir das 11h, logo depois do pico
  de calor da manhã.

---

## Limitações

- **Pressão atmosférica inválida.** Todas as leituras de `bmp_pressao` (~185.000 Pa) estão fora
  da faixa do BMP280 e são quase o dobro da pressão ao nível do mar (~101.325 Pa). Isso indica
  um erro na leitura ou na compensação do BMP280 no firmware. Por isso a coluna não foi usada.
- **Mudanças bruscas no sensor de chuva.** A leitura muda em degraus (às 00:12, 08:11, 10:20,
  11:22 e 19:50 de 14/11 e às 00:40 de 15/11), com um pico em cada mudança. As quedas
  instantâneas para "seco" (08:11 e 00:40) são rápidas demais para evaporação natural e podem
  indicar manuseio do sensor ou mau contato.
- **Água na placa não é o mesmo que chuva.** A placa também detecta orvalho e continua molhada
  depois que a chuva para. O sensor não mede o volume de chuva.
- **Placa mais molhada no período mais seco.** Em 14/11 a placa teve o maior nível de água à
  tarde, justamente quando a umidade do ar foi a menor do dia. Vale conferir onde ficam o
  sensor de chuva e o DHT11 (se um está exposto e o outro abrigado).
- **Precisão do DHT11.** O DHT11 mede a temperatura em passos de 1 °C (de 27 a 31 °C no
  período), e o BMP280 marca em média ~1,7 °C a mais. Por isso foi usada a `temperatura_media`.
- **Período curto.** São menos de dois dias de coleta, o que não basta para tirar conclusões
  climáticas, só para descrever o comportamento nesses dias.

---

## Possíveis melhorias

- Coletar por mais dias para comparar padrões entre dias.
- Corrigir a leitura do BMP280 para incluir a pressão (e a altitude) na análise.
- Gravar `altitude` e `fila_tam` no CSV para avaliar também a conectividade da estação.
- Registrar quando o sensor for manuseado, para separar testes de eventos reais.
- Gerar gráficos (ex.: `matplotlib`) da temperatura, umidade e chuva ao longo do dia.
- Usar um pluviômetro para medir o volume de chuva em mm, e não só se a placa está molhada.

---

## Tecnologias

- **Coleta:** Raspberry Pi Pico W, MicroPython, DHT11, BMP280, sensor de chuva analógico
- **Análise:** Python 3, pandas
