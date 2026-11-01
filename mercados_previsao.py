"""
Baixa a probabilidade implícita (minuto a minuto) dos mercados de previsão sobre a
eleição presidencial brasileira de 2026, na noite do 2º turno (25/10/2026).

  - Polymarket: API pública Gamma (busca do mercado) + CLOB /prices-history (preços de 1 min)
  - Kalshi:     API pública v2 (lista do evento KXBRPRES-26) + candlesticks de 1 min

Uso:
    pip install requests pandas
    python mercados_previsao.py

Saídas (na mesma pasta):
    polymarket_1min.csv   colunas: t, mercado, prob
    kalshi_1min.csv       colunas: t, mercado, prob, volume
    log_mercados.txt      tudo o que foi impresso na tela (cole aqui no chat se der erro)
    debug_*.json          respostas brutas das APIs, para diagnóstico

Convenção de tempo: t = INÍCIO do minuto, horário de Brasília (igual aos candles da Bybit).
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

BRT = timezone(timedelta(hours=-3))
INICIO = datetime(2026, 10, 25, 16, 30, tzinfo=BRT)
FIM = datetime(2026, 10, 25, 23, 30, tzinfo=BRT)
TS0, TS1 = int(INICIO.timestamp()), int(FIM.timestamp())
HEADERS = {"User-Agent": "Mozilla/5.0 (pesquisa academica; eleicao-2026-ewz)"}

_log = open("log_mercados.txt", "w", encoding="utf-8")


def log(*args):
    msg = " ".join(str(a) for a in args)
    print(msg)
    _log.write(msg + "\n")
    _log.flush()


def get(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=40)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


def salvar_debug(nome, obj):
    with open(f"debug_{nome}.json", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def _lista(x):
    """Campos como outcomes/clobTokenIds às vezes vêm como string JSON."""
    if isinstance(x, str):
        try:
            return json.loads(x)
        except json.JSONDecodeError:
            return [x]
    return x or []


def _quem(texto):
    t = (texto or "").lower()
    if "lula" in t:
        return "Lula"
    if "flávio" in t or "flavio" in t:
        return "Flávio Bolsonaro"
    return None


# ============================================================ Polymarket
def polymarket():
    log("\n=== POLYMARKET ===")
    candidatos = {}
    for q in ("Brazil presidential election", "Brazil election winner", "Lula Brazil election"):
        st, js = get("https://gamma-api.polymarket.com/public-search",
                     dict(q=q, keep_closed_markets=1, limit_per_type=25))
        if st != 200 or not isinstance(js, dict):
            log(f"  busca '{q}': HTTP {st}")
            continue
        salvar_debug(f"polymarket_busca_{q.replace(' ', '_')}", js)
        for ev in js.get("events") or []:
            for m in ev.get("markets") or []:
                pergunta = m.get("question") or ""
                p = pergunta.lower()
                # queremos o mercado "quem vence a eleição" (não 1º turno, margem, 2º lugar...)
                if not ("brazil" in p and ("presidential" in p or "president" in p)):
                    continue
                if any(x in p for x in ("first round", "1st round", "margin", "second place", "by at least")):
                    continue
                quem = _quem(pergunta)
                if quem is None or "win" not in p:
                    continue
                candidatos[m.get("slug") or pergunta] = (quem, pergunta, m)

    if not candidatos:
        log("  Nenhum mercado encontrado. Veja os arquivos debug_polymarket_busca_*.json.")
        return
    log("  Mercados encontrados:")
    for slug, (quem, pergunta, m) in candidatos.items():
        log(f"   - [{quem}] {pergunta}  (slug={slug}, fechado={m.get('closed')})")

    linhas = []
    usados = set()
    for slug, (quem, pergunta, m) in candidatos.items():
        if quem in usados:   # um mercado por candidato
            continue
        outcomes, tokens = _lista(m.get("outcomes")), _lista(m.get("clobTokenIds"))
        try:
            token_yes = tokens[[o.lower() for o in outcomes].index("yes")]
        except (ValueError, IndexError):
            log(f"  [{quem}] não achei o token 'Yes' (outcomes={outcomes})")
            continue
        n0 = len(linhas)
        # baixa em janelas de 1 hora, com fidelidade de 1 minuto
        for a in range(TS0, TS1, 3600):
            st, js = get("https://clob.polymarket.com/prices-history",
                         dict(market=token_yes, startTs=a, endTs=min(a + 3600, TS1), fidelity=1))
            if st != 200 or not isinstance(js, dict):
                log(f"  [{quem}] prices-history HTTP {st}: {str(js)[:200]}")
                continue
            for h in js.get("history", []):
                linhas.append(dict(t=h["t"], mercado=quem, prob=float(h["p"])))
            time.sleep(0.3)
        log(f"  [{quem}] {len(linhas) - n0} pontos baixados")
        usados.add(quem)

    if linhas:
        df = pd.DataFrame(linhas)
        df["t"] = pd.to_datetime(df["t"], unit="s", utc=True).dt.tz_convert(BRT).dt.floor("min")
        df = df.drop_duplicates(["t", "mercado"]).sort_values(["mercado", "t"])
        df.to_csv("polymarket_1min.csv", index=False)
        resumo(df, "polymarket_1min.csv")


# ============================================================ Kalshi
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"


def _preco_kalshi(c):
    """Fecha do candle: preço negociado; se não houver negócio, ponto médio bid/ask. Normaliza para 0-1."""
    def num(v):
        if v is None:
            return None
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v / 100 if v > 1 else v   # centavos -> probabilidade

    preco = c.get("price") or {}
    for chave in ("close_dollars", "close"):
        v = num(preco.get(chave))
        if v is not None:
            return v, "negocio"
    bid = c.get("yes_bid") or c.get("bid") or {}
    ask = c.get("yes_ask") or c.get("ask") or {}
    b = next((num(bid.get(k)) for k in ("close_dollars", "close") if num(bid.get(k)) is not None), None)
    a = next((num(ask.get(k)) for k in ("close_dollars", "close") if num(ask.get(k)) is not None), None)
    if b is not None and a is not None:
        return (a + b) / 2, "mid"
    return None, None


def kalshi(evento="KXBRPRES-26"):
    log("\n=== KALSHI ===")
    serie = evento.split("-")[0]
    st, js = get(f"{KALSHI}/markets", dict(event_ticker=evento, limit=200))
    if st != 200 or not isinstance(js, dict):
        log(f"  lista de mercados: HTTP {st}: {str(js)[:300]}")
        return
    salvar_debug("kalshi_mercados", js)
    mercados = js.get("markets") or []
    log(f"  {len(mercados)} mercados no evento {evento}:")
    escolhidos = {}
    for m in mercados:
        rotulo = m.get("yes_sub_title") or m.get("subtitle") or m.get("title") or ""
        log(f"   - {m.get('ticker')}: {rotulo}  (status={m.get('status')})")
        quem = _quem(rotulo) or _quem(m.get("ticker"))
        if quem and quem not in escolhidos:
            escolhidos[quem] = m["ticker"]

    linhas = []
    for quem, ticker in escolhidos.items():
        params = dict(start_ts=TS0, end_ts=TS1, period_interval=1)
        tentativas = [f"{KALSHI}/series/{serie}/markets/{ticker}/candlesticks",
                      f"{KALSHI}/historical/markets/{ticker}/candlesticks"]
        candles = []
        for url in tentativas:
            st, js = get(url, params)
            if st == 200 and isinstance(js, dict) and js.get("candlesticks"):
                candles = js["candlesticks"]
                salvar_debug(f"kalshi_candles_{ticker}", js)
                break
            log(f"  [{quem}] {url.split('/v2/')[1]} -> HTTP {st}")
        n_mid = 0
        for c in candles:
            p, tipo = _preco_kalshi(c)
            if p is None:
                continue
            n_mid += tipo == "mid"
            linhas.append(dict(t=int(c["end_period_ts"]) - 60, mercado=quem, prob=p,
                               volume=float(c.get("volume") or c.get("volume_fp") or 0)))
        log(f"  [{quem}] {ticker}: {len(candles)} candles ({n_mid} sem negócio, usando ponto médio bid/ask)")

    if linhas:
        df = pd.DataFrame(linhas)
        df["t"] = pd.to_datetime(df["t"], unit="s", utc=True).dt.tz_convert(BRT)
        df = df.drop_duplicates(["t", "mercado"]).sort_values(["mercado", "t"])
        df.to_csv("kalshi_1min.csv", index=False)
        resumo(df, "kalshi_1min.csv")


def resumo(df, arquivo):
    log(f"  -> salvo {arquivo}")
    for quem, g in df.groupby("mercado"):
        def em(h, m):
            alvo = datetime(2026, 10, 25, h, m, tzinfo=BRT)
            x = g[g.t <= alvo]
            return f"{x.prob.iloc[-1]:.0%}" if len(x) else "—"
        log(f"     {quem}: {len(g)} min | P(vitória) às 17h={em(17, 0)}, 19h={em(19, 0)}, "
            f"20h={em(20, 0)}, 20h30={em(20, 30)}, 21h={em(21, 0)}, 22h={em(22, 0)}")


if __name__ == "__main__":
    for etapa in (polymarket, kalshi):
        try:
            etapa()
        except Exception as e:   # um mercado falhar não impede o outro
            log(f"  ERRO em {etapa.__name__}: {type(e).__name__}: {e}")
    log("\nFim. Mande aqui os CSVs gerados e o log_mercados.txt.")
    _log.close()
