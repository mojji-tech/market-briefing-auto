# -*- coding: utf-8 -*-
# Daily Market Briefing (GitHub Actions용)
# - Yahoo Finance 기반 전일 종가 브리핑
# - 소수점 1자리, KRW 정수 천단위
# - B 라벨, 하이라이팅(+% 빨강 / -% 파랑)
# - docs/index.html + output/report.txt 생성

import yfinance as yf, pandas as pd, numpy as np, re, os
from datetime import datetime, timezone, timedelta

# ----- 기본 설정 -----
KST = timezone(timedelta(hours=9))

def last_two_closes(ticker):
    t = yf.Ticker(ticker)
    hist = t.history(period="15d", interval="1d", auto_adjust=False)
    if hist.empty or "Close" not in hist.columns: return np.nan, np.nan
    closes = hist["Close"].dropna()
    if len(closes)==0: return np.nan, np.nan
    if len(closes)==1: return closes.iloc[-1], np.nan
    return closes.iloc[-1], closes.iloc[-2]

def px_chg_pct(ticker):
    last, prev = last_two_closes(ticker)
    chg = (last-prev) if pd.notna(last) and pd.notna(prev) else np.nan
    pct = (chg/prev*100) if pd.notna(chg) and pd.notna(prev) and prev!=0 else np.nan
    return last, chg, pct

def build_table(rows):
    df = pd.DataFrame(rows)
    num_cols = [c for c in df.columns if c not in ["Name","Ticker","Sector"]]
    for c in num_cols: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def krw(v, usdkrw): 
    return np.nan if pd.isna(v) or pd.isna(usdkrw) else v*usdkrw

def fmt1(x):   # 소수 1자리
    return "" if pd.isna(x) else f"{x:,.1f}"

def fmt_pct1(x):
    return "" if pd.isna(x) else f"{x:+.1f}%"

def fmt_int(x):  # 천단위 정수
    return "" if pd.isna(x) else f"{int(round(x)):,.0f}"

# ----- 데이터 수집 -----
usdkrw,_,_ = px_chg_pct("KRW=X")

# 1) 미국 3대 지수
indices = {"^GSPC":"S&P 500","^IXIC":"Nasdaq","^DJI":"Dow Jones"}
rows_idx=[]
for t,n in indices.items():
    p,d,pct = px_chg_pct(t)
    rows_idx.append({"Ticker":t,"Name":n,"Price":p,"Change":d,"Change %":pct,"Price_KRW":krw(p,usdkrw)})
us_df = build_table(rows_idx)

# 2) 글로벌 지수
global_idx = {
    "^N225":"Nikkei 225","^KS11":"KOSPI","000001.SS":"Shanghai Composite",
    "^HSI":"Hang Seng","^GDAXI":"DAX","^FTSE":"FTSE 100"
}
rows_g=[]
for t,n in global_idx.items():
    p,d,pct = px_chg_pct(t)
    rows_g.append({"Ticker":t,"Name":n,"Price":p,"Change":d,"Change %":pct,"Price_KRW":krw(p,usdkrw)})
g_df = build_table(rows_g)

# 3) ETF (B 라벨)
t1 = {
 "SPY":"S&P500 / 미국 대형주 / 전체시장",
 "QQQ":"Nasdaq100 / 빅테크 중심 / AAPL·MSFT·NVDA",
 "IWM":"러셀2000 / 스몰캡 / 경기민감",
 "DIA":"다우30 / 안정 대형주 / 블루칩",
 "XLK":"IT 섹터 / 성장주 / AAPL·MSFT·AVGO",
 "XLF":"금융 / 은행·보험 / JPM·BAC·GS",
 "XLV":"헬스케어 / 제약·의료 / UNH·LLY·JNJ",
 "XLE":"에너지 / 정유·가스 / XOM·CVX·SLB",
 "XLI":"산업재 / 제조·운송 / CAT·GE·HON",
 "XLB":"소재 / 화학·금속 / LIN·SHW",
 "XLY":"임의소비재 / 소비경기 / AMZN·TSLA·NKE",
 "XLU":"유틸리티 / 방어 / NEE·DUK",
 "XLRE":"리츠 / 상업·데이터센터 / PLD·AMT",
 "XLC":"커뮤니케이션 / 플랫폼·광고 / GOOGL·META",
 "TLT":"미국 장기채 / 금리민감 / 20년+",
 "HYG":"하이일드 채권 / 위험선호 지표"}
t2 = {"EEM":"신흥국 / 광범위 EM","EWY":"한국 / KOSPI 대형주","EWJ":"일본 / 니케이 구성",
       "EFA":"선진국 ex-US / 유럽+일본","VWO":"신흥국 / FTSE EM",
       "FXI":"중국 대형주 / 홍콩 상장","ASHR":"중국 A주 / 본토시장",
       "EWZ":"브라질 / Bovespa 대형주","INDA":"인도 / Nifty50 기반"}

def table_for(m):
    rows=[]
    for t,n in m.items():
        p,d,pct = px_chg_pct(t)
        rows.append({"Ticker":t,"Name":n,"Price":p,"Change":d,"Change %":pct,"Price_KRW":krw(p,usdkrw)})
    return build_table(rows)

t1_df, t2_df = table_for(t1), table_for(t2)

# 4) 섹터 성과 요약
sector = {k:v for k,v in t1.items() if k.startswith("XL")}
rows=[]
for t,n in sector.items():
    p,d,pct = px_chg_pct(t)
    rows.append({"Ticker":t,"Sector":n,"Change %":pct})
sector_df = pd.DataFrame(rows).sort_values("Change %", ascending=False)

# 5) 메가캡
mega = ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA"]
mrows=[]
for t in mega:
    p,d,pct = px_chg_pct(t)
    mrows.append({"Ticker":t,"Price":p,"Change":d,"Change %":pct,"Price_KRW":krw(p,usdkrw)})
mega_df = build_table(mrows)

# 6) FX / 금리 / 원자재
fx_map = {"KRW=X":"USD/KRW","JPY=X":"USD/JPY","EURUSD=X":"EUR/USD","DX-Y.NYB":"US Dollar Index"}
rates = {"^IRX":"US 13W T-Bill (≈3M)","^FVX":"US 5Y","^TNX":"US 10Y","^TYX":"US 30Y","^MOVE":"MOVE (Bond Vol)"}
cmdty = {"CL=F":"WTI Crude","BZ=F":"Brent Crude","GC=F":"Gold Futures","BTC-USD":"Bitcoin"}

def y_yahoo(t, v):  # 야후 수익률 스케일 보정
    return (v/10.0) if (t in ["^IRX","^FVX","^TNX","^TYX"] and pd.notna(v)) else v

fx_rows=[]
for t,n in fx_map.items():
    last, prev = last_two_closes(t)
    chg = (last-prev) if pd.notna(last) and pd.notna(prev) else np.nan
    pct = (chg/prev*100) if pd.notna(chg) and pd.notna(prev) and prev!=0 else np.nan
    fx_rows.append({"Ticker":t,"Name":n,"Price":last,"Change":chg,"Change %":pct})
fx_df = build_table(fx_rows)

rate_rows=[]
for t,n in rates.items():
    last, prev = last_two_closes(t)
    last_y, prev_y = y_yahoo(t,last), y_yahoo(t,prev)
    chg = (last_y - prev_y) if pd.notna(last_y) and pd.notna(prev_y) else np.nan
    pct = (chg/prev_y*100) if pd.notna(chg) and pd.notna(prev_y) and prev_y!=0 else np.nan
    rate_rows.append({"Ticker":t,"Name":n,"Yield":last_y,"Change":chg,"Change %":pct})
rates_df = build_table(rate_rows)

cmd_rows=[]
for t,n in cmdty.items():
    p,d,pct = px_chg_pct(t)
    cmd_rows.append({"Ticker":t,"Name":n,"Price":p,"Change":d,"Change %":pct,"Price_KRW":krw(p,usdkrw)})
cmd_df = build_table(cmd_rows)

# ----- CSV 저장 (포맷 적용) -----
ts = datetime.now(KST).strftime("%Y-%m-%d_%H%M")
tables = {
  "us_indices":us_df, "global_indices":g_df,
  "etf_us_t1":t1_df, "etf_global_t2":t2_df,
  "sector_perf":sector_df, "megacaps":mega_df,
  "fx":fx_df, "rates":rates_df, "commodities":cmd_df
}

for name,df in tables.items():
    df_out = df.copy()
    for c in df_out.columns:
        if c in ["Price","Change","Yield"]: df_out[c] = df_out[c].apply(fmt1)
        if c=="Change %": df_out[c] = df_out[c].apply(fmt_pct1)
        if c=="Price_KRW": df_out[c] = df_out[c].apply(fmt_int)
    df_out.to_csv(f"out_{name}.csv", index=False, encoding="utf-8-sig")

import re, os
from datetime import datetime

# === 리포트 본문 만들기 ===
now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
report_text = f"전일 종가 브리핑 생성시각: {now}\n\n"

def safe_df_to_text(title, df):
    try:
        return f"===== {title} =====\n{df.to_string(index=False)}\n\n"
    except Exception as e:
        return f"===== {title} =====\n(표 변환 실패: {e})\n\n"

# ✅ 실제 존재하는 DF 이름으로 정확히 붙이기
report_text += safe_df_to_text("1) 미국 3대 지수", us_df)
report_text += safe_df_to_text("2) 글로벌 주요 지수", g_df)
report_text += safe_df_to_text("3) ETF T1 (미국/섹터)", t1_df)
report_text += safe_df_to_text("3) ETF T2 (글로벌/EM)", t2_df)
report_text += safe_df_to_text("4) 섹터 성과 요약", sector_df)
report_text += safe_df_to_text("5) 메가캡", mega_df)
report_text += safe_df_to_text("6) 환율", fx_df)
report_text += safe_df_to_text("6) 금리", rates_df)
report_text += safe_df_to_text("6) 원자재", cmd_df)
report_text += "\n9) CNN Fear & Greed Index → https://money.cnn.com/data/fear-and-greed/\n"

# 디렉토리
os.makedirs("output", exist_ok=True)
os.makedirs("docs", exist_ok=True)

# === 하이라이팅 ===
def highlight_changes(text):
    text = re.sub(r'(\+\d+(\.\d+)?%)', r'<span class="pos">\1</span>', text)  # 상승
    text = re.sub(r'(-\d+(\.\d+)?%)', r'<span class="neg">\1</span>', text)  # 하락
    return text

highlighted_report = highlight_changes(report_text)

# === HTML 저장 ===
html = f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<title>전일 종가 브리핑</title>
<style>
  body {{
    font-family: 'Pretendard','Segoe UI','Helvetica','Arial',sans-serif;
    background:#f9fafc; color:#222; padding:2rem; line-height:1.5;
  }}
  h2 {{ color:#2c3e50; border-bottom:2px solid #3498db; padding-bottom:.5rem; }}
  pre {{ font-family:'JetBrains Mono','Consolas',monospace; font-size:.9rem; white-space:pre-wrap; }}
  .pos {{ color:#d63031; font-weight:bold; }}
  .neg {{ color:#0984e3; font-weight:bold; }}
  footer {{ margin-top:2rem; font-size:.9rem; color:#555; }}
</style>
<h2>전일 종가 브리핑</h2>
<pre>{highlighted_report}</pre>
<footer>
  ⏰ 자동 생성 시각: {datetime.now().strftime("%Y-%m-%d %H:%M")} KST<br>
  📈 출처: Yahoo Finance / CNN Fear & Greed Index
</footer>
</html>"""

with open("output/report.txt", "w", encoding="utf-8") as f:
    f.write(report_text)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ report.txt, docs/index.html 저장 완료 (표+하이라이트 반영)")
