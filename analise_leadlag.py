"""
Análise: quem se move primeiro na noite do 2º turno (25/10/2026)?
EWZUSDT (Bybit) x probabilidade de vitória de Lula no Polymarket e no Kalshi.

Uso:
    pip install pandas numpy statsmodels
    python analise_leadlag.py

Entradas: ewz_bybit_1min.csv, polymarket_1min.csv, kalshi_1min.csv
Saída:    resultados na tela + painel_1min.csv (as três séries alinhadas)

Convenção de tempo (importante para lead-lag): todas as séries são marcadas no FIM do minuto.
  - Bybit e Kalshi: candles marcados pelo início do minuto; o fechamento ocorre 1 min depois -> +1 min
  - Polymarket (/prices-history): preço no instante -> sem ajuste
Janela de estimação: 17h00–21h10 (do fim previsto da votação à declaração do TSE).
Exercício descritivo de um único evento; não é inferência causal.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

BRT = "-03:00"
T = lambda h: pd.Timestamp(f"2026-10-25 {h}", tz=BRT)


def p_lula(arq, desloca_min):
    d = pd.read_csv(arq)
    d["t"] = pd.to_datetime(d["t"]) + pd.Timedelta(minutes=desloca_min)
    pv = d.pivot_table(index="t", columns="mercado", values="prob")
    s = pv["Lula"].fillna(1 - pv["Flávio Bolsonaro"])
    return s[~((s - 0.5).abs() < 1e-9)]   # Kalshi: livro vazio no fechamento vira 50% -> descarta


mk = pd.read_csv("ewz_bybit_1min.csv")
mk["t"] = pd.to_datetime(mk["t"]) + pd.Timedelta(minutes=1)
idx = pd.date_range(T("16:31"), T("23:31"), freq="1min")
D = pd.DataFrame(index=idx)
D["ewz"] = mk.set_index("t").close.reindex(idx).ffill()
D["polymarket"] = p_lula("polymarket_1min.csv", 0).reindex(idx).ffill()
kal = p_lula("kalshi_1min.csv", 1)
D["kalshi"] = kal.reindex(idx).ffill()
D.loc[D.index > kal.index.max(), "kalshi"] = np.nan
D.to_csv("painel_1min.csv")

# ---------------------------------------------------------------- marcos da noite
print("Horário   EWZ(desde 17h)  P(Lula) Polymarket  Kalshi")
base = D.ewz[T("17:00")]
for h in ["17:00", "19:00", "19:09", "19:40", "19:50", "20:07", "20:26", "20:58", "21:01", "21:10", "23:30"]:
    r = D.loc[T(h)]
    print(f"{h}     {100 * (r.ewz / base - 1):6.1f}%          {100 * r.polymarket:5.1f}%        "
          f"{'' if np.isnan(r.kalshi) else f'{100 * r.kalshi:5.1f}%'}")

w = D.loc[T("17:00"):T("21:10")].copy()
w["r"] = 100 * np.log(w.ewz).diff()        # retorno log do EWZUSDT, %
w["dpoly"] = 100 * w.polymarket.diff()     # variação de probabilidade, p.p.
w["dkal"] = 100 * w.kalshi.diff()
w = w.dropna()
print(f"\nJanela 17h00–21h10: {len(w)} minutos")
print(f"Correlação das variações Polymarket x Kalshi (mesmo minuto): {w.dpoly.corr(w.dkal):.2f}")

# ---------------------------------------------------------------- lead-lag
for nome, col in (("Polymarket", "dpoly"), ("Kalshi", "dkal")):
    X = pd.concat({f"k={k:+d}": w[col].shift(k) for k in range(-3, 7)}, axis=1)
    d = pd.concat([w.r, X], axis=1).dropna()
    m = sm.OLS(d.r, sm.add_constant(d.drop(columns="r"))).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    print(f"\n{nome}: retorno do EWZ no minuto t contra a variação de P(Lula) no minuto t−k "
          f"(k>0: o mercado de previsão se move antes)")
    print(pd.DataFrame({"coef": m.params, "p-valor": m.pvalues}).drop("const").round(3).T.to_string())

    # Granger nos dois sentidos, 5 defasagens, erros HAC
    L = range(1, 6)
    Z = pd.concat({**{f"r{k}": w.r.shift(k) for k in L}, **{f"p{k}": w[col].shift(k) for k in L}}, axis=1)
    g1 = sm.OLS(w.r, sm.add_constant(Z), missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    g2 = sm.OLS(w[col], sm.add_constant(Z), missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    p1 = float(g1.f_test(", ".join(f"p{k} = 0" for k in L)).pvalue)
    p2 = float(g2.f_test(", ".join(f"r{k} = 0" for k in L)).pvalue)
    print(f"Granger: {nome} -> EWZ  p = {p1:.5f}   |   EWZ -> {nome}  p = {p2:.3f}")

# ---------------------------------------------------------------- efeito implícito (à la Snowberg, Wolfers e Zitzewitz, 2007)
print("\nEfeito implícito: variação % do EWZUSDT por 1,0 de variação em P(Lula), 17h00–20h58")
for f in ("5min", "10min", "15min"):
    s = D.loc[T("17:00"):T("20:58")].resample(f).last()
    dd = pd.concat([100 * np.log(s.ewz).diff(), s.polymarket.diff()], axis=1).dropna()
    m = sm.OLS(dd.iloc[:, 0], sm.add_constant(dd.iloc[:, 1])).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
    print(f"  dados a cada {f:>5}: beta = {m.params.iloc[1]:6.1f}%  (erro-padrão {m.bse.iloc[1]:.1f}; N = {len(dd)})")
a, b = T("17:00"), T("20:58")
print(f"  ponta a ponta: {100 * np.log(D.ewz[b] / D.ewz[a]):.1f}% / {D.polymarket[b] - D.polymarket[a]:.2f} "
      f"= {100 * np.log(D.ewz[b] / D.ewz[a]) / (D.polymarket[b] - D.polymarket[a]):.1f}%")
