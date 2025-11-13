import os
import re
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import yfinance as yf
DEBUG_LOG = []

# ===== 공통 설정 =====
KST = timezone(timedelta(hours=9))


def last_two_closes(ticker):
    t = yf.Ticker(ticker)
    try:
        hist = t.history(period="15d", interval="1d", auto_adjust=False)
        if hist.empty or "Close" not in hist.columns:
            DEBUG_LOG.append(f"[WARN] {ticker}: history empty (len={len(hist)})")
            return np.nan, np.nan
        closes = hist["Close"].dropna()
        if len(closes)==0:
            DEBUG_LOG.append(f"[WARN] {ticker}: closes len=0")
            return np.nan, np.nan
        if len(closes)==1:
            DEBUG_LOG.append(f"[INFO] {ticker}: closes len=1, last={closes.iloc[-1]}")
            return closes.iloc[-1], np.nan
        DEBUG_LOG.append(f"[OK] {ticker}: last={closes.iloc[-1]}, prev={closes.iloc[-2]}")
        return closes.iloc[-1], closes.iloc[-2]
    except Exception as e:
        DEBUG_LOG.append(f"[ERR] {ticker}: {e}")
        return np.nan, np.nan


def px_chg_pct(ticker: str):
    last, prev = last_two_closes(ticker)
    chg = (last - prev) if pd.notna(last) and pd.notna(prev) else np.nan
    pct = (chg / prev * 100) if pd.notna(chg) and pd.notna(prev) and prev != 0 else np.nan
    return last, chg, pct


def build_table(rows):
    df = pd.DataFrame(rows)
    for c in df.columns:
        if c not in ["Ticker", "Name", "Sector"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def krw(value, usdkrw):
    if pd.isna(value) or pd.isna(usdkrw):
        return np.nan
    return value * usdkrw


def fmt1(x):      # 소수점 1자리
    return "" if pd.isna(x) else f"{x:,.1f}"


def fmt_pct1(x):  # 소수점 1자리 + %
    return "" if pd.isna(x) else f"{x:+.1f}%"


def fmt_int(x):   # 정수 천단위
    return "" if pd.isna(x) else f"{int(round(x)):,.0f}"


def format_df_for_report(df: pd.DataFrame) -> str:
    """텍스트 리포트용 포맷 적용한 문자열"""
    out = df.copy()
    for c in out.columns:
        if c in ["Price", "Change", "Yield"]:
            out[c] = out[c].apply(fmt1)
        elif c == "Change %":
            out[c] = out[c].apply(fmt_pct1)
        elif c == "Price_KRW":
            out[c] = out[c].apply(fmt_int)
    # index=False로 깔끔하게
    return out.to_string(index=False)


# ===== 0) 환율 (USD/KRW) =====
usdkrw, _, _ = px_chg_pct("KRW=X")

# ===== 1) 미국 3대 지수 =====
indices = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones"}
rows_idx = []
for t, n in indices.items():
    p, d, pct = px_chg_pct(t)
    rows_idx.append(
        {
            "Ticker": t,
            "Name": n,
            "Price": p,
            "Change": d,
            "Change %": pct,
            "Price_KRW": krw(p, usdkrw),
        }
    )
us_indices_df = build_table(rows_idx)

# ===== 2) 글로벌 주요 지수 =====
global_idx = {
    "^N225": "Nikkei 225",
    "^KS11": "KOSPI",
    "000001.SS": "Shanghai Composite",
    "^HSI": "Hang Seng",
    "^GDAXI": "DAX",
    "^FTSE": "FTSE 100",
}
rows_g = []
for t, n in global_idx.items():
    p, d, pct = px_chg_pct(t)
    rows_g.append(
        {
            "Ticker": t,
            "Name": n,
            "Price": p,
            "Change": d,
            "Change %": pct,
            "Price_KRW": krw(p, usdkrw),
        }
    )
global_indices_df = build_table(rows_g)

# ===== 3) ETF (B 라벨) =====
t1 = {
    "SPY": "S&P500 / 미국 대형주 / 전체시장",
    "QQQ": "Nasdaq100 / 빅테크 중심 / AAPL·MSFT·NVDA",
    "IWM": "러셀2000 / 스몰캡 / 경기민감",
    "DIA": "다우30 / 안정 대형주 / 블루칩",
    "XLK": "IT 섹터 / 성장주 / AAPL·MSFT·AVGO",
    "XLF": "금융 / 은행·보험 / JPM·BAC·GS",
    "XLV": "헬스케어 / 제약·의료 / UNH·LLY·JNJ",
    "XLE": "에너지 / 정유·가스 / XOM·CVX·SLB",
    "XLI": "산업재 / 제조·운송 / CAT·GE·HON",
    "XLB": "소재 / 화학·금속 / LIN·SHW",
    "XLY": "임의소비재 / 소비경기 / AMZN·TSLA·NKE",
    "XLU": "유틸리티 / 방어 / NEE·DUK",
    "XLRE": "리츠 / 상업·데이터센터 / PLD·AMT",
    "XLC": "커뮤니케이션 / 플랫폼·광고 / GOOGL·META",
    "TLT": "미국 장기채 / 금리민감 / 20년+",
    "HYG": "하이일드 채권 / 위험선호 지표",
}
t2 = {
    "EEM": "신흥국 / 광범위 EM",
    "EWY": "한국 / KOSPI 대형주",
    "EWJ": "일본 / 니케이 구성",
    "EFA": "선진국 ex-US / 유럽+일본",
    "VWO": "신흥국 / FTSE EM",
    "FXI": "중국 대형주 / 홍콩 상장",
    "ASHR": "중국 A주 / 본토시장",
    "EWZ": "브라질 / Bovespa 대형주",
    "INDA": "인도 / Nifty50 기반",
}


def table_for(tmap):
    rows = []
    for t, n in tmap.items():
        p, d, pct = px_chg_pct(t)
        rows.append(
            {
                "Ticker": t,
                "Name": n,
                "Price": p,
                "Change": d,
                "Change %": pct,
                "Price_KRW": krw(p, usdkrw),
            }
        )
    return build_table(rows)


etf_us_t1_df = table_for(t1)
etf_global_t2_df = table_for(t2)

# ===== 4) 섹터 성과 요약 =====
sector_map = {k: v for k, v in t1.items() if k.startswith("XL")}
sector_rows = []
for t, n in sector_map.items():
    p, d, pct = px_chg_pct(t)
    sector_rows.append({"Ticker": t, "Sector": n, "Change %": pct})
sector_perf_df = pd.DataFrame(sector_rows).sort_values("Change %", ascending=False)

# ===== 5) 메가캡 =====
mega = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
mega_rows = []
for t in mega:
    p, d, pct = px_chg_pct(t)
    mega_rows.append(
        {
            "Ticker": t,
            "Price": p,
            "Change": d,
            "Change %": pct,
            "Price_KRW": krw(p, usdkrw),
        }
    )
megacaps_df = build_table(mega_rows)

# ===== 6) FX / 금리 / 원자재 =====
fx_map = {
    "KRW=X": "USD/KRW",
    "JPY=X": "USD/JPY",
    "EURUSD=X": "EUR/USD",
    "DX-Y.NYB": "US Dollar Index",
}
rates_map = {
    "^IRX": "US 13W T-Bill (≈3M)",
    "^FVX": "US 5Y",
    "^TNX": "US 10Y",
    "^TYX": "US 30Y",
    "^MOVE": "MOVE (Bond Vol)",
}
cmdty_map = {
    "CL=F": "WTI Crude",
    "BZ=F": "Brent Crude",
    "GC=F": "Gold Futures",
    "BTC-USD": "Bitcoin",
}


def yield_from_yahoo(t, v):
    if t in ["^IRX", "^FVX", "^TNX", "^TYX"] and pd.notna(v):
        return v / 10.0
    return v


fx_rows = []
for t, n in fx_map.items():
    last, prev = last_two_closes(t)
    chg = (last - prev) if pd.notna(last) and pd.notna(prev) else np.nan
    pct = (chg / prev * 100) if pd.notna(chg) and pd.notna(prev) and prev != 0 else np.nan
    fx_rows.append(
        {"Ticker": t, "Name": n, "Price": last, "Change": chg, "Change %": pct}
    )
fx_df = build_table(fx_rows)

rate_rows = []
for t, n in rates_map.items():
    last, prev = last_two_closes(t)
    last_y = yield_from_yahoo(t, last)
    prev_y = yield_from_yahoo(t, prev)
    chg = (last_y - prev_y) if pd.notna(last_y) and pd.notna(prev_y) else np.nan
    pct = (chg / prev_y * 100) if pd.notna(chg) and pd.notna(prev_y) and prev_y != 0 else np.nan
    rate_rows.append(
        {"Ticker": t, "Name": n, "Yield": last_y, "Change": chg, "Change %": pct}
    )
rates_df = build_table(rate_rows)

cmd_rows = []
for t, n in cmdty_map.items():
    p, d, pct = px_chg_pct(t)
    cmd_rows.append(
        {
            "Ticker": t,
            "Name": n,
            "Price": p,
            "Change": d,
            "Change %": pct,
            "Price_KRW": krw(p, usdkrw),
        }
    )
commodities_df = build_table(cmd_rows)

# ===== 7) 텍스트 리포트 조립 =====
now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

sections = []
sections.append(f"전일 종가 브리핑 생성시각: {now_str}\n")

sections.append("===== 1) 미국 3대 지수 =====\n" + format_df_for_report(us_indices_df))
sections.append("===== 2) 글로벌 주요 지수 =====\n" + format_df_for_report(global_indices_df))
sections.append("===== 3) ETF T1 (미국/섹터) =====\n" + format_df_for_report(etf_us_t1_df))
sections.append("===== 3) ETF T2 (글로벌/EM) =====\n" + format_df_for_report(etf_global_t2_df))
sections.append("===== 4) 섹터 성과 요약 =====\n" + format_df_for_report(sector_perf_df))
sections.append("===== 5) 메가캡 =====\n" + format_df_for_report(megacaps_df))
sections.append("===== 6) 환율 =====\n" + format_df_for_report(fx_df))
sections.append("===== 6) 금리 =====\n" + format_df_for_report(rates_df))
sections.append("===== 6) 원자재 =====\n" + format_df_for_report(commodities_df))
sections.append(
    "9) CNN Fear & Greed Index → https://money.cnn.com/data/fear-and-greed/"
)

report_text = "\n\n".join(sections)

# ===== 8) HTML 하이라이트 =====
def highlight_changes(text: str) -> str:
    text = re.sub(r"(\+\d+(\.\d+)?%)", r'<span class="pos">\1</span>', text)
    text = re.sub(r"(-\d+(\.\d+)?%)", r'<span class="neg">\1</span>', text)
    return text


highlighted_report = highlight_changes(report_text)

import re

def highlight_changes(text):
    text = re.sub(r'(\+\d+(\.\d+)?%)', r'<span class="pos">\1</span>', text)
    text = re.sub(r'(-\d+(\.\d+)?%)', r'<span class="neg">\1</span>', text)
    return text

highlighted_report = highlight_changes(report_text)

# 🔽 여기부터 디버그 텍스트 추가
debug_block = ""
if DEBUG_LOG:
    debug_block = "\n\n--- DEBUG ---\n" + "\n".join(DEBUG_LOG) + "\n"

html = f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<title>전일 종가 브리핑</title>
<style>
  body {{
    font-family: 'Pretendard', 'Segoe UI', 'Helvetica', 'Arial', sans-serif;
    background: #f9fafc;
    color: #222;
    padding: 2rem;
    line-height: 1.5;
  }}
  h2 {{
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.5rem;
  }}
  pre {{
    white-space: pre-wrap;
  }}
  .pos {{ color: #d63031; font-weight: bold; }}
  .neg {{ color: #0984e3; font-weight: bold; }}
  footer {{
    margin-top: 2rem;
    font-size: 0.9rem;
    color: #555;
  }}
</style>
<h2>전일 종가 브리핑</h2>
<pre>{highlighted_report}{debug_block}</pre>
<footer>
  ⏰ 자동 생성 시각: {datetime.now().strftime("%Y-%m-%d %H:%M")} KST<br>
  📈 출처: Yahoo Finance / CNN Fear & Greed Index
</footer>
</html>"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ report.txt, docs/index.html 저장 완료")

# ===== 9) 저장 =====
os.makedirs("output", exist_ok=True)
os.makedirs("docs", exist_ok=True)

with open("output/report.txt", "w", encoding="utf-8") as f:
    f.write(report_text)

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ report.txt, docs/index.html 저장 완료")
