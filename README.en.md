# Market efficiency in real time — Brazil's 2026 presidential runoff (Oct 25, 2026)

*[Versão em português](README.md)*

Minute-by-minute comparison of three series on runoff night:

1. the price of the **EWZUSDT** perpetual (Bybit), which tracks the iShares MSCI Brazil ETF and trades 24/7 — with B3 and the NYSE closed on a Sunday, one of the few "Brazil" prices available;
2. the **implied probability of a Lula win** on the prediction markets **Polymarket** and **Kalshi**;
3. the **partial vote count** released by Brazil's electoral court (TSE).

![Three-panel chart](eleicao_vs_ewz_previsao.png)

## Main findings

- **Prediction markets moved before EWZUSDT.** Changes in win probability lead the perpetual's returns by about 3–5 minutes (window 5:00–9:10 pm). Granger tests: Polymarket → EWZ, p < 0.001; EWZ → Polymarket, p ≈ 0.8. Kalshi shows the same pattern.
- **Polymarket and Kalshi move almost in lockstep** (0.69 correlation of same-minute changes).
- **Prediction markets flipped early.** At 5 pm they gave Lula 24%; by 7:09 pm, with less than 3% of ballot boxes counted, he was already the favorite — over an hour before he retook the lead in the count (8:26 pm).
- **The −7% step at 9 pm was not news:** by 8:58 pm Lula's probability was already 99%. The timing matches 00:00 UTC (Bybit funding settlement and the Tokyo open), pointing to a microstructure effect.
- **Implied valuation effect** (in the spirit of Snowberg, Wolfers and Zitzewitz, 2007): from 5:00 to 8:58 pm EWZUSDT fell about 20% while P(Lula) rose 75 points. Regressions give −16% to −28% per 1.0 of probability, increasing with the horizon (consistent with EWZ's lagged adjustment) and with large standard errors. Indicative only; likely inflated by the perpetual's leverage and thin liquidity.

## Files

| File | Content |
|---|---|
| `eleicao_vs_ewz.py` | Downloads Bybit data and draws the charts (2 panels; 3 panels if the prediction-market CSVs are present) |
| `mercados_previsao.py` | Downloads 1-minute history from Polymarket and Kalshi (public APIs, no key) |
| `mercados_previsao_colab.ipynb` | Same download, ready to run on Google Colab (see "Access from Brazil") |
| `analise_leadlag.py` | Reproduces the numbers above: key times, lead-lag, Granger tests and implied effect |
| `ewz_bybit_1min.csv` | 1-minute EWZUSDT candles, 4:30–11:30 pm (Brasília time, UTC−3) |
| `polymarket_1min.csv` | Win probability (0–1) for Lula and Flávio Bolsonaro, 1 minute |
| `kalshi_1min.csv` | Same, markets KXBRPRES-26-LULA and KXBRPRES-26-FBOL, until market close (9:39 pm), with volume |
| `apuracao_manual.csv` | Partial vote-count results (time, % of ballot boxes, % of valid votes per candidate, source) |
| `eleicao_vs_ewz_previsao.png` | Three-panel chart |
| `eleicao_vs_ewz.png` | Two-panel chart (EWZ and vote count) |

## How to run

```bash
pip install requests pandas numpy matplotlib statsmodels
python eleicao_vs_ewz.py --offline   # charts from the included CSVs
python analise_leadlag.py            # results
python eleicao_vs_ewz.py             # re-download Bybit prices
python mercados_previsao.py          # re-download Polymarket and Kalshi data
```

### Access from Brazil

Since April 2026, Polymarket and Kalshi have been banned and blocked in Brazil (National Monetary Council resolution and Anatel block), and their domains do not resolve from Brazilian internet providers. The included CSVs were downloaded with `mercados_previsao_colab.ipynb`, run on Google Colab. The script only reads public price history; no account, deposit or trading is involved.

## Sources

- **EWZUSDT:** Bybit public API v5 (`/v5/market/kline`).
- **Polymarket:** Gamma API (`/public-search`) to find the "Will … win the 2026 Brazilian presidential election?" markets, and CLOB API (`/prices-history`, 1-minute fidelity).
- **Kalshi:** public API v2 (`/series/KXBRPRES/markets/{ticker}/candlesticks`, 1-minute interval). Uses the traded closing price; in minutes without trades, the bid-ask midpoint.
- **Vote count:** official TSE partial results, collected from the live blogs of InfoMoney and Bloomberg Línea. The TSE does not publish a minute-by-minute history of its releases.

## Notes

- EWZUSDT is a leveraged, USDT-settled derivative with much lower liquidity than EWZ. It shows where the market wanted to go, not an equilibrium price for Brazilian equities.
- For the lead-lag analysis all series are stamped at the end of each minute (Bybit and Kalshi shifted by +1 minute). Differences of 1–2 minutes depend on this convention; the 3–5 minute lag much less so.
- Vote-count timestamps are the times news outlets published each update, usually 1–2 minutes after the TSE release. The earliest partials (5:16 pm and 7:02 pm) cover less than 0.3% of ballot boxes.
- Voting was extended until 7 pm by a Supreme Court (STF) decision; releases were essentially paused between 5 and 7 pm. The drop starting at 7 pm coincides with the resumption of releases and the Sunday open of CME Globex (6 pm in New York).
- A single event, at one-minute frequency, with thinly traded series: the tests are descriptive, not causal inference.
- A data-communication exercise implying no political position.

## Credits

Code written by Claude (Anthropic) following the author's instructions; the idea, analytical choices and interpretation are the author's.

Author: Ricardo Buscariolli
