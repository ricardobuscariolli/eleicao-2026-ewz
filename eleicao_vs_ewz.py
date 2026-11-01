"""
Eficiência de mercado em tempo real: apuração do 2º turno (25/10/2026) x EWZUSDT (Bybit)

Painel superior: retorno acumulado (%) do perpétuo EWZUSDT na Bybit, minuto a minuto
Painel inferior: % de votos válidos de Lula (vermelho) e Flávio (azul) durante a apuração

Uso:
    pip install requests pandas matplotlib
    python eleicao_vs_ewz.py              # baixa Bybit + usa apuracao_manual.csv (já preenchido)
    python eleicao_vs_ewz.py --offline    # usa ewz_bybit_1min.csv já salvo (não acessa a Bybit)
    python eleicao_vs_ewz.py --wayback   # alternativa: tenta reconstruir a apuração via Wayback Machine
    python eleicao_vs_ewz.py --demo       # dados simulados, só para testar o gráfico

Fontes:
  - Bybit API pública v5 (sem chave): /v5/market/kline, candles de 1 minuto
  - TSE: o JSON de divulgação (br-c0001-e00XXXX-r.json) é sobrescrito a cada atualização;
    o TSE não guarda o histórico. As fotografias intermediárias só existem se alguém as
    arquivou (Wayback Machine) ou nas parciais publicadas por portais de notícia.
"""
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BRT = timezone(timedelta(hours=-3))
INICIO = datetime(2026, 10, 25, 17, 0, tzinfo=BRT)    # fim previsto da votação
FIM = datetime(2026, 10, 25, 23, 30, tzinfo=BRT)
DECLARACAO = datetime(2026, 10, 25, 21, 10, tzinfo=BRT)
FIM_VOTACAO = datetime(2026, 10, 25, 17, 0, tzinfo=BRT)   # horário original
RETOMADA = datetime(2026, 10, 25, 19, 0, tzinfo=BRT)      # fim da prorrogação (STF) e retomada da divulgação
SIMBOLO = "EWZUSDT"


# ---------------------------------------------------------------- mercado (Bybit)
def baixar_bybit(simbolo=SIMBOLO, inicio=INICIO, fim=FIM):
    url = "https://api.bybit.com/v5/market/kline"
    linhas, ini = [], int(inicio.timestamp() * 1000)
    fim_ms = int(fim.timestamp() * 1000)
    while ini < fim_ms:
        r = requests.get(url, params=dict(category="linear", symbol=simbolo, interval="1",
                                          start=ini, end=fim_ms, limit=1000), timeout=30)
        r.raise_for_status()
        js = r.json()
        if js.get("retCode") != 0:
            raise RuntimeError(f"Bybit: {js.get('retMsg')}")
        lote = js["result"]["list"]
        if not lote:
            break
        linhas += lote
        ini = max(int(x[0]) for x in lote) + 60_000
    df = pd.DataFrame(linhas, columns=["t", "open", "high", "low", "close", "volume", "turnover"])
    df["t"] = pd.to_datetime(df["t"].astype("int64"), unit="ms", utc=True).dt.tz_convert(BRT)
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df.drop_duplicates("t").sort_values("t").reset_index(drop=True)


# ---------------------------------------------------------------- apuração (TSE via Wayback)
def _num(x):
    return float(str(x).replace(",", "."))


def apuracao_wayback(prefixo="resultados.tse.jus.br/oficial/ele2026/"):
    """Procura snapshots arquivados do JSON nacional de presidente (br-c0001-...-r.json)."""
    cdx = requests.get("http://web.archive.org/cdx/search/cdx", timeout=60, params=dict(
        url=prefixo, matchType="prefix", output="json",
        filter=["original:.*br-c0001-e.*-r\\.json", "statuscode:200"],
        **{"from": "20261025", "to": "20261026"})).json()
    if len(cdx) <= 1:
        return pd.DataFrame()
    cab, snaps = cdx[0], [dict(zip(cdx[0], s)) for s in cdx[1:]]
    print(f"{len(snaps)} snapshots encontrados no Wayback")
    regs = []
    for s in snaps:
        try:
            js = requests.get(f"http://web.archive.org/web/{s['timestamp']}id_/{s['original']}",
                              timeout=60).json()
            if js.get("t", "2") not in ("2", 2) and "2" not in str(js.get("tpabr", "")):
                pass  # alguns arquivos não trazem o turno; o filtro por data já resolve
            hora = datetime.strptime(f"{js['dt']} {js['ht']}", "%d/%m/%Y %H:%M:%S").replace(tzinfo=BRT)
            votos = {c["nm"].upper(): _num(c["pvap"]) for c in js["cand"]}
            lula = next(v for k, v in votos.items() if "LULA" in k)
            flavio = next(v for k, v in votos.items() if "FL" in k and "BOLSONARO" in k)
            regs.append(dict(t=hora, pct_urnas=_num(js["pst"]), lula=lula, flavio=flavio))
        except Exception as e:  # snapshot quebrado, de outro turno etc.
            print("  pulando", s["timestamp"], type(e).__name__)
        time.sleep(1)  # educado com o Wayback
    return pd.DataFrame(regs).drop_duplicates("t").sort_values("t").reset_index(drop=True)


def apuracao_manual(arquivo="apuracao_manual.csv"):
    """CSV com colunas: hora (HH:MM, horário de Brasília), pct_urnas, lula, flavio."""
    df = pd.read_csv(arquivo, dtype=str)
    df["t"] = pd.to_datetime("2026-10-25 " + df["hora"]).dt.tz_localize(BRT)
    for c in ("pct_urnas", "lula", "flavio"):
        df[c] = df[c].map(_num)
    return df.sort_values("t").reset_index(drop=True)


# ---------------------------------------------------------------- dados simulados (teste)
def dados_demo():
    import numpy as np
    rng = np.random.default_rng(7)
    t = pd.date_range(INICIO, FIM, freq="1min")
    tt = (t - FIM_VOTACAO).total_seconds().values / 3600
    # apuração: Flávio larga na frente (Sul/Sudeste) e o Nordeste vira o jogo
    pct = 100 * (1 - np.exp(-np.clip(tt, 0, None) / 1.4))
    lula = 46 + 4.9 * (1 - np.exp(-pct / 45))
    ap = pd.DataFrame(dict(t=t, pct_urnas=pct, lula=lula, flavio=100 - lula))
    ap = ap[(ap.t >= FIM_VOTACAO + timedelta(minutes=20)) & (ap.index % 5 == 0)]
    # mercado reage à probabilidade implícita de vitória do Lula
    drift = -2.8 / (1 + np.exp(-(tt - 3.4) * 3))
    close = 30 * np.exp((drift + np.cumsum(rng.normal(0, 0.05, len(t)))) / 100)
    mk = pd.DataFrame(dict(t=t, close=close))
    return mk, ap.reset_index(drop=True)


# ---------------------------------------------------------------- gráfico
def grafico(mk, ap, saida="eleicao_vs_ewz.png"):
    base = mk.loc[mk.t <= FIM_VOTACAO, "close"].iloc[-1] if (mk.t <= FIM_VOTACAO).any() else mk.close.iloc[0]
    mk = mk.assign(ret=100 * (mk.close / base - 1))

    VERMELHO, AZUL, CINZA = "#C8102E", "#1F4E9C", "#6B7280"
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 8.4),
                                 gridspec_kw=dict(height_ratios=[1, 1], hspace=0.28))
    INI_VOTOS = INICIO     # mesmo eixo nos dois painéis; a apuração só aparece a partir das 19h

    a1.plot(mk.t, mk.ret, color="#111827", lw=1.4)
    a1.axhline(0, color=CINZA, lw=0.8, ls=":")
    a1.set_ylabel(f"{SIMBOLO} (Bybit)\nretorno acumulado desde 17h (%)")
    a1.set_title("Eficiência de mercado em tempo real — 2º turno, 25/10/2026",
                 loc="left", fontsize=14, fontweight="bold")

    a2.plot(ap.t, ap.lula, color=VERMELHO, lw=2, marker="o", ms=3, label="Lula")
    a2.plot(ap.t, ap.flavio, color=AZUL, lw=2, marker="o", ms=3, label="Flávio Bolsonaro")
    a2.axhline(50, color=CINZA, lw=0.8, ls=":")
    a2.set_ylabel("% dos votos válidos")
    a2.legend(frameon=False, loc="upper right")
    a2.set_title("Apuração do TSE", loc="left",
                 fontsize=10, color="#111827")

    # % de urnas apuradas como eixo secundário discreto
    a3 = a2.twinx()
    a3.fill_between(ap.t, ap.pct_urnas, color=CINZA, alpha=0.10, step="post")
    a3.set_ylim(0, 100)
    a3.set_ylabel("% de urnas apuradas (sombra)", color=CINZA)
    a3.tick_params(colors=CINZA)
    a3.spines["right"].set_visible(True)
    a2.set_zorder(a3.get_zorder() + 1); a2.patch.set_visible(False)

    # trocas de liderança (nos dois sentidos)
    lider = (ap.lula > ap.flavio)
    trocas = ap[lider != lider.shift()].iloc[1:]

    # linhas verticais
    for ax in (a1, a2):
        ax.axvspan(FIM_VOTACAO, RETOMADA, color=CINZA, alpha=0.07, lw=0)
    for ax in (a1, a2):
        ax.axvline(RETOMADA, color="#111827", lw=1.2)
    a2.text(FIM_VOTACAO + timedelta(minutes=3), 53, "17h–19h: votação prorrogada,\ndivulgação suspensa",
            fontsize=8, color=CINZA, va="center")
    pre = ap[ap.t < RETOMADA]
    if not pre.empty:   # parcial divulgada antes da suspensão
        r = pre.iloc[0]
        a2.text(r.t + timedelta(minutes=2), r.lula - 2.3,
                f"{r.t:%Hh%M}: {r.pct_urnas:.2f}% das urnas,\nantes da suspensão".replace(".", ","),
                fontsize=7.5, color="#111827", va="center")
    a2.text(RETOMADA + timedelta(minutes=2), 45, "19h01: divulgação\nretomada", fontsize=8,
            color="#111827", va="center", ha="left",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))
    for ax in (a1, a2):
        ax.axvline(DECLARACAO, color="#111827", lw=1)
        for _, r in trocas.iterrows():
            ax.axvline(r.t, color=VERMELHO if r.lula > r.flavio else AZUL, lw=1, ls="--", alpha=0.7)
    a1.text(FIM_VOTACAO + timedelta(minutes=3), -26, "17h–19h: votação prorrogada,\ndivulgação suspensa",
            fontsize=8, color=CINZA, va="bottom")
    for ax, y, va in ((a1, a1.get_ylim()[1], "top"), (a2, 55, "center")):
        ax.text(DECLARACAO, y, " TSE declara\n Lula eleito\n (21h10)", va=va, fontsize=8,
                color="#111827", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.95))

    # queda das 19h no painel de cima
    if (mk.t == RETOMADA).any():
        a1.annotate("19h: início das divulgações\ne abertura do CME Globex\n(18h em Nova York)",
                    xy=(RETOMADA, mk.loc[mk.t == RETOMADA, "ret"].iloc[0]),
                    xytext=(datetime(2026, 10, 25, 17, 25, tzinfo=BRT), -14), textcoords="data",
                    fontsize=8, color=CINZA, arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.7))

    # rótulos das viradas, colados às linhas tracejadas
    for _, r in trocas.iterrows():
        lula_lidera = r.lula > r.flavio
        cor = VERMELHO if lula_lidera else AZUL
        quem = "Lula" if lula_lidera else "Flávio"
        a2.text(r.t + timedelta(minutes=1.5), 46.5 if lula_lidera else 54,
                f"{quem} assume {r.t:%Hh%M}\n({r.pct_urnas:.0f}% apuradas)", ha="left", va="center",
                fontsize=8, color=cor, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))

    # degrau das 21h: 00h UTC (abertura de Tóquio / liquidação de funding na Bybit)
    t21 = datetime(2026, 10, 25, 21, 0, tzinfo=BRT)
    if (mk.t == t21).any():
        y21 = mk.loc[mk.t == t21, "ret"].iloc[0]
        a1.annotate("21h = 00h UTC\n(abertura de Tóquio,\nfunding da Bybit)", (t21, y21),
                    xytext=(datetime(2026, 10, 25, 21, 35, tzinfo=BRT), -17), textcoords="data",
                    fontsize=8, color=CINZA, ha="left", zorder=5,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.95),
                    arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.7))

    for ax, ini in ((a1, INICIO), (a2, INI_VOTOS)):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=BRT))
        ax.set_xlim(ini, FIM)
    a2.set_xlabel("Horário de Brasília")

    # alinha as horas: o painel de baixo começa exatamente embaixo das 19h do painel de cima
    p1, p2 = a1.get_position(), a2.get_position()
    frac = (INI_VOTOS - INICIO) / (FIM - INICIO)
    for ax in (a2, a3):
        ax.set_position([p1.x0 + frac * p1.width, p2.y0, p1.width * (1 - frac), p2.height])
    fig.text(0.01, 0.005, "Fontes: Bybit (perpétuo EWZUSDT, candles de 1 min); parciais do TSE publicadas por "
             "InfoMoney e Bloomberg Línea (horário da publicação). Domingo: B3 e NYSE fechadas.",
             fontsize=7.5, color=CINZA)
    fig.savefig(saida, dpi=200, bbox_inches="tight")
    print("salvo em", saida)


# ---------------------------------------------------------------- mercados de previsão (opcional)
def carregar_previsao():
    """Lê polymarket_1min.csv e kalshi_1min.csv (gerados por mercados_previsao.py), se existirem.
    Devolve {fonte: Série de P(Lula vence)} com horário = FIM do minuto (mesma convenção da análise)."""
    import os
    out = {}
    for fonte, arq, desloca in (("Polymarket", "polymarket_1min.csv", 0), ("Kalshi", "kalshi_1min.csv", 1)):
        if not os.path.exists(arq):
            continue
        d = pd.read_csv(arq)
        d["t"] = pd.to_datetime(d["t"]) + pd.Timedelta(minutes=desloca)   # Kalshi: candle -> fim do minuto
        pv = d.pivot_table(index="t", columns="mercado", values="prob")
        s = pv["Lula"].fillna(1 - pv["Flávio Bolsonaro"]) if "Flávio Bolsonaro" in pv else pv["Lula"]
        if fonte == "Kalshi":   # no fechamento do mercado o livro esvazia e o ponto médio vira 50%: descarta
            s = s[~((s - 0.5).abs() < 1e-9)]
        out[fonte] = s.sort_index()
    return out


def grafico3(mk, ap, prev, saida="eleicao_vs_ewz_previsao.png"):
    """Três painéis no mesmo eixo: EWZUSDT, P(Lula vence) nos mercados de previsão, apuração."""
    mk = mk.assign(t=mk.t + pd.Timedelta(minutes=1))   # close do candle -> fim do minuto
    base = mk.loc[mk.t <= FIM_VOTACAO, "close"].iloc[-1]
    mk = mk.assign(ret=100 * (mk.close / base - 1))

    VERMELHO, AZUL, CINZA, PRETO = "#C8102E", "#1F4E9C", "#6B7280", "#111827"
    COR_PREV = {"Polymarket": "#6D28D9", "Kalshi": "#0F766E"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    fig, (a1, ap_, a2) = plt.subplots(3, 1, figsize=(10, 11.5), sharex=True,
                                      gridspec_kw=dict(height_ratios=[1.15, 0.9, 0.9], hspace=0.22))

    # --- painel 1: EWZUSDT
    a1.plot(mk.t, mk.ret, color=PRETO, lw=1.4)
    a1.axhline(0, color=CINZA, lw=0.8, ls=":")
    a1.set_ylabel(f"{SIMBOLO} (Bybit)\nretorno desde 17h (%)")
    a1.set_title("Eficiência de mercado em tempo real — 2º turno, 25/10/2026",
                 loc="left", fontsize=14, fontweight="bold")

    # --- painel 2: mercados de previsão
    for fonte, s in prev.items():
        s = s[(s.index >= INICIO) & (s.index <= FIM)]
        ap_.plot(s.index, 100 * s.values, color=COR_PREV[fonte], lw=1.6,
                 ls="-" if fonte == "Polymarket" else "--", label=fonte)
    ap_.axhline(50, color=CINZA, lw=0.8, ls=":")
    ap_.set_ylim(0, 100)
    ap_.set_ylabel("P(Lula vence) (%)\nmercados de previsão")
    ap_.set_title("Probabilidade implícita de vitória de Lula", loc="left", fontsize=10, color=PRETO)
    ap_.legend(frameon=False, loc="lower right")
    poly = prev.get("Polymarket")
    if poly is not None:
        p17 = poly[poly.index <= FIM_VOTACAO].iloc[-1]
        ap_.text(FIM_VOTACAO + timedelta(minutes=3), 62,
                 f"17h: {100 * p17:.0f}% para Lula\n(véspera: favoritismo de Flávio)",
                 fontsize=8, color=COR_PREV["Polymarket"], va="bottom")
        cruza = poly[(poly.index >= RETOMADA) & (poly > 0.5)]
        if len(cruza):
            tc = cruza.index[0]
            depois = ap.loc[ap.t >= tc, "pct_urnas"]   # parciais só têm horário de notícia: dá um teto
            u = f"\n(menos de {int(depois.iloc[0]) + 1}% das urnas)" if len(depois) else ""
            ap_.axvline(tc, color=COR_PREV["Polymarket"], lw=1, ls=":")
            ap_.text(tc - timedelta(minutes=2), 88, f"Lula vira favorito: {tc:%Hh%M}{u}",
                     ha="right", va="center", fontsize=8, color=COR_PREV["Polymarket"],
                     bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))

    # --- painel 3: apuração
    a2.plot(ap.t, ap.lula, color=VERMELHO, lw=2, marker="o", ms=3, label="Lula")
    a2.plot(ap.t, ap.flavio, color=AZUL, lw=2, marker="o", ms=3, label="Flávio Bolsonaro")
    a2.axhline(50, color=CINZA, lw=0.8, ls=":")
    a2.set_ylabel("% dos votos válidos")
    a2.set_title("Apuração do TSE", loc="left", fontsize=10, color=PRETO)
    a2.legend(frameon=False, loc="upper right")
    a3 = a2.twinx()
    a3.fill_between(ap.t, ap.pct_urnas, color=CINZA, alpha=0.10, step="post")
    a3.set_ylim(0, 100)
    a3.set_ylabel("% de urnas apuradas (sombra)", color=CINZA)
    a3.tick_params(colors=CINZA)
    a3.spines["right"].set_visible(True)
    a2.set_zorder(a3.get_zorder() + 1); a2.patch.set_visible(False)

    # --- linhas verticais comuns
    lider = (ap.lula > ap.flavio)
    trocas = ap[lider != lider.shift()].iloc[1:]
    for ax in (a1, ap_, a2):
        ax.axvspan(FIM_VOTACAO, RETOMADA, color=CINZA, alpha=0.07, lw=0)
        ax.axvline(RETOMADA, color=PRETO, lw=1.2)
        ax.axvline(DECLARACAO, color=PRETO, lw=1)
        for _, r in trocas.iterrows():
            ax.axvline(r.t, color=VERMELHO if r.lula > r.flavio else AZUL, lw=1, ls="--", alpha=0.7)

    # --- anotações
    a1.text(FIM_VOTACAO + timedelta(minutes=3), a1.get_ylim()[0] + 1, "17h–19h: votação prorrogada,\ndivulgação suspensa",
            fontsize=8, color=CINZA, va="bottom")
    a1.text(DECLARACAO, a1.get_ylim()[1], " TSE declara\n Lula eleito\n (21h10)", va="top", fontsize=8,
            color=PRETO, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.95))
    t19 = RETOMADA + timedelta(minutes=1)
    if (mk.t == t19).any():
        a1.annotate("19h: divulgação retomada\ne abertura do CME Globex\n(18h em Nova York)",
                    xy=(t19, mk.loc[mk.t == t19, "ret"].iloc[0]),
                    xytext=(datetime(2026, 10, 25, 17, 25, tzinfo=BRT), -14), textcoords="data",
                    fontsize=8, color=CINZA, arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.7))
    t21 = datetime(2026, 10, 25, 21, 1, tzinfo=BRT)
    if (mk.t == t21).any():
        txt = "21h = 00h UTC (Tóquio,\nfunding da Bybit)"
        if poly is not None:
            txt += f"\nP(Lula) já em {100 * poly[poly.index <= t21].iloc[-1]:.0f}%"
        a1.annotate(txt, (t21, mk.loc[mk.t == t21, "ret"].iloc[0]),
                    xytext=(datetime(2026, 10, 25, 21, 35, tzinfo=BRT), -15), textcoords="data",
                    fontsize=8, color=CINZA, ha="left", zorder=5,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.95),
                    arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.7))
    for _, r in trocas.iterrows():
        lula_lidera = r.lula > r.flavio
        a2.text(r.t + timedelta(minutes=1.5), 46.5 if lula_lidera else 54,
                f"{'Lula' if lula_lidera else 'Flávio'} assume {r.t:%Hh%M}\n({r.pct_urnas:.0f}% apuradas)",
                ha="left", va="center", fontsize=8, color=VERMELHO if lula_lidera else AZUL,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))

    a2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=BRT))
    a2.set_xlim(INICIO, FIM)
    a2.set_xlabel("Horário de Brasília")
    fig.text(0.01, 0.005, "Fontes: Bybit (perpétuo EWZUSDT), Polymarket e Kalshi (APIs públicas, 1 min); parciais do TSE "
             "publicadas por InfoMoney e Bloomberg Línea.\nHorários no fim de cada minuto. Domingo: B3 e NYSE fechadas.",
             fontsize=7.5, color=CINZA)
    fig.savefig(saida, dpi=200, bbox_inches="tight")
    print("salvo em", saida)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        mk, ap = dados_demo()
        grafico(mk, ap, "eleicao_vs_ewz_DEMO.png")
        sys.exit()
    if "--offline" in sys.argv:   # reaproveita o CSV já baixado, sem acessar a Bybit
        mk = pd.read_csv("ewz_bybit_1min.csv")
        mk["t"] = pd.to_datetime(mk["t"])
    else:
        mk = baixar_bybit()
    print(f"Bybit: {len(mk)} candles de 1 min")
    # padrão: série das parciais publicadas (apuracao_manual.csv, já preenchido);
    # --wayback tenta reconstruir a partir de snapshots arquivados do JSON do TSE
    ap = apuracao_wayback() if "--wayback" in sys.argv else apuracao_manual()
    if ap.empty:
        sys.exit("Nada encontrado no Wayback; rode sem --wayback para usar apuracao_manual.csv.")
    mk.to_csv("ewz_bybit_1min.csv", index=False)
    ap.to_csv("apuracao_serie.csv", index=False)
    grafico(mk, ap)
    prev = carregar_previsao()   # se houver polymarket_1min.csv / kalshi_1min.csv na pasta
    if prev:
        grafico3(mk, ap, prev)
