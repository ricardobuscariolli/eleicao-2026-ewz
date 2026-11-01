# Eficiência de mercado em tempo real — 2º turno das eleições brasileiras (25/10/2026)

*[English version](README.en.md)*

Cruzamento, minuto a minuto, de três séries na noite do 2º turno presidencial:

1. o preço do perpétuo **EWZUSDT** (Bybit), que acompanha o ETF iShares MSCI Brazil e negocia 24/7 — com B3 e NYSE fechadas no domingo, um dos poucos preços "Brasil" disponíveis;
2. a **probabilidade implícita de vitória de Lula** nos mercados de previsão **Polymarket** e **Kalshi**;
3. as **parciais da apuração** divulgadas pelo TSE.

![Gráfico com três painéis](eleicao_vs_ewz_previsao.png)

## Principais resultados

- **Os mercados de previsão se moveram antes do EWZUSDT.** As variações de probabilidade antecipam o retorno do perpétuo em cerca de 3 a 5 minutos (janela 17h00–21h10). Teste de Granger: Polymarket → EWZ, p < 0,001; EWZ → Polymarket, p ≈ 0,8. Kalshi: mesmo padrão.
- **Polymarket e Kalshi praticamente coincidem** (correlação de 0,69 entre as variações no mesmo minuto).
- **Os mercados de previsão viraram cedo.** Às 17h davam 24% a Lula; às 19h09, com menos de 3% das urnas apuradas, ele já era favorito — mais de uma hora antes de retomar a liderança no placar (20h26).
- **O degrau de −7% às 21h não foi notícia:** às 20h58 a probabilidade de Lula já era de 99%. O horário coincide com 00h UTC (liquidação de *funding* na Bybit e abertura de Tóquio), o que sugere um efeito de microestrutura.
- **Efeito implícito** (à la Snowberg, Wolfers e Zitzewitz, 2007): entre 17h00 e 20h58, o EWZUSDT caiu cerca de 20% enquanto P(Lula) subia 75 pontos. As regressões dão −16% a −28% por 1,0 de probabilidade, crescendo com o horizonte (consistente com o ajuste defasado do EWZ) e com erros-padrão grandes. Número indicativo, inflado pela alavancagem e pela baixa liquidez do perpétuo.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `eleicao_vs_ewz.py` | Baixa os dados da Bybit e gera os gráficos (2 painéis; 3 painéis se os CSVs dos mercados de previsão estiverem na pasta) |
| `mercados_previsao.py` | Baixa o histórico de 1 minuto do Polymarket e do Kalshi (APIs públicas, sem chave) |
| `mercados_previsao_colab.ipynb` | O mesmo download, pronto para rodar no Google Colab (ver "Acesso a partir do Brasil") |
| `analise_leadlag.py` | Reproduz os números acima: marcos da noite, lead-lag, Granger e efeito implícito |
| `ewz_bybit_1min.csv` | Candles de 1 minuto do EWZUSDT, 16h30–23h30 (horário de Brasília) |
| `polymarket_1min.csv` | Probabilidade (0–1) de vitória de Lula e de Flávio Bolsonaro, 1 minuto |
| `kalshi_1min.csv` | Idem, mercados KXBRPRES-26-LULA e KXBRPRES-26-FBOL, até o fechamento (21h39), com volume |
| `apuracao_manual.csv` | Parciais da apuração (horário, % de urnas, % de votos válidos de cada candidato, fonte) |
| `eleicao_vs_ewz_previsao.png` | Gráfico com 3 painéis |
| `eleicao_vs_ewz.png` | Gráfico com 2 painéis (EWZ e apuração) |

## Como rodar

```bash
pip install requests pandas numpy matplotlib statsmodels
python eleicao_vs_ewz.py --offline   # gráficos a partir dos CSVs incluídos
python analise_leadlag.py            # resultados
python eleicao_vs_ewz.py             # baixa de novo os preços da Bybit
python mercados_previsao.py          # baixa de novo os dados do Polymarket e do Kalshi
```

### Acesso a partir do Brasil

Desde abril de 2026, Polymarket e Kalshi estão proibidos e bloqueados no Brasil (Resolução do CMN e bloqueio da Anatel), e os domínios não resolvem a partir de provedores brasileiros. Os CSVs incluídos foram baixados pelo notebook `mercados_previsao_colab.ipynb`, executado no Google Colab. O script apenas lê o histórico público de preços; não envolve conta, depósito nem aposta.

## Fontes

- **EWZUSDT:** API pública da Bybit v5 (`/v5/market/kline`).
- **Polymarket:** API Gamma (`/public-search`) para localizar os mercados "Will … win the 2026 Brazilian presidential election?" e API CLOB (`/prices-history`, fidelidade de 1 minuto).
- **Kalshi:** API pública v2 (`/series/KXBRPRES/markets/{ticker}/candlesticks`, intervalo de 1 minuto). Usa o preço de fechamento negociado; nos minutos sem negócio, o ponto médio entre compra e venda.
- **Apuração:** parciais oficiais do TSE, coletadas dos blogs ao vivo da InfoMoney e da Bloomberg Línea. O TSE não disponibiliza o histórico minuto a minuto da divulgação.

## Observações

- O EWZUSDT é um derivativo alavancado, liquidado em USDT, com liquidez bem menor que a do EWZ. Mostra para onde o mercado quis ir, não um preço de equilíbrio do Ibovespa.
- Para o lead-lag, todas as séries são marcadas no fim do minuto (Bybit e Kalshi deslocados em +1 minuto). Diferenças de 1 a 2 minutos dependem dessa convenção; o atraso de 3 a 5 minutos, menos.
- Os horários da apuração são os da publicação das notícias, em geral 1–2 minutos depois do TSE. As primeiras parciais (17h16 e 19h02) cobrem menos de 0,3% das urnas.
- A votação foi prorrogada até 19h por decisão do STF; a divulgação ficou praticamente parada entre 17h e 19h. A queda a partir das 19h coincide com a retomada da divulgação e com a abertura do CME Globex (18h em Nova York).
- Um único evento, minuto a minuto, com séries de liquidez limitada: os testes são descritivos, não inferência causal.
- Exercício de divulgação, sem qualquer posição política implícita.

## Créditos

Código escrito pelo Claude (Anthropic) a partir das instruções do autor; ideia, escolhas de análise e interpretação são do autor.

Autor: Ricardo Buscariolli
