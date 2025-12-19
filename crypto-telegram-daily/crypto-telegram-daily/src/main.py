import os
import requests
import yaml
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # e.g. @your_channel OR -100xxxxxxxxxx

# --- Data sources ---
FNG_URL = "https://api.alternative.me/fng/?limit=3"
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{token}"

def tg_send_html(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()

def get_fear_greed():
    r = requests.get(FNG_URL, timeout=30)
    r.raise_for_status()
    data = r.json()["data"]
    # data[0] now, data[1] yesterday, data[2] last week (usually)
    def fmt(item):
        return int(item["value"]), item["value_classification"]
    now_v, now_c = fmt(data[0])
    y_v, y_c = fmt(data[1]) if len(data) > 1 else (None, None)
    w_v, w_c = fmt(data[2]) if len(data) > 2 else (None, None)
    return (now_v, now_c), (y_v, y_c), (w_v, w_c)

def dex_token_snapshot(token: str):
    url = DEXSCREENER_TOKEN_URL.format(token=token)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    js = r.json()
    pairs = js.get("pairs") or []
    if not pairs:
        return None

    # pick the most liquid pair (or highest 24h volume as fallback)
    def score(p):
        liq = (p.get("liquidity") or {}).get("usd") or 0
        vol = (p.get("volume") or {}).get("h24") or 0
        tx  = (p.get("txns") or {}).get("h24") or {}
        txc = (tx.get("buys") or 0) + (tx.get("sells") or 0)
        return (liq, vol, txc)
    p = sorted(pairs, key=score, reverse=True)[0]

    base = (p.get("baseToken") or {})
    quote = (p.get("quoteToken") or {})

    # core fields
    name = base.get("name") or "Unknown"
    symbol = base.get("symbol") or "?"
    chain = p.get("chainId") or "?"
    dex = p.get("dexId") or "?"
    price = p.get("priceUsd")
    fdv = p.get("fdv")  # Dexscreener often uses FDV as proxy for mcap
    liq_usd = (p.get("liquidity") or {}).get("usd")
    vol_24h = (p.get("volume") or {}).get("h24")
    chg_24h = (p.get("priceChange") or {}).get("h24")
    tx = (p.get("txns") or {}).get("h24") or {}
    buys = tx.get("buys") or 0
    sells = tx.get("sells") or 0
    url = p.get("url")

    return {
        "name": name,
        "symbol": symbol,
        "chain": chain,
        "dex": dex,
        "price_usd": price,
        "fdv": fdv,
        "liq_usd": liq_usd,
        "vol_24h": vol_24h,
        "chg_24h": chg_24h,
        "buys": buys,
        "sells": sells,
        "pair_url": url,
        "quote_symbol": quote.get("symbol") or "",
    }

def fmt_money(x):
    if x is None:
        return "—"
    try:
        x = float(x)
    except Exception:
        return str(x)
    absx = abs(x)
    if absx >= 1e9:
        return f"${x/1e9:.2f}B"
    if absx >= 1e6:
        return f"${x/1e6:.2f}M"
    if absx >= 1e3:
        return f"${x/1e3:.2f}K"
    return f"${x:.2f}"

def fmt_pct(x):
    if x is None:
        return "—"
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return str(x)

def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    tz_bj = timezone(timedelta(hours=8))
    now = datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M")

    cfg = load_yaml("config.yaml")
    topics = (load_yaml("hot_topics.yaml") or {}).get("topics", [])

    (fg_now_v, fg_now_c), (fg_y_v, fg_y_c), (fg_w_v, fg_w_c) = get_fear_greed()

    # meme list
    items = []
    for it in cfg.get("watchlist", []):
        snap = dex_token_snapshot(it["address"])
        if snap:
            snap["label"] = it.get("label") or snap["symbol"]
            items.append(snap)

    # rank by 24h volume desc
    items.sort(key=lambda x: (x.get("vol_24h") or 0), reverse=True)

    # compose message
    lines = []
    lines.append(f"<b>币圈早报</b>（北京时间 {now}）")
    lines.append("")
    lines.append("🧭 <b>情绪</b>")
    lines.append(f"• 恐慌指数：<b>{fg_now_v}</b>（{fg_now_c}）｜昨日 {fg_y_v}（{fg_y_c}）｜上周 {fg_w_v}（{fg_w_c}）")
    lines.append("")
    lines.append("🔥 <b>爆量 Meme 观察</b>（按24h成交量）")
    if not items:
        lines.append("• （暂无数据：检查 Dexscreener API 或地址是否正确）")
    else:
        for s in items[: cfg.get("max_meme_items", 5)]:
            vol = fmt_money(s.get("vol_24h"))
            liq = fmt_money(s.get("liq_usd"))
            fdv = fmt_money(s.get("fdv"))
            price = s.get("price_usd")
            price_str = f"${float(price):.6g}" if price is not None else "—"
            lines.append(
                f"• <b>{s['symbol']}</b>（{s['chain']} / {s['dex']}）"
                f"  价 {price_str}｜24h {fmt_pct(s.get('chg_24h'))}"
                f"｜量 {vol}｜流动性 {liq}｜FDV {fdv}｜Txns {s.get('buys',0)+s.get('sells',0)}"
            )
        # include links (plain URLs are okay in Telegram even if preview disabled)
        lines.append("")
        lines.append("🔗 <b>池子链接</b>")
        for s in items[: cfg.get("max_meme_items", 5)]:
            if s.get("pair_url"):
                lines.append(f"• {s['symbol']}: {s['pair_url']}")

    # hot narrative section (manual list you edit)
    lines.append("")
    lines.append("📣 <b>热门叙事/刷屏</b>")
    if topics:
        for t in topics[: cfg.get("max_topics", 5)]:
            # allow either string or dict
            if isinstance(t, dict):
                title = t.get("title", "").strip()
                note = t.get("note", "").strip()
                src = t.get("source", "").strip()
                if src:
                    lines.append(f"• <b>{title}</b>：{note}（{src}）")
                else:
                    lines.append(f"• <b>{title}</b>：{note}")
            else:
                lines.append(f"• {str(t).strip()}")
    else:
        lines.append("• （在 hot_topics.yaml 里填：例如“币安 UTF-8 编码测试→中文 meme 拉升”等）")

    # footer
    lines.append("")
    lines.append("—")
    lines.append("注：Meme 数据来自 Dexscreener（按最液态交易对）；指数来自 Alternative.me。")

    tg_send_html("\n".join(lines))

if __name__ == "__main__":
    main()