from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DASHBOARD_PATH = DATA_DIR / "dashboard_data.json"
TRADES_PATH = DATA_DIR / "trades.json"
HEALTH_PREMIUM_THRESHOLD = 20_000
HEALTH_PREMIUM_RATE = 0.0211


st.set_page_config(
    page_title="00919 監控儀表板",
    page_icon="919",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
      .main .block-container { padding-top: 1.3rem; padding-bottom: 2rem; }
      [data-testid="stSidebar"] { display: none; }
      #MainMenu,
      footer,
      header,
      [data-testid="stToolbar"],
      [data-testid="stDecoration"],
      [data-testid="stStatusWidget"],
      .stDeployButton {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
      }
      [data-testid="stMetricValue"] { font-size: 1.45rem; }
      .status-box {
        border: 1px solid #d9e2df;
        border-radius: 8px;
        padding: 16px 18px;
        background: white;
        margin-bottom: 14px;
      }
      .signal-green { color: #0f8f61; font-weight: 800; }
      .signal-yellow { color: #c78300; font-weight: 800; }
      .signal-red { color: #b42318; font-weight: 800; }
      .small-note { color: #66736f; font-size: 0.92rem; }
      @media (max-width: 760px), (max-height: 520px) and (orientation: landscape), (hover: none) and (pointer: coarse) {
        .main .block-container {
          padding: 0 0.25rem 0.35rem !important;
          max-width: 100%;
        }
        [data-testid="stMainBlockContainer"],
        [data-testid="stAppViewBlockContainer"] {
          padding: 0 !important;
          max-width: 100% !important;
        }
        iframe[title="st.iframe"],
        iframe.stIFrame,
        iframe {
          height: 1320px !important;
          min-height: 0 !important;
        }
        .status-box { display: none; }
        div[data-testid="stMarkdownContainer"]:has(.status-box) { display: none; }
        div[data-testid="stVerticalBlock"] { gap: 0.25rem !important; }
        div[data-testid="stHorizontalBlock"] {
          display: grid !important;
          grid-template-columns: 1fr !important;
          gap: 0 !important;
          margin: 0 8px 6px !important;
          padding: 0 !important;
        }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
          display: none !important;
        }
        div[data-testid="stHorizontalBlock"] button {
          min-height: 40px !important;
          border-radius: 12px !important;
          font-weight: 800 !important;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def optional_password_gate() -> None:
    try:
        password = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        password = ""
    if not password:
        return
    if st.session_state.get("authenticated"):
        return
    st.title("00919 監控儀表板")
    typed = st.text_input("請輸入密碼", type="password")
    if st.button("進入"):
        if typed == password:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("密碼不正確")
    st.stop()


def read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_dashboard() -> dict:
    return read_json(DASHBOARD_PATH, {})


def load_trades() -> list[dict]:
    return read_json(TRADES_PATH, [])


def save_trades(rows: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    TRADES_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def money(value: float | int | None, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{value:,.{digits}f}"


def pct(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{value:.{digits}f}%"


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_trade(row: dict) -> dict:
    return {
        "trade_date": str(row.get("trade_date") or row.get("交易日期") or "").replace("/", "-"),
        "action": str(row.get("action") or row.get("買 / 賣") or row.get("買賣") or "buy").strip(),
        "shares": int(float(row.get("shares") or row.get("交易股數") or 0)),
        "price": float(row.get("price") or row.get("成交價位") or row.get("買入 / 賣出價位") or 0),
        "fee": float(row.get("fee") or row.get("手續費") or 0),
        "tax": float(row.get("tax") or row.get("交易稅") or 0),
        "note_type": str(row.get("note_type") or row.get("分類") or "其他"),
        "note": str(row.get("note") or row.get("自訂備註") or ""),
    }


def calc_shares_on_date(trades: list[dict], target_date: str | None) -> int:
    target = parse_date(target_date)
    if not target:
        return 0
    shares = 0
    for trade in sorted(trades, key=lambda item: item.get("trade_date", "")):
        trade_date = parse_date(trade.get("trade_date"))
        if not trade_date or trade_date > target:
            continue
        qty = int(float(trade.get("shares") or 0))
        if trade.get("action") == "sell" or trade.get("action") == "賣出":
            shares -= qty
        else:
            shares += qty
    return max(shares, 0)


def calc_position(trades: list[dict], dividends: list[dict]) -> dict:
    shares = 0
    cost = 0.0
    realized = 0.0
    first_date = None

    for trade in sorted(trades, key=lambda item: item.get("trade_date", "")):
        qty = int(float(trade.get("shares") or 0))
        price = float(trade.get("price") or 0)
        amount = qty * price
        is_sell = trade.get("action") == "sell" or trade.get("action") == "賣出"
        trade_date = trade.get("trade_date")
        if qty <= 0 or price <= 0:
            continue
        if not is_sell and (first_date is None or trade_date < first_date):
            first_date = trade_date
        if is_sell:
            avg = cost / shares if shares else 0
            cost -= avg * min(qty, shares)
            shares -= qty
            realized += amount - avg * qty
        else:
            shares += qty
            cost += amount

    cumulative_dividend = 0.0
    for div in dividends:
        div_shares = calc_shares_on_date(trades, div.get("ex_date"))
        cumulative_dividend += div_shares * float(div.get("dividend_per_share") or 0)

    return {
        "shares": max(shares, 0),
        "cost": max(cost, 0.0),
        "avg_cost": cost / shares if shares > 0 else 0.0,
        "realized": realized,
        "first_date": first_date or "--",
        "cumulative_dividend": cumulative_dividend,
    }


def latest_monthly_row(data: dict) -> dict:
    rows = [
        row
        for row in data.get("monthly_history", data.get("monthly_size", []))
        if row.get("month")
        and (row.get("aum_100m_twd") is not None or row.get("beneficiary_count") is not None)
    ]
    return sorted(rows, key=lambda item: item.get("month", ""))[-1] if rows else {}


def collect_integrity_warnings(data: dict) -> list[str]:
    latest = data.get("latest_daily", {})
    dividend = data.get("latest_dividend", {})
    monthly = latest_monthly_row(data)
    holdings = data.get("holdings", {})
    warnings = []

    def missing(value) -> bool:
        return value is None or value == "" or (isinstance(value, float) and pd.isna(value))

    checks = [
        ("市價", latest.get("market_price"), "目前市值、未實現損益、含息報酬會失真"),
        ("淨值", latest.get("nav"), "折溢價與淨值線會失真"),
        ("折溢價", latest.get("premium_discount_pct"), "每日燈號會失真"),
        ("成交量", latest.get("volume_lots"), "成交量觀察會缺資料"),
        ("AUM", monthly.get("aum_100m_twd") or monthly.get("aum_million_twd"), "ETF 規模健康會失真"),
        ("受益人數", monthly.get("beneficiary_count"), "受益人數趨勢會失真"),
        ("最新配息", dividend.get("dividend_per_share"), "每季配息與年度配息會失真"),
        ("持股資料", holdings.get("top10"), "前十大集中度與汰換紀錄會缺資料"),
    ]
    for label, value, impact in checks:
        if missing(value) or value == []:
            warnings.append(f"{label}缺漏：{impact}")
    return warnings


def calc_total_signal(data: dict, position: dict, total_return: float) -> tuple[str, str]:
    warnings = collect_integrity_warnings(data)
    if warnings:
        return "red", f"資料完整性：{warnings[0]}"
    latest = data.get("latest_daily", {})
    discount = latest.get("premium_discount_pct")
    if discount is not None and abs(float(discount)) >= 2:
        return "red", f"折溢價 {pct(discount)} 已超過紅燈門檻，請看每日圖表。"
    if discount is not None and abs(float(discount)) >= 1:
        return "yellow", f"折溢價 {pct(discount)} 已超過黃燈門檻，請看每日圖表。"
    if position["cost"] > 0 and total_return < 0:
        return "yellow", "含息損益為負，請到每月頁確認含息報酬趨勢。"
    return "green", "所有數據正常"


def run_update() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, "fetch_data.py"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:
        return False, str(exc)
    output = "\n".join([result.stdout.strip(), result.stderr.strip()]).strip()
    return result.returncode == 0, output or "更新完成"


def sync_static_files() -> None:
    STATIC_DIR.mkdir(exist_ok=True)
    static_assets = STATIC_DIR / "assets"
    static_data = STATIC_DIR / "data"

    if not (STATIC_DIR / "index.html").exists() and (BASE_DIR / "index.html").exists():
        shutil.copy2(BASE_DIR / "index.html", STATIC_DIR / "index.html")

    if not static_assets.exists() and (BASE_DIR / "assets").exists():
        shutil.copytree(BASE_DIR / "assets", static_assets)

    static_data.mkdir(exist_ok=True)
    for source in DATA_DIR.glob("*.json"):
        shutil.copy2(source, static_data / source.name)


def build_embedded_dashboard_html() -> str:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return "<h2>找不到 static/index.html</h2>"

    html = index_path.read_text(encoding="utf-8")
    dashboard_json = json.dumps(load_dashboard(), ensure_ascii=False)
    trades_json = json.dumps(load_trades(), ensure_ascii=False)

    bootstrap = f"""
    <script>
      window.__00919_DASHBOARD_DATA = {dashboard_json};
      window.__00919_TRADES_DATA = {trades_json};
    </script>
    """
    html = html.replace("</head>", f"{bootstrap}</head>", 1)

    def inline_stylesheet(match: re.Match) -> str:
        href = match.group("href").split("?", 1)[0]
        path = STATIC_DIR / href
        if not path.exists():
            return match.group(0)
        css = path.read_text(encoding="utf-8")
        return f"<style>\n{css}\n</style>"

    def inline_script(match: re.Match) -> str:
        src = match.group("src").split("?", 1)[0]
        path = STATIC_DIR / src
        if not path.exists():
            return match.group(0)
        script = path.read_text(encoding="utf-8")
        if src == "assets/app.js":
            script = script.replace(
                "fetch(`data/dashboard_data.json?ts=${Date.now()}`)",
                "Promise.resolve(new Response(JSON.stringify(window.__00919_DASHBOARD_DATA || {}), {status: 200, headers: {'Content-Type': 'application/json'}}))",
            )
            script = script.replace(
                "fetch(`data/trades.json?ts=${Date.now()}`)",
                "Promise.resolve(new Response(JSON.stringify(window.__00919_TRADES_DATA || []), {status: 200, headers: {'Content-Type': 'application/json'}}))",
            )
        return f"<script>\n{script}\n</script>"

    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="(?P<href>assets/[^"]+)"\s*/?>',
        inline_stylesheet,
        html,
    )
    html = re.sub(
        r'<script\s+src="(?P<src>assets/[^"]+)"></script>',
        inline_script,
        html,
    )
    resize_script = """
    <script>
      let frameHeightObserver = null;

      function getDashboardHeightRoot() {
        const mobileHome = document.querySelector(".mobile-home");
        const mobileVisible = mobileHome && window.getComputedStyle(mobileHome).display !== "none";
        if (mobileVisible) return mobileHome;
        return document.querySelector(".app-shell") || document.querySelector(".content") || document.body;
      }

      function sendStreamlitFrameHeight() {
        const root = getDashboardHeightRoot();
        const rect = root ? root.getBoundingClientRect() : { height: 0 };
        const height = Math.ceil(rect.height) + 24;
        window.parent.postMessage(
          { isStreamlitMessage: true, type: "streamlit:setFrameHeight", height },
          "*"
        );
      }

      function observeFrameHeightRoot() {
        if (!("ResizeObserver" in window)) {
          sendStreamlitFrameHeight();
          return;
        }
        if (frameHeightObserver) frameHeightObserver.disconnect();
        const root = getDashboardHeightRoot();
        if (!root) return;
        frameHeightObserver = new ResizeObserver(sendStreamlitFrameHeight);
        frameHeightObserver.observe(root);
        sendStreamlitFrameHeight();
      }

      window.addEventListener("load", sendStreamlitFrameHeight);
      window.addEventListener("load", observeFrameHeightRoot);
      window.addEventListener("resize", observeFrameHeightRoot);
      window.addEventListener("dashboard:rendered", sendStreamlitFrameHeight);
      window.setTimeout(sendStreamlitFrameHeight, 250);
      window.setTimeout(sendStreamlitFrameHeight, 1000);
      window.setTimeout(sendStreamlitFrameHeight, 2500);
    </script>
    """
    html = html.replace("</body>", f"{resize_script}</body>", 1)
    return html


def render_embedded_html_ui() -> None:
    sync_static_files()
    st.markdown(
        """
        <div class="status-box">
          <strong>雲端測試版</strong>
          <div class="small-note">
            下方嵌入的是本機端同一套 HTML 儀表板。雲端更新請按這裡的「更新資料」，
            儀表板內原本的更新按鈕在 Streamlit Cloud 上只會重新讀取資料檔。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1, 5])
    with left:
        if st.button("更新資料", type="primary", use_container_width=True):
            with st.spinner("正在抓取價格、月規模、配息 54C 與前十大持股..."):
                ok, message = run_update()
                if ok:
                    sync_static_files()
                    st.success("資料更新完成")
                    st.rerun()
                st.error("資料更新失敗")
                st.code(message[-2000:])
    with right:
        fetched = load_dashboard().get("fetched_at", "--")
        st.caption(f"目前資料抓取時間：{fetched}")

    components.html(build_embedded_dashboard_html(), height=2600, scrolling=False)


def render_home(data: dict, trades: list[dict]) -> None:
    latest = data.get("latest_daily", {})
    dividend = data.get("latest_dividend", {})
    dividends = data.get("dividends", [])
    position = calc_position(trades, dividends)
    market_price = float(latest.get("market_price") or 0)
    market_value = position["shares"] * market_price
    unrealized = market_value - position["cost"]
    total_return = unrealized + position["cumulative_dividend"] + position["realized"]
    total_return_rate = total_return / position["cost"] * 100 if position["cost"] else 0
    signal, reason = calc_total_signal(data, position, total_return)
    signal_class = f"signal-{signal}"
    monthly = latest_monthly_row(data)
    holdings = data.get("holdings", {})
    top10 = holdings.get("top10", [])
    top10_total = sum(float(row.get("weight_pct") or 0) for row in top10)
    first_holding = top10[0] if top10 else {}
    div_shares = calc_shares_on_date(trades, dividend.get("ex_date"))
    estimated_dividend = div_shares * float(dividend.get("dividend_per_share") or 0)
    estimated_54c = div_shares * float(dividend.get("estimated_54c_per_share") or 0)

    st.title("00919 群益台灣精選高息")
    st.caption(f"資料抓取時間：{data.get('fetched_at', '--')}")

    if st.button("更新資料", type="primary"):
        with st.spinner("正在更新價格、月規模、配息 54C 與前十大持股..."):
            ok, message = run_update()
        if ok:
            st.success("全資料更新完成，頁面將重新載入。")
            st.rerun()
        st.error("更新失敗")
        st.code(message[-2000:])

    st.markdown(
        f"<div class='status-box'><h3 class='{signal_class}'>{'綠燈' if signal == 'green' else '黃燈' if signal == 'yellow' else '紅燈'}</h3><p>{reason}</p></div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1.2, 1.0, 1.0])
    with col1:
        st.subheader("倉位資訊")
        m1, m2, m3 = st.columns(3)
        m1.metric("目前股數", f"{money(position['shares'])} 股")
        m2.metric("平均成本", money(position["avg_cost"], 2))
        m3.metric("最早買進日", position["first_date"])
        m4, m5, m6 = st.columns(3)
        m4.metric("目前市值", f"${money(market_value)}")
        m5.metric("投入本金", f"${money(position['cost'])}")
        m6.metric("含息損益", f"${money(total_return)}", f"{pct(total_return_rate)}")
    with col2:
        st.subheader("股價資訊")
        p1, p2 = st.columns(2)
        p1.metric("市價", money(latest.get("market_price"), 2))
        p2.metric("淨值", money(latest.get("nav"), 2))
        p3, p4 = st.columns(2)
        p3.metric("折溢價", pct(latest.get("premium_discount_pct")))
        p4.metric("成交量", f"{money(latest.get('volume_lots'))} 張")
    with col3:
        st.subheader("資料更新狀態")
        warnings = collect_integrity_warnings(data)
        st.metric("資料完整性", "正常" if not warnings else "需檢查")
        if warnings:
            st.warning(warnings[0])
        else:
            st.success("關鍵欄位完整")

    st.subheader("首頁重點總覽")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("含息報酬", f"${money(total_return)}", pct(total_return_rate))
    f2.metric("最新配息", f"{money(dividend.get('dividend_per_share'), 2)} 元", dividend.get("ex_date", "--"))
    f3.metric("本次 54C", f"${money(estimated_54c)}", f"估配息 ${money(estimated_dividend)}")
    f4.metric("補充保費觀察", "未達" if estimated_54c < HEALTH_PREMIUM_THRESHOLD else "觀察", f"門檻 ${money(HEALTH_PREMIUM_THRESHOLD)}")
    f5, f6, f7, f8 = st.columns(4)
    f5.metric("AUM 規模", f"{money(monthly.get('aum_100m_twd'))} 億" if monthly.get("aum_100m_twd") else "--", monthly.get("month", "--"))
    f6.metric("受益人數", f"{money(monthly.get('beneficiary_count'))} 人" if monthly.get("beneficiary_count") else "--")
    f7.metric("前十大集中度", pct(top10_total), holdings.get("data_date", "--"))
    f8.metric("第一大持股", f"{first_holding.get('name', '--')} {first_holding.get('code', '')}", pct(first_holding.get("weight_pct")))

    st.subheader("市價、淨值、折溢價與成交量")
    daily = pd.DataFrame(data.get("daily", []))
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"])
        recent = daily.tail(30).copy()
        base = alt.Chart(recent).encode(x=alt.X("date:T", title="日期"))
        price_lines = base.transform_fold(
            ["market_price", "nav"], as_=["類型", "價格"]
        ).mark_line(point=True).encode(
            y=alt.Y("價格:Q", title="價格"),
            color=alt.Color("類型:N", title="", scale=alt.Scale(range=["#1f66b3", "#d65a3a"])),
        )
        discount_line = base.mark_line(point=True, strokeDash=[5, 4], color="#6f5cc2").encode(
            y=alt.Y("premium_discount_pct:Q", title="折溢價 %")
        )
        st.altair_chart(price_lines, use_container_width=True)
        if "premium_discount_pct" in recent:
            st.altair_chart(discount_line, use_container_width=True)
    else:
        st.info("尚無每日資料。")


def render_trades(trades: list[dict], data: dict) -> None:
    st.header("交易紀錄")
    st.caption("雲端第一版先用 CSV 匯入 / 匯出。未來再接雲端同步寫入。")
    normalized = [normalize_trade(row) for row in trades]
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["trade_date", "action", "shares", "price", "fee", "tax", "note_type", "note"])
    writer.writeheader()
    writer.writerows(normalized)
    st.download_button("匯出交易 CSV", csv_buffer.getvalue().encode("utf-8-sig"), "00919_trades.csv", "text/csv")

    uploaded = st.file_uploader("匯入交易 CSV", type=["csv"])
    if uploaded is not None:
        text = uploaded.getvalue().decode("utf-8-sig")
        rows = [normalize_trade(row) for row in csv.DictReader(io.StringIO(text))]
        if st.button("合併匯入"):
            existing_keys = {(row.get("trade_date"), row.get("action"), int(row.get("shares") or 0), float(row.get("price") or 0), row.get("note")) for row in normalized}
            merged = normalized[:]
            for row in rows:
                key = (row.get("trade_date"), row.get("action"), int(row.get("shares") or 0), float(row.get("price") or 0), row.get("note"))
                if key not in existing_keys:
                    merged.append(row)
            save_trades(merged)
            st.success("匯入完成")
            st.rerun()

    st.dataframe(pd.DataFrame(normalized), use_container_width=True, hide_index=True)


def render_monthly(data: dict, trades: list[dict]) -> None:
    st.header("每月健康檢查")
    monthly = pd.DataFrame(data.get("monthly_history", []))
    if monthly.empty:
        st.info("尚無月資料。")
        return
    st.dataframe(monthly.sort_values("month", ascending=False), use_container_width=True, hide_index=True)


def render_quarterly(data: dict, trades: list[dict]) -> None:
    st.header("每季配息與 54C")
    rows = []
    for div in data.get("dividends", []):
        shares = calc_shares_on_date(trades, div.get("ex_date"))
        dividend_cash = shares * float(div.get("dividend_per_share") or 0)
        estimated_54c = shares * float(div.get("estimated_54c_per_share") or 0)
        rows.append({
            "除息日": div.get("ex_date"),
            "發放日": div.get("pay_date"),
            "每股配息": div.get("dividend_per_share"),
            "股利所得%": div.get("dividend_income_pct"),
            "收益平準金%": div.get("equalization_pct"),
            "資本利得%": div.get("capital_gain_pct"),
            "當時股數": shares,
            "配息估算": dividend_cash,
            "54C估算": estimated_54c,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_holdings(data: dict) -> None:
    st.header("前十大持股與占比變化")
    holdings = data.get("holdings", {})
    st.caption(f"資料日：{holdings.get('data_date', '--')}")
    top10 = pd.DataFrame(holdings.get("top10", []))
    industries = pd.DataFrame(holdings.get("industries", []))
    if not top10.empty:
        st.bar_chart(top10.set_index("name")["weight_pct"])
        st.dataframe(top10, use_container_width=True, hide_index=True)
    if not industries.empty:
        st.subheader("產業分布")
        st.bar_chart(industries.set_index("name")["weight_pct"])


def render_yearly(data: dict, trades: list[dict]) -> None:
    st.header("年度配息與稅務總覽")
    records: dict[str, dict] = {}
    for div in data.get("dividends", []):
        ex_date = div.get("ex_date", "")
        year = ex_date[:4]
        if not year:
            continue
        shares = calc_shares_on_date(trades, ex_date)
        dividend_cash = shares * float(div.get("dividend_per_share") or 0)
        estimated_54c = shares * float(div.get("estimated_54c_per_share") or 0)
        row = records.setdefault(year, {"年度": year, "配息次數": 0, "年度配息總額": 0.0, "年度54C估算": 0.0})
        row["配息次數"] += 1
        row["年度配息總額"] += dividend_cash
        row["年度54C估算"] += estimated_54c
    table = pd.DataFrame(records.values()).sort_values("年度", ascending=False) if records else pd.DataFrame()
    st.dataframe(table, use_container_width=True, hide_index=True)


def render_manual() -> None:
    st.header("使用說明")
    sop = BASE_DIR / "00919手機監控_出版SOP.md"
    if sop.exists():
        st.markdown(sop.read_text(encoding="utf-8"))
    else:
        st.info("尚未找到 SOP 文件。")


def main() -> None:
    optional_password_gate()
    render_embedded_html_ui()


if __name__ == "__main__":
    main()
