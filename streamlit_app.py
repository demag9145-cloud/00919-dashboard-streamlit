from __future__ import annotations

import csv
import base64
import html
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

GOOGLE_SHEETS_IMPORT_ERROR = ""
try:
    from services.google_sheets_trades import (
        append_trade_to_google_sheets,
        load_google_sheets_trades,
        test_append_trade_directly,
    )
except Exception as exc:  # Keep the formal app usable even if optional cloud deps are absent locally.
    GOOGLE_SHEETS_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    append_trade_to_google_sheets = None
    load_google_sheets_trades = None
    test_append_trade_directly = None


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DASHBOARD_PATH = DATA_DIR / "dashboard_data.json"
TRADES_PATH = DATA_DIR / "trades.json"
DAILY_HISTORY_PATH = DATA_DIR / "daily_history.json"
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
      /* UI19: remove Streamlit's empty top spacer above the dashboard iframe. */
      html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
      }
      [data-testid="stHeader"], header, [data-testid="stToolbar"], .stDeployButton {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        min-height: 0 !important;
      }
      [data-testid="stMainBlockContainer"],
      [data-testid="stAppViewBlockContainer"],
      .main .block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
      }
      div[data-testid="stVerticalBlock"] {
        gap: 0.35rem !important;
      }
      .main .block-container { padding-top: 0 !important; padding-bottom: 2rem; }
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
      @media (min-width: 761px) {
        .main .block-container {
          padding-top: 0 !important;
          padding-bottom: 0.75rem !important;
        }
        .status-box,
        div[data-testid="stMarkdownContainer"]:has(.status-box) {
          display: none !important;
        }
        div[data-testid="stHorizontalBlock"] {
          margin: 0 0 0.75rem !important;
          gap: 0.75rem !important;
          align-items: center !important;
        }
        div[data-testid="stHorizontalBlock"] button {
          min-height: 42px !important;
          border-radius: 12px !important;
          font-size: 0.98rem !important;
          font-weight: 800 !important;
          background: #059669 !important;
          color: #ffffff !important;
          border: 0 !important;
        }
        div[data-testid="stHorizontalBlock"] button:hover {
          background: #047857 !important;
          color: #ffffff !important;
        }
      }
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
          min-height: 0 !important;
          margin-bottom: 0 !important;
        }
        div[data-testid="stElementContainer"]:has(iframe[title="st.iframe"]),
        div[data-testid="stElementContainer"]:has(iframe.stIFrame),
        div[data-testid="stElementContainer"]:has(iframe) {
          min-height: 0 !important;
          margin-bottom: 0 !important;
          padding-bottom: 0 !important;
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


def load_trades_with_source() -> tuple[list[dict], dict]:
    if load_google_sheets_trades is not None:
        try:
            result = load_google_sheets_trades()
            return result.rows, {
                "source": result.source,
                "ok": True,
                "message": result.message,
            }
        except Exception as exc:
            fallback = read_json(TRADES_PATH, [])
            return fallback, {
                "source": "data/trades.json",
                "ok": False,
                "message": f"Google Sheets 失敗，改用 data/trades.json fallback：{type(exc).__name__}",
            }

    fallback = read_json(TRADES_PATH, [])
    return fallback, {
        "source": "data/trades.json",
        "ok": False,
        "message": "Google Sheets 模組未載入，改用 data/trades.json fallback" + (f"（{GOOGLE_SHEETS_IMPORT_ERROR}）" if GOOGLE_SHEETS_IMPORT_ERROR else ""),
    }


def load_trades() -> list[dict]:
    rows, _ = load_trades_with_source()
    return rows


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


def _has_number(value) -> bool:
    if value is None or value == "":
        return False
    try:
        return pd.notna(float(value))
    except Exception:
        return False


def latest_market_daily_row(data: dict) -> dict:
    rows = data.get("daily", []) or []
    for row in reversed(rows):
        if _has_number(row.get("market_price")):
            return row
    return data.get("latest_daily", {}) or {}


def latest_complete_daily_row(data: dict) -> dict:
    latest = data.get("latest_daily", {}) or {}
    if (
        latest.get("date")
        and _has_number(latest.get("market_price"))
        and _has_number(latest.get("nav"))
        and _has_number(latest.get("premium_discount_pct"))
    ):
        return latest
    rows = data.get("daily", []) or []
    for row in reversed(rows):
        if (
            row.get("date")
            and _has_number(row.get("market_price"))
            and _has_number(row.get("nav"))
            and _has_number(row.get("premium_discount_pct"))
        ):
            return row
    return latest


def collect_integrity_warnings(data: dict) -> list[str]:
    # UI25: 市價可用最新交易日；淨值/折溢價改用最近一筆完整資料。
    # 例如市價到 5/29、淨值與折溢價到 5/28，屬 ETF NAV 正常延遲，不應直接判成燈號異常。
    latest_market = latest_market_daily_row(data)
    latest_complete = latest_complete_daily_row(data)
    dividend = data.get("latest_dividend", {})
    monthly = latest_monthly_row(data)
    holdings = data.get("holdings", {})
    warnings = []

    def missing(value) -> bool:
        return value is None or value == "" or (isinstance(value, float) and pd.isna(value))

    checks = [
        ("市價", latest_market.get("market_price"), "目前市值、未實現損益、含息報酬會失真"),
        ("淨值", latest_complete.get("nav"), "折溢價與淨值線會失真"),
        ("折溢價", latest_complete.get("premium_discount_pct"), "每日燈號會失真"),
        ("成交量", latest_market.get("volume_lots") or latest_complete.get("volume_lots"), "成交量觀察會缺資料"),
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
    # 只有資料真的嚴重缺漏時，才讓原生交易頁 Hero 進入紅燈；一般完整性提醒不再誤拉黃燈。
    if warnings:
        return "red", f"資料完整性：{warnings[0]}"
    latest = latest_complete_daily_row(data)
    discount = latest.get("premium_discount_pct")
    if discount is not None and abs(float(discount)) >= 2:
        return "red", f"折溢價 {pct(discount)} 已超過紅燈門檻，請看每日圖表。"
    if discount is not None and abs(float(discount)) >= 1:
        return "yellow", f"折溢價 {pct(discount)} 已超過黃燈門檻，請看每日圖表。"
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


def consume_embedded_update_request() -> None:
    if st.query_params.get("run_update") != "1":
        return

    with st.spinner("更新資料中，正在抓取價格、月規模、配息 54C 與前十大持股..."):
        ok, message = run_update()

    st.query_params.clear()
    if ok:
        sync_static_files()
        st.session_state["last_update_message"] = "資料已更新"
        st.rerun()

    st.error("資料更新失敗")
    st.code(message[-2000:])


def google_sheets_write_help() -> str:
    return (
        "寫入 Google Sheets 失敗。可能原因：Service Account 尚未加入 Google Sheet 共用、"
        "Service Account 不是編輯者、Google API scope 仍是 readonly、"
        "GOOGLE_SHEET_ID 錯誤，或 Trades 工作表不存在。"
    )


def log_append_debug(message: str) -> None:
    print(f"[00919 append] {message}")


def render_google_sheets_trade_form(status_message: str | None = None, show_title: bool = True) -> None:
    if append_trade_to_google_sheets is None:
        st.warning("Google Sheets 寫入模組尚未啟用；目前只能讀取既有交易資料。")
        return

    st.markdown(
        """
        <style>
          .streamlit-trade-form-shell {
            margin: 12px 0 14px;
            padding: 0;
          }
          .streamlit-trade-form-title {
            margin: 0 0 8px;
            color: #0f172a;
            font-size: 1.2rem;
            font-weight: 800;
          }
          div[data-testid="stForm"] {
            border: 1px solid #d9e2df;
            border-radius: 14px;
            padding: 14px 16px 16px;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
          }
          div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
            background: #059669;
            border: 0;
            border-radius: 10px;
            color: #ffffff;
            font-weight: 800;
            min-height: 42px;
          }
          div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
            background: #047857;
            color: #ffffff;
          }
          .trade-form-panel-note {
            margin: 0 0 12px;
            padding: 10px 12px;
            border: 1px solid #bfdbfe;
            border-radius: 10px;
            background: #eff6ff;
            color: #1e3a8a;
            font-size: 0.92rem;
          }
          .trade-form-status {
            margin: 0 0 10px;
            padding: 10px 12px;
            border: 1px solid #bbf7d0;
            border-radius: 10px;
            background: #f0fdf4;
            color: #166534;
            font-size: 0.92rem;
            font-weight: 700;
          }
          @media (max-width: 760px) {
            .streamlit-trade-form-shell,
            div[data-testid="stForm"] {
              display: none !important;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='streamlit-trade-form-shell'>", unsafe_allow_html=True)
    if show_title:
        st.markdown("<div class='streamlit-trade-form-title'>新增交易</div>", unsafe_allow_html=True)
    if status_message:
        st.markdown(
            f"<div class='trade-form-status'>{html.escape(status_message)}，資料已重新讀取。</div>",
            unsafe_allow_html=True,
        )

    with st.form("google_sheets_trade_append_form", clear_on_submit=True):
        row1 = st.columns([1.0, 1.25, 1.1, 1.1])
        action_label = row1[0].radio("交易類型", ["買入", "賣出"], horizontal=True)
        trade_date_value = row1[1].date_input("交易日期", value=date.today())
        shares = row1[2].number_input("交易股數", min_value=1, step=1, value=1)
        price = row1[3].number_input("成交價", min_value=0.0, step=0.01, value=0.0, format="%.2f")

        row2 = st.columns([1.2, 2.8])
        note_type = row2[0].selectbox(
            "備註分類",
            ["其他", "測試", "定期買入", "加碼", "減碼", "配息再投入", "手動修正"],
        )
        note = row2[1].text_input("備註", placeholder="例如：streamlit form test")

        submitted = st.form_submit_button("新增並寫入 Google Sheets", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        return

    action = "BUY" if action_label == "買入" else "SELL"
    if not trade_date_value or int(shares) <= 0 or float(price) <= 0 or action not in {"BUY", "SELL"}:
        st.error("寫入 Google Sheets 失敗：請確認日期、股數與成交價都已正確填寫。")
        return

    trade = {
        "trade_date": trade_date_value.strftime("%Y-%m-%d"),
        "action": action,
        "shares": int(shares),
        "price": float(price),
        "note_type": note_type,
        "note": note.strip(),
        "source": "streamlit_form",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        append_trade_to_google_sheets(trade)
    except Exception as exc:
        log_append_debug(f"streamlit form append failed: {type(exc).__name__}: {exc}")
        st.error("寫入 Google Sheets 失敗")
        st.info(google_sheets_write_help())
        st.code(f"{type(exc).__name__}: {exc}")
        return

    log_append_debug(
        "streamlit form append success "
        f"trade_date={trade['trade_date']} action={trade['action']} "
        f"shares={trade['shares']} price={trade['price']}"
    )
    st.session_state["last_update_message"] = "新增交易已寫入 Google Sheets"
    st.rerun()


def trades_to_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["trade_date", "action", "shares", "price", "note_type", "note"])
    writer.writeheader()
    for row in rows:
        normalized = normalize_trade(row)
        writer.writerow(
            {
                "trade_date": normalized.get("trade_date", ""),
                "action": str(normalized.get("action", "")).upper(),
                "shares": normalized.get("shares", 0),
                "price": normalized.get("price", 0),
                "note_type": normalized.get("note_type", ""),
                "note": normalized.get("note", ""),
            }
        )
    return output.getvalue()



def render_native_trade_log_section(status_message: str | None = None) -> None:
    """Render the native Streamlit trade page without relying on open HTML wrappers.

    UI5 used a long <section> wrapper split across several st.markdown/widgets.
    In Streamlit this can be fragile and may leave the actual form/table invisible
    after the hero. This version renders every HTML block as a complete fragment,
    then places Streamlit widgets between them.
    """
    dashboard = load_dashboard()
    trades, trades_source = load_trades_with_source()
    dividends = dashboard.get("dividends", [])
    latest = dashboard.get("latest_daily", {})
    market_price = float(latest.get("market_price") or 0)
    position = calc_position(trades, dividends)
    market_value = position["shares"] * market_price
    unrealized = market_value - position["cost"]
    total_return = unrealized + position["cumulative_dividend"] + position["realized"]

    st.markdown(
        """
        <style>
          .native-trade-zone {
            margin: 0 0 18px;
          }
          .native-trade-card {
            border: 1px solid #d9e2df;
            border-radius: 14px;
            background: #ffffff;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
            overflow: hidden;
          }
          .native-trade-card__inner {
            padding: 16px;
          }
          .native-trade-head {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: flex-start;
            margin-bottom: 14px;
          }
          .native-trade-head p {
            margin: 0;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
          }
          .native-trade-head h3 {
            margin: 2px 0 0;
            color: #0f172a;
            font-size: 1.25rem;
            font-weight: 900;
          }
          .native-trade-head small {
            color: #64748b;
            font-size: 0.9rem;
            line-height: 1.45;
          }
          .native-trade-stats {
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 10px;
            margin: 0 0 14px;
          }
          .native-trade-stat {
            min-height: 72px;
            padding: 12px 14px;
            border: 1px solid #d9e2df;
            border-radius: 10px;
            background: #fbfcfc;
          }
          .native-trade-stat span {
            display: block;
            color: #64748b;
            font-size: 0.84rem;
            font-weight: 750;
            margin-bottom: 6px;
          }
          .native-trade-stat strong {
            color: #0f172a;
            font-size: 1.12rem;
            font-weight: 950;
            white-space: nowrap;
          }
          .native-trade-stat strong.positive { color: #059669; }
          .native-trade-stat strong.negative { color: #dc2626; }
          .native-trade-status {
            margin: 0 0 12px;
            padding: 10px 12px;
            border: 1px solid #bbf7d0;
            border-radius: 10px;
            background: #f0fdf4;
            color: #166534;
            font-size: 0.92rem;
            font-weight: 800;
          }
          .native-trade-panel-title {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            margin: 12px 0 8px;
            padding: 0 2px;
          }
          .native-trade-panel-title strong {
            color: #0f172a;
            font-size: 1rem;
            font-weight: 900;
          }
          .native-trade-panel-title small {
            color: #64748b;
            font-size: 0.86rem;
          }
          .native-trade-form-scope div[data-testid="stForm"] {
            border: 1px solid #d9e2df;
            border-radius: 12px;
            padding: 14px 16px 16px;
            background: #fbfcfc;
            box-shadow: none;
            margin-bottom: 12px;
          }
          .native-trade-form-scope div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
            background: #059669 !important;
            border: 0 !important;
            border-radius: 10px !important;
            color: #ffffff !important;
            font-weight: 900 !important;
            min-height: 42px !important;
          }
          .native-trade-form-scope div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
            background: #047857 !important;
            color: #ffffff !important;
          }
          .native-trade-table-wrap {
            max-height: 360px;
            overflow: auto;
            border: 1px solid #d9e2df;
            border-radius: 10px;
            margin-top: 8px;
            background: #ffffff;
          }
          .native-trade-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.94rem;
          }
          .native-trade-table th,
          .native-trade-table td {
            padding: 12px 14px;
            border-bottom: 1px solid #e6ecea;
            text-align: left;
            white-space: nowrap;
          }
          .native-trade-table th {
            position: sticky;
            top: 0;
            z-index: 1;
            background: #eef3f2;
            color: #475569;
            font-weight: 850;
          }
          .native-trade-table td { color: #0f172a; }
          .native-trade-badge {
            display: inline-flex;
            padding: 4px 8px;
            border-radius: 999px;
            background: #e8f8f0;
            color: #059669;
            font-weight: 900;
            font-size: 0.82rem;
          }
          .native-trade-badge.sell { background: #fff1f2; color: #e11d48; }
          .native-trade-source {
            color: #64748b;
            font-size: 0.82rem;
            margin-top: 8px;
          }
          .native-trade-download-row {
            margin-top: 10px;
          }
          div[data-testid="stDownloadButton"] button {
            min-height: 34px;
            border-radius: 8px;
            border: 1px solid #d9e2df;
            background: #ffffff;
            color: #0f172a;
            font-weight: 800;
          }
          @media (max-width: 1300px) {
            .native-trade-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
          }
          @media (max-width: 980px) {
            .native-trade-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .native-trade-head { flex-direction: column; }
          }
          @media (max-width: 760px) {
            .native-trade-zone { display: none !important; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    stats = [
        ("目前股數", f"{money(position['shares'])} 股", ""),
        ("平均成本", money(position["avg_cost"], 2), ""),
        ("投入本金", f"${money(position['cost'])}", ""),
        ("累積配息估算", f"${money(position['cumulative_dividend'])}", ""),
        ("目前市值", f"${money(market_value)}", ""),
        ("未實現損益", f"${money(unrealized)}", "positive" if unrealized >= 0 else "negative"),
        ("含息損益估算", f"${money(total_return)}", "positive" if total_return >= 0 else "negative"),
    ]
    stats_html = "".join(
        f"<div class='native-trade-stat'><span>{label}</span><strong class='{tone}'>{value}</strong></div>"
        for label, value, tone in stats
    )
    status_html = (
        f"<div class='native-trade-status'>{html.escape(status_message)}，資料已重新讀取。</div>"
        if status_message
        else ""
    )
    st.markdown(
        f"""
        <div class="native-trade-zone native-trade-card">
          <div class="native-trade-card__inner">
            <div class="native-trade-head">
              <div>
                <p>Trade Log</p>
                <h3>交易紀錄</h3>
              </div>
              <small>交易紀錄會驅動首頁股數、成本與含息損益。正式資料來源為 Google Sheets。</small>
            </div>
            <div class="native-trade-stats">{stats_html}</div>
            {status_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="native-trade-zone native-trade-card native-trade-form-scope">
          <div class="native-trade-card__inner">
            <div class="native-trade-panel-title">
              <strong>新增交易</strong>
              <small>資料將直接寫入 Google Sheets，所有裝置會同步更新。</small>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Native Streamlit form: render as real widgets, not inside a split HTML wrapper.
    # Keep the inputs visible even when Google Sheets dependencies are missing, so the
    # page never looks empty; the submit handler will show the actual setup error.
    if append_trade_to_google_sheets is None:
        detail = f"（{GOOGLE_SHEETS_IMPORT_ERROR}）" if GOOGLE_SHEETS_IMPORT_ERROR else ""
        st.warning(
            "Google Sheets 寫入模組尚未啟用；表單先保留顯示。"
            "請確認已安裝 gspread / google-auth，且 Streamlit secrets 已設定。" + detail
        )

    with st.form("google_sheets_trade_append_form_native", clear_on_submit=True):
        row1 = st.columns([1.0, 1.25, 1.1, 1.1])
        action_label = row1[0].radio("買 / 賣", ["買入", "賣出"], horizontal=True)
        trade_date_value = row1[1].date_input("交易日期", value=date.today())
        shares = row1[2].number_input("交易股數（股）", min_value=1, step=1, value=1)
        price = row1[3].number_input("平均成本 / 成交價", min_value=0.0, step=0.01, value=0.0, format="%.2f")

        row2 = st.columns([1.25, 2.75])
        note_type = row2[0].selectbox(
            "買入理由 / 備註分類",
            ["股息再投入", "薪資投入", "年終投入", "定期投入", "閒置資金投入", "再平衡調整", "部位調整", "其他"],
        )
        note = row2[1].text_input("備註", placeholder="可留空或補充說明，例如：首次買進、定期投入、加碼原因")
        submitted = st.form_submit_button("新增交易並寫入 Google Sheets", use_container_width=True)

    if submitted:
        action = "BUY" if action_label == "買入" else "SELL"
        if not trade_date_value or int(shares) <= 0 or float(price) <= 0 or action not in {"BUY", "SELL"}:
            st.error("寫入 Google Sheets 失敗：請確認日期、股數與成交價都已正確填寫。")
        elif append_trade_to_google_sheets is None:
            st.error("寫入 Google Sheets 失敗：Google Sheets 寫入模組尚未啟用。")
            st.info("請先安裝 requirements.txt 內的 gspread / google-auth，並確認 .streamlit/secrets.toml 已包含 gcp_service_account 與 GOOGLE_SHEET_ID。" + (f"目前錯誤：{GOOGLE_SHEETS_IMPORT_ERROR}" if GOOGLE_SHEETS_IMPORT_ERROR else ""))
        else:
            trade = {
                "trade_date": trade_date_value.strftime("%Y-%m-%d"),
                "action": action,
                "shares": int(shares),
                "price": float(price),
                "note_type": note_type,
                "note": note.strip(),
                "source": "streamlit_form",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            try:
                append_trade_to_google_sheets(trade)
            except Exception as exc:
                log_append_debug(f"streamlit native form append failed: {type(exc).__name__}: {exc}")
                st.error("寫入 Google Sheets 失敗")
                st.info(google_sheets_write_help())
                st.code(f"{type(exc).__name__}: {exc}")
            else:
                log_append_debug(
                    "streamlit native form append success "
                    f"trade_date={trade['trade_date']} action={trade['action']} "
                    f"shares={trade['shares']} price={trade['price']}"
                )
                st.session_state["last_update_message"] = "新增交易已寫入 Google Sheets"
                st.rerun()

    sorted_trades = sorted([normalize_trade(row) for row in trades], key=lambda row: row.get("trade_date", ""), reverse=True)
    table_rows = []
    for row in sorted_trades:
        shares_i = int(row.get("shares") or 0)
        price_f = float(row.get("price") or 0)
        action = str(row.get("action") or "").lower()
        is_sell = action == "sell"
        action_label = "賣出" if is_sell else "買入"
        table_rows.append(
            "<tr>"
            f"<td><span class='native-trade-badge {'sell' if is_sell else ''}'>{action_label}</span></td>"
            f"<td>{html.escape(row.get('trade_date') or '--')}</td>"
            f"<td>{money(shares_i)} 股</td>"
            f"<td>{money(price_f, 2)}</td>"
            f"<td>${money(shares_i * price_f)}</td>"
            f"<td>{html.escape(row.get('note_type') or '')}</td>"
            f"<td>{html.escape(row.get('note') or '')}</td>"
            "</tr>"
        )
    if not table_rows:
        table_rows.append("<tr><td colspan='7'>尚無交易紀錄。</td></tr>")

    st.markdown(
        """
        <div class="native-trade-zone native-trade-card">
          <div class="native-trade-card__inner">
            <div class="native-trade-panel-title">
              <strong>Google Sheets 交易紀錄表格</strong>
              <small>資料多時表格內部捲動，不把整頁往下撐太長。</small>
            </div>
            <div class="native-trade-table-wrap">
              <table class="native-trade-table">
                <thead>
                  <tr>
                    <th>買 / 賣</th>
                    <th>交易日期</th>
                    <th>交易股數</th>
                    <th>成交價位</th>
                    <th>交易金額</th>
                    <th>分類</th>
                    <th>自訂備註</th>
                  </tr>
                </thead>
                <tbody>
        """
        + "".join(table_rows)
        + f"""
                </tbody>
              </table>
            </div>
            <div class="native-trade-source">{html.escape(trades_source.get('message', ''))}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    template_data = "trade_date,action,shares,price,note_type,note\n2026-05-27,BUY,1000,27.00,其他,範例\n"
    st.markdown('<div class="native-trade-zone native-trade-download-row">', unsafe_allow_html=True)
    action_cols = st.columns([1, 1, 5])
    with action_cols[0]:
        st.download_button("匯出資料", trades_to_csv(trades), "00919_trades.csv", "text/csv", use_container_width=True)
    with action_cols[1]:
        st.download_button("下載範本", template_data, "00919_trade_template.csv", "text/csv", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("匯入資料：上傳 CSV 範本到 Google Sheets", expanded=True):
        st.caption("可先下載範本填寫，再上傳 CSV；匯入後會寫入 Google Sheets，重新整理後首頁與交易頁會同步。若你直接在 Google Sheets 新增交易，也只要回到 Dashboard 重新整理或按更新資料即可讀到最新資料。")
        uploaded_trades = st.file_uploader("選擇交易 CSV 檔", type=["csv"], key="native_trade_csv_importer")
        preview_rows: list[dict] = []
        if uploaded_trades is not None:
            try:
                text = uploaded_trades.getvalue().decode("utf-8-sig")
                preview_rows = [normalize_trade(row) for row in csv.DictReader(io.StringIO(text))]
                valid_preview_rows = [row for row in preview_rows if row.get("trade_date") and int(row.get("shares") or 0) > 0 and float(row.get("price") or 0) > 0]
                st.info(f"已讀取 {len(preview_rows)} 筆，其中 {len(valid_preview_rows)} 筆格式可匯入。")
                if valid_preview_rows:
                    preview_table = []
                    for row in valid_preview_rows[:8]:
                        preview_table.append({
                            "交易日期": row.get("trade_date"),
                            "買 / 賣": "賣出" if str(row.get("action") or "").lower() in {"sell", "s", "賣", "賣出"} else "買入",
                            "股數": int(row.get("shares") or 0),
                            "價格": float(row.get("price") or 0),
                            "分類": row.get("note_type") or "其他",
                            "備註": row.get("note") or "",
                        })
                    st.dataframe(preview_table, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error("CSV 讀取失敗，請確認欄位名稱與編碼。")
                st.code(f"{type(exc).__name__}: {exc}")

        import_cols = st.columns([1, 5])
        do_import = import_cols[0].button("確認匯入到 Google Sheets", type="primary", use_container_width=True)
        if do_import:
            if uploaded_trades is None:
                st.error("請先選擇 CSV 檔案。")
            elif append_trade_to_google_sheets is None:
                st.error("目前 Google Sheets 寫入模組尚未啟用，無法匯入到正式資料庫。")
                st.info("請先執行 pip install -r requirements.txt，並確認 .streamlit/secrets.toml 已設定。" + (f"目前錯誤：{GOOGLE_SHEETS_IMPORT_ERROR}" if GOOGLE_SHEETS_IMPORT_ERROR else ""))
            else:
                try:
                    text = uploaded_trades.getvalue().decode("utf-8-sig")
                    imported_rows = [normalize_trade(row) for row in csv.DictReader(io.StringIO(text))]
                    imported_rows = [row for row in imported_rows if row.get("trade_date") and int(row.get("shares") or 0) > 0 and float(row.get("price") or 0) > 0]
                    existing_keys = {
                        (
                            str(row.get("trade_date") or ""),
                            "sell" if str(row.get("action") or "").lower() in {"sell", "s", "賣", "賣出"} else "buy",
                            int(row.get("shares") or 0),
                            round(float(row.get("price") or 0), 4),
                            str(row.get("note") or ""),
                        )
                        for row in sorted_trades
                    }
                    appended_count = 0
                    skipped_count = 0
                    for row in imported_rows:
                        action_norm = "sell" if str(row.get("action") or "").lower() in {"sell", "s", "賣", "賣出"} else "buy"
                        key = (
                            str(row.get("trade_date") or ""),
                            action_norm,
                            int(row.get("shares") or 0),
                            round(float(row.get("price") or 0), 4),
                            str(row.get("note") or ""),
                        )
                        if key in existing_keys:
                            skipped_count += 1
                            continue
                        append_trade_to_google_sheets({
                            "trade_date": row.get("trade_date"),
                            "action": "SELL" if action_norm == "sell" else "BUY",
                            "shares": int(row.get("shares") or 0),
                            "price": float(row.get("price") or 0),
                            "note_type": row.get("note_type") or "其他",
                            "note": row.get("note") or "",
                            "source": "csv_import",
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                        })
                        existing_keys.add(key)
                        appended_count += 1
                    st.session_state["last_update_message"] = f"匯入完成：新增 {appended_count} 筆，略過重複 {skipped_count} 筆"
                    st.rerun()
                except Exception as exc:
                    st.error("匯入失敗")
                    st.code(f"{type(exc).__name__}: {exc}")


def consume_direct_append_test_request() -> None:
    if st.query_params.get("test_append_trade") != "1":
        return

    try:
        if test_append_trade_directly is None:
            raise RuntimeError("Google Sheets 直接寫入測試模組未載入")
        log_append_debug("direct append test start")
        test_append_trade_directly()
        log_append_debug("direct append test success")
        st.query_params.clear()
        st.success("後端直接 append 測試成功，請到 Google Sheets Trades 最後一列確認。")
        st.stop()
    except Exception as exc:
        log_append_debug(f"direct append test failed: {type(exc).__name__}: {exc}")
        st.query_params.clear()
        st.error("後端直接 append 測試失敗")
        st.info(google_sheets_write_help())
        st.code(f"{type(exc).__name__}: {exc}")
        st.stop()


def consume_embedded_trade_append_request() -> None:
    payload = st.query_params.get("append_trade")
    if not payload:
        return

    try:
        if append_trade_to_google_sheets is None:
            raise RuntimeError("Google Sheets 寫入模組未載入")

        padded = payload + ("=" * (-len(payload) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        trade = json.loads(decoded)
        if not isinstance(trade, dict):
            raise ValueError("新增交易資料格式錯誤")

        normalized = normalize_trade(trade)
        client_request_id = str(trade.get("client_request_id") or "").strip()
        processed = st.session_state.setdefault("processed_append_trade_ids", set())
        if client_request_id and client_request_id in processed:
            log_append_debug(f"skip duplicate append_trade request client_request_id={client_request_id}")
            st.query_params.clear()
            st.rerun()

        log_append_debug(
            "received append_trade request "
            f"trade_date={normalized.get('trade_date')} "
            f"action={normalized.get('action')} "
            f"shares={normalized.get('shares')} "
            f"price={normalized.get('price')}"
        )
        log_append_debug("append_trade_to_google_sheets start")
        append_payload = {**normalized, "client_request_id": client_request_id}
        append_trade_to_google_sheets(append_payload)
        if client_request_id:
            processed.add(client_request_id)
        log_append_debug("append_trade_to_google_sheets success")
        st.query_params.clear()
        st.session_state["last_update_message"] = "新增交易已寫入 Google Sheets"
        st.rerun()
    except Exception as exc:
        log_append_debug(f"append_trade_to_google_sheets failed: {type(exc).__name__}: {exc}")
        st.query_params.clear()
        st.error("寫入 Google Sheets 失敗")
        st.info(google_sheets_write_help())
        st.code(f"{type(exc).__name__}: {exc}")
        st.stop()


def consume_embedded_trade_sync_request() -> None:
    payload = st.query_params.get("sync_trades")
    if not payload:
        return

    try:
        padded = payload + ("=" * (-len(payload) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        rows = json.loads(decoded)
        if not isinstance(rows, list):
            raise ValueError("交易紀錄格式不是清單")
        normalized = [normalize_trade(row) for row in rows]
        save_trades(normalized)
        sync_static_files()
        st.session_state["last_update_message"] = f"交易紀錄已同步，共 {len(normalized)} 筆"
        st.query_params.clear()
        st.rerun()
    except Exception as exc:
        st.query_params.clear()
        st.error("交易紀錄同步失敗")
        st.code(str(exc))


def build_embedded_dashboard_html(split_mode: str = "full", initial_hash: str = "#home") -> str:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return "<h2>找不到 static/index.html</h2>"

    html = index_path.read_text(encoding="utf-8")
    split_class = {
        "before_trade_form": " streamlit-before-trade-form",
        "after_trade_form": " streamlit-after-trade-form",
    }.get(split_mode, "")
    html = html.replace("<body>", f'<body class="streamlit-embedded{split_class}">', 1)
    dashboard_json = json.dumps(load_dashboard(), ensure_ascii=False)
    trades, trades_source = load_trades_with_source()
    trades_json = json.dumps(trades, ensure_ascii=False)
    trades_source_json = json.dumps(trades_source, ensure_ascii=False)
    daily_history_json = json.dumps(load_daily_history_map(), ensure_ascii=False)
    initial_hash = initial_hash if initial_hash in {"#home", "#trades", "#monthly", "#quarterly", "#holdings", "#yearly", "#signal-settings", "#data-maintenance", "#manual"} else "#home"
    initial_hash_json = json.dumps(initial_hash)

    bootstrap = f"""
    <style>
      body.streamlit-before-trade-form #trades,
      body.streamlit-before-trade-form #monthly,
      body.streamlit-before-trade-form #quarterly,
      body.streamlit-before-trade-form #holdings,
      body.streamlit-before-trade-form #yearly,
      body.streamlit-before-trade-form #signal-settings,
      body.streamlit-before-trade-form #manual {{
        display: none !important;
      }}

      body.streamlit-after-trade-form .mobile-home,
      body.streamlit-after-trade-form .desktop-home,
      body.streamlit-after-trade-form .hero-grid,
      body.streamlit-after-trade-form .data-freshness-section,
      body.streamlit-after-trade-form .home-focus-section,
      body.streamlit-after-trade-form #daily,
      body.streamlit-after-trade-form #trades {{
        display: none !important;
      }}

      body.streamlit-after-trade-form .sidebar {{
        display: none !important;
      }}

      body.streamlit-after-trade-form .app-shell {{
        display: block !important;
      }}

      body.streamlit-after-trade-form .content {{
        width: 100% !important;
        max-width: none !important;
        padding: 0 !important;
      }}

      @media (max-width: 760px) {{
        body.streamlit-after-trade-form {{
          display: none !important;
        }}
      }}
    </style>
    <script>
      window.__00919_STREAMLIT_EMBED = true;
      // UI17: keep the original HTML dashboard routing. The left sidebar Trade Log
      // stays inside the HTML dashboard; only the explicit “新增 / 匯入交易” button
      // opens a separate Streamlit native form page.
      window.__00919_NATIVE_TRADES_ENABLED = false;
      window.__00919_NATIVE_TRADES_URL = "/?native_page=trade_entry";
      window.__00919_INITIAL_PAGE_HASH = {initial_hash_json};
      window.__00919_DASHBOARD_DATA = {dashboard_json};
      window.__00919_TRADES_DATA = {trades_json};
      window.__00919_TRADES_SOURCE = {trades_source_json};
      window.__00919_DAILY_HISTORY_DATA = {daily_history_json};
      console.info("[00919] " + (window.__00919_TRADES_SOURCE.message || "交易紀錄來源已載入"));
      window.addEventListener("DOMContentLoaded", () => {{
        const ref = document.referrer || window.location.href || "http://localhost:8501/";
        let entryUrl = "/?native_page=trade_entry";
        try {{ entryUrl = new URL("?native_page=trade_entry", ref).toString(); }} catch (err) {{}}
        window.__00919_NATIVE_TRADES_URL = entryUrl;
        document.querySelectorAll('a[href="/?native_page=trade_entry"], a[data-trade-entry-link="true"]').forEach((link) => {{
          link.setAttribute("href", entryUrl);
          link.setAttribute("target", "_blank");
          link.setAttribute("rel", "noopener noreferrer");
        }});
      }});
    </script>
    """
    html = html.replace("</head>", f"{bootstrap}</head>", 1)
    # UI17: do not rewrite #trades to a native route. Trade Log remains a normal HTML dashboard page.

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
            script = script.replace(
                "fetch(`data/daily_history.json?ts=${Date.now()}`).catch(() => null)",
                "Promise.resolve(new Response(JSON.stringify(window.__00919_DAILY_HISTORY_DATA || {}), {status: 200, headers: {'Content-Type': 'application/json'}}))",
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
      let frameHeightTimer = null;
      let lastSentFrameHeight = 0;

      function pxNumber(value) {
        const parsed = Number.parseFloat(value);
        return Number.isFinite(parsed) ? parsed : 0;
      }

      function getParentAvailableHeight() {
        try {
          const frame = window.frameElement;
          const parentHeight = window.parent && window.parent.innerHeight ? window.parent.innerHeight : window.innerHeight;
          const frameTop = frame ? frame.getBoundingClientRect().top : 0;
          return Math.max(560, Math.floor(parentHeight - Math.max(frameTop, 0) - 10));
        } catch (err) {
          return Math.max(560, Math.floor(window.innerHeight || 720));
        }
      }

      function updateDashboardViewportVars() {
        const availableHeight = getParentAvailableHeight();
        document.documentElement.style.setProperty("--dashboard-shell-min-height", `${availableHeight}px`);
        document.body.style.setProperty("--dashboard-shell-min-height", `${availableHeight}px`);
        return availableHeight;
      }

      function getVisibleMobileHome() {
        const mobileHome = document.querySelector(".mobile-home");
        if (!mobileHome) return null;
        return window.getComputedStyle(mobileHome).display !== "none" ? mobileHome : null;
      }

      function getActiveDashboardPage() {
        const mobileHome = getVisibleMobileHome();
        if (mobileHome) return mobileHome;
        const pageName = document.body.dataset.activePage || "home";
        if (pageName === "home") return document.querySelector(".desktop-home") || document.querySelector(".content");
        return document.getElementById(pageName) || document.querySelector(".content");
      }

      function isInternallyCapped(element, style) {
        if (!element || !style) return false;
        const overflowY = style.overflowY || "";
        const hasScrollModel = overflowY === "auto" || overflowY === "scroll" || overflowY === "hidden";
        const hasHeightCap = style.maxHeight !== "none" || style.height !== "auto";
        return hasScrollModel && hasHeightCap;
      }

      function elementDocumentBottom(element) {
        if (!element) return 0;
        const style = window.getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") return 0;
        const rect = element.getBoundingClientRect();
        const marginBottom = pxNumber(style.marginBottom);
        const measuredHeight = isInternallyCapped(element, style)
          ? rect.height
          : Math.max(element.scrollHeight, rect.height);
        return Math.ceil(rect.top + window.scrollY + measuredHeight + marginBottom);
      }

      function measureDashboardHeight() {
        const minShellHeight = updateDashboardViewportVars();
        const content = document.querySelector(".content");
        const desktopHome = document.querySelector(".desktop-home");
        const activePage = getActiveDashboardPage();
        const visibleSections = Array.from(document.querySelectorAll(".content > section:not(.dashboard-page-hidden):not([hidden])"));
        const candidates = [minShellHeight, elementDocumentBottom(content), elementDocumentBottom(activePage)];

        if (desktopHome && window.getComputedStyle(desktopHome).display !== "none") {
          candidates.push(elementDocumentBottom(desktopHome));
        }
        visibleSections.forEach((section) => candidates.push(elementDocumentBottom(section)));

        const height = Math.ceil(Math.max(...candidates.filter((value) => Number.isFinite(value) && value > 0))) + 18;
        return Math.min(Math.max(height, 560), 4200);
      }

      function applyFrameHeight(height) {
        try {
          if (window.frameElement) {
            window.frameElement.style.height = height + "px";
            window.frameElement.style.minHeight = height + "px";
            window.frameElement.style.maxHeight = "none";
            if (window.frameElement.parentElement) {
              window.frameElement.parentElement.style.height = height + "px";
              window.frameElement.parentElement.style.minHeight = height + "px";
              window.frameElement.parentElement.style.maxHeight = "none";
            }
          }
        } catch (err) {
          /* frameElement may be blocked in some environments */
        }
      }

      function sendStreamlitFrameHeight() {
        const height = measureDashboardHeight();
        if (Math.abs(height - lastSentFrameHeight) <= 2) return;
        lastSentFrameHeight = height;
        applyFrameHeight(height);
        window.parent.postMessage({ type: "00919:frame-height", height }, "*");
        window.parent.postMessage(
          { isStreamlitMessage: true, type: "streamlit:setFrameHeight", height },
          "*"
        );
      }

      function scheduleFrameHeightUpdate() {
        window.clearTimeout(frameHeightTimer);
        sendStreamlitFrameHeight();
        frameHeightTimer = window.setTimeout(sendStreamlitFrameHeight, 80);
        window.setTimeout(sendStreamlitFrameHeight, 220);
        window.setTimeout(sendStreamlitFrameHeight, 520);
        window.setTimeout(sendStreamlitFrameHeight, 1000);
      }

      function observeFrameHeightRoot() {
        updateDashboardViewportVars();
        if (!("ResizeObserver" in window)) {
          scheduleFrameHeightUpdate();
          return;
        }
        if (frameHeightObserver) frameHeightObserver.disconnect();
        const roots = [document.querySelector(".content"), getActiveDashboardPage(), document.querySelector(".desktop-home")].filter(Boolean);
        frameHeightObserver = new ResizeObserver(scheduleFrameHeightUpdate);
        roots.forEach((root) => frameHeightObserver.observe(root));
        scheduleFrameHeightUpdate();
      }

      window.addEventListener("load", scheduleFrameHeightUpdate);
      window.addEventListener("load", observeFrameHeightRoot);
      window.addEventListener("resize", observeFrameHeightRoot);
      window.addEventListener("orientationchange", observeFrameHeightRoot);
      window.addEventListener("dashboard:rendered", () => {
        observeFrameHeightRoot();
        scheduleFrameHeightUpdate();
      });
      window.setTimeout(scheduleFrameHeightUpdate, 60);
      window.setTimeout(scheduleFrameHeightUpdate, 250);
      window.setTimeout(scheduleFrameHeightUpdate, 1000);
      function applyInitialDashboardHash() {
        const initialHash = window.__00919_INITIAL_PAGE_HASH || "#home";
        if (!initialHash || initialHash === "#home") return;
        if (typeof window.showDashboardPage === "function") {
          window.showDashboardPage(initialHash, true, false);
          scheduleFrameHeightUpdate();
          return;
        }
        window.location.hash = initialHash;
      }

      window.addEventListener("load", () => window.setTimeout(applyInitialDashboardHash, 0));
      window.setTimeout(applyInitialDashboardHash, 80);
      window.setTimeout(applyInitialDashboardHash, 300);
      window.setTimeout(scheduleFrameHeightUpdate, 2500);
    </script>
    """
    html = html.replace("</body>", f"{resize_script}</body>", 1)
    return html


def render_iframe_navigation_bridge() -> None:
    """Install a tiny same-origin bridge in the Streamlit parent page.

    The main dashboard is rendered by components.html inside an iframe.  The HTML
    sidebar lives inside that iframe, while the Streamlit native trade page lives
    at the top-level URL (?native_page=trades).  This bridge listens for messages
    from the dashboard iframe and changes the parent URL, so clicking the left
    sidebar Trade Log item opens the real Streamlit page instead of the legacy
    HTML trade section.
    """
    components.html(
        """
        <script>
          (function install00919NavBridge() {
            var parentWindow;
            try { parentWindow = window.parent; } catch (err) { return; }
            if (!parentWindow) return;

            try {
              if (parentWindow.__00919NavBridgeVersion === "ui61") return;
              parentWindow.__00919NavBridgeVersion = "ui61";
              // 不再沿用舊版 __00919NavBridgeInstalled，避免瀏覽器還掛著 UI14/UI55
              // 的 bridge，導致資料維護的 navigate-native 訊息沒有人處理。
              parentWindow.__00919NavBridgeInstalled = true;
            } catch (err) {
              /* Continue even if the marker cannot be written. */
            }

            function getParentDocument() {
              try { return parentWindow.document; } catch (err) { return null; }
            }

            function makeNativeTradesUrl() {
              try {
                var url = new URL(parentWindow.location.href);
                url.searchParams.set("native_page", "trades");
                url.searchParams.delete("target_page");
                url.hash = "";
                return url.toString();
              } catch (err) {
                return "/?native_page=trades";
              }
            }

            function makeNativePageUrl(nativePage, nativeUrl) {
              if (nativeUrl) {
                try { return new URL(nativeUrl, parentWindow.location.href).toString(); } catch (err) {}
              }
              try {
                var url = new URL(parentWindow.location.href);
                if (nativePage === "data_maintenance") {
                  url.searchParams.set("native_page", "data_maintenance");
                  url.searchParams.delete("target_page");
                } else if (nativePage === "data-maintenance") {
                  url.searchParams.set("target_page", "data-maintenance");
                  url.searchParams.delete("native_page");
                } else {
                  url.searchParams.set("native_page", nativePage || "data_maintenance");
                  url.searchParams.delete("target_page");
                }
                url.searchParams.delete("embedded");
                url.hash = "";
                return url.toString();
              } catch (err) {
                if (nativePage === "data_maintenance") return "/?native_page=data_maintenance";
                if (nativePage === "data-maintenance") return "/?target_page=data-maintenance";
                return "/?native_page=" + (nativePage || "data_maintenance");
              }
            }

            function goNativePage(nativePage, nativeUrl) {
              var target = makeNativePageUrl(nativePage, nativeUrl);
              try {
                // 用 assign 比 href 更穩定，會觸發 Streamlit 重新跑一次，
                // target_page=data-maintenance 才會進原生資料維護頁。
                parentWindow.location.assign(target);
                return true;
              } catch (err) {}
              try { parentWindow.location.href = target; return true; } catch (err) {}
              try { parentWindow.open(target, "_self"); return true; } catch (err) {}
              return false;
            }

            function goNativeTrades() {
              var target = makeNativeTradesUrl();
              try {
                parentWindow.location.href = target;
                return true;
              } catch (err) {
                try { parentWindow.location.assign(target); return true; } catch (innerErr) {}
              }
              return false;
            }

            function getFrames() {
              var parentDoc = getParentDocument();
              if (!parentDoc) return [];
              return Array.prototype.slice.call(parentDoc.querySelectorAll("iframe"));
            }

            function relayHashToDashboard(hash) {
              getFrames().forEach(function(frame) {
                try {
                  frame.contentWindow.postMessage({ type: "00919:scroll-to", hash: hash }, "*");
                } catch (err) {}
              });
            }

            function syncActivePageToParentUrl(page, hash) {
              var normalized = String(page || hash || "home").replace(/^#/, "");
              var allowed = { home: true, trades: true, monthly: true, quarterly: true, holdings: true, yearly: true, "signal-settings": true, "data-maintenance": true, manual: true };
              if (!allowed[normalized]) normalized = "home";
              try {
                var url = new URL(parentWindow.location.href);
                if (url.searchParams.get("native_page")) return;
                if (url.searchParams.get("target_page") === normalized) return;
                url.searchParams.set("target_page", normalized);
                url.searchParams.delete("run_update");
                url.hash = "";
                parentWindow.history.replaceState(parentWindow.history.state || {}, "", url.toString());
              } catch (err) {
                /* Best-effort: old browsers may block history replacement. */
              }
            }

            parentWindow.addEventListener("message", function(event) {
              var data = event.data || {};

              if (data.type === "00919:active-page") {
                syncActivePageToParentUrl(data.page, data.hash);
                return;
              }

              if (data.type === "00919:navigate-native") {
                goNativePage(data.nativePage, data.nativeUrl);
                return;
              }

              // UI59 相容訊息：從 HTML iframe 左側點資料維護時，也允許走
              // 00919:navigate + nativeUrl，避免舊 navigation handler 或快取造成左鍵失效。
              if (data.type === "00919:navigate" && data.nativeUrl) {
                goNativePage(data.nativePage || (data.hash === "#data-maintenance" ? "data-maintenance" : "trades"), data.nativeUrl);
                return;
              }

              if (data.type === "00919:navigate" && data.hash === "#trades") {
                goNativeTrades();
                return;
              }

              if (data.type === "00919:navigate" && data.hash) {
                relayHashToDashboard(data.hash);
                return;
              }

              if (data.type === "00919:navigate-offset") {
                var frames = getFrames();
                var sourceFrame = frames.find(function(frame) { return frame.contentWindow === event.source; });
                if (!sourceFrame) return;
                var frameTop = sourceFrame.getBoundingClientRect().top + parentWindow.scrollY;
                var targetTop = frameTop + Number(data.top || 0) - 12;
                parentWindow.scrollTo({ top: targetTop, behavior: "smooth" });
                return;
              }

              if (data.type === "00919:frame-height") {
                var frames = getFrames();
                var sourceFrame = frames.find(function(frame) { return frame.contentWindow === event.source; });
                var height = Math.min(Math.max(Number(data.height || 0), 560), 4200);
                if (!sourceFrame || !Number.isFinite(height)) return;
                sourceFrame.style.height = height + "px";
                sourceFrame.style.minHeight = height + "px";
                sourceFrame.style.maxHeight = "none";
                if (sourceFrame.parentElement) {
                  sourceFrame.parentElement.style.height = height + "px";
                  sourceFrame.parentElement.style.minHeight = height + "px";
                  sourceFrame.parentElement.style.maxHeight = "none";
                }
              }
            });
          })();
        </script>
        """,
        height=1,
        scrolling=False,
    )




def target_page_hash_from_query() -> str:
    page = str(st.query_params.get("target_page", "home") or "home").strip()
    mapping = {
        "home": "#home",
        "trades": "#trades",
        "monthly": "#monthly",
        "quarterly": "#quarterly",
        "holdings": "#holdings",
        "yearly": "#yearly",
        "signal-settings": "#signal-settings",
        "data-maintenance": "#data-maintenance",
        "manual": "#manual",
    }
    return mapping.get(page, "#home")


def dashboard_route_url(target: str) -> str:
    if target == "trades":
        return "/?native_page=trades"
    if target == "data-maintenance":
        # UI59: 資料維護改走 target_page 原生路由，不再使用 native_page，
        # 避免被 HTML dashboard iframe 套住，造成黑屏與雙更新按鈕。
        return "/?target_page=data-maintenance"
    return f"/?target_page={target}"


def render_native_sidebar(active: str = "trades") -> None:
    nav_items = [
        ("home", "home", "green", "首頁總覽"),
        ("trades", "briefcase", "blue", "交易紀錄"),
        ("monthly", "activity", "green", "每月健康檢查"),
        ("quarterly", "coins", "orange", "每季 / 54C 檢視"),
        ("holdings", "pieChart", "purple", "持股分析"),
        ("yearly", "calculator", "pink", "年度稅務總覽"),
        ("signal-settings", "trafficCone", "green", "燈號設定"),
        ("data-maintenance", "database", "blue", "資料維護"),
        ("manual", "user", "cyan", "使用說明"),
    ]
    links = []
    for key, icon, color, label in nav_items:
        active_class = " active is-active" if key == active else ""
        aria = " aria-current='page'" if key == active else ""
        href = dashboard_route_url(key)
        onclick = "try{event.preventDefault(); window.location.assign(this.href);}catch(e){window.location.href=this.href;} return false;"
        links.append(
            f'<a class="{active_class.strip()}" href="{href}" target="_self"{aria} onclick="{onclick}">'
            f"<span data-icon='{icon}' data-icon-color='{color}'></span>{html.escape(label)}</a>"
        )
    st.markdown(
        """
        <aside class="native-sidebar">
          <div class="brand">
            <span class="brand-mark">919</span>
            <div>
              <h1>00919 監控</h1>
              <p>高股息現金流儀表板</p>
            </div>
          </div>
          <nav class="nav">
        """
        + "".join(links)
        + """
          </nav>
          <div class="sidebar-signal">
            <span class="sidebar-signal__dot"></span>
            <div>
              <strong>綠燈</strong>
              <small>所有數據正常</small>
            </div>
          </div>
          <div class="source-card">
            <span>資料來源</span>
            <strong>Google Sheets / MoneyDJ / TWSE</strong>
            <small>交易紀錄由 Google Sheets 同步</small>
          </div>
        </aside>
        """,
        unsafe_allow_html=True,
    )


def install_native_sidebar_same_tab_guard() -> None:
    """Keep custom HTML native-sidebar links in the current browser tab.

    UI54: avoid intercepting clicks from a Streamlit component iframe.  The
    native sidebar anchors now carry their own target="_self" + onclick handler
    in the main Streamlit document.  This helper only normalizes target attrs as
    a best-effort pass, so it will not trap the user inside 資料維護 when leaving
    for 首頁 / 其他 HTML dashboard pages.
    """
    components.html(
        """
        <script>
        (() => {
          function install() {
            try {
              const doc = window.parent && window.parent.document ? window.parent.document : document;
              doc.querySelectorAll('.native-sidebar .nav a[href]').forEach((link) => {
                link.setAttribute('target', '_self');
                link.removeAttribute('rel');
              });
            } catch (err) {}
          }
          install();
          window.setTimeout(install, 250);
          window.setTimeout(install, 900);
        })();
        </script>
        """,
        height=0,
        scrolling=False,
    )


def build_daily_history_preview_df(history: dict, limit: int = 30) -> pd.DataFrame:
    rows = [history[key] for key in sorted(history.keys(), reverse=True)[:limit]]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    column_labels = {
        "date": "日期",
        "market_price": "市價",
        "market_close": "收盤價",
        "adjusted_close": "還原收盤價",
        "volume_shares": "成交股數",
        "volume_lots": "成交張數",
        "price_source": "收盤價來源",
        "updated_at": "更新時間",
        "official_nav": "官方淨值",
        "nav": "淨值",
        "nav_source": "淨值來源",
        "is_estimated_nav": "是否估算淨值",
        "premium_discount_amount": "折溢價金額",
        "premium_discount_pct": "折溢價率%",
        "premium_source": "折溢價來源",
        "imported_premium_discount_pct": "匯入折溢價率%",
        "source": "原始來源",
    }
    preferred = [
        "date",
        "market_price",
        "market_close",
        "adjusted_close",
        "volume_shares",
        "volume_lots",
        "price_source",
        "official_nav",
        "nav",
        "nav_source",
        "is_estimated_nav",
        "premium_discount_amount",
        "premium_discount_pct",
        "premium_source",
        "updated_at",
    ]
    ordered = [col for col in preferred if col in df.columns]
    ordered += [col for col in df.columns if col not in ordered]
    df = df[ordered].rename(columns=column_labels)

    source_map = {
        "Yahoo": "Yahoo",
        "TWSE": "TWSE",
        "MoneyDJ": "MoneyDJ",
        "calculated": "系統計算",
        "excel_import": "Excel 匯入",
        "capitalfund_excel_import": "群益 Excel 匯入",
        "capitalfund_trend": "群益官網",
    }
    for col in ["收盤價來源", "淨值來源", "折溢價來源", "原始來源"]:
        if col in df.columns:
            df[col] = df[col].map(lambda value: source_map.get(value, value) if value not in (None, "") else "缺")
    if "是否估算淨值" in df.columns:
        df["是否估算淨值"] = df["是否估算淨值"].map(lambda value: "是" if bool(value) else "否")
    df = df.where(pd.notnull(df), "缺")
    return df




def _maintenance_format_cell(value, column_name: str) -> str:
    if value in (None, "", "缺") or pd.isna(value):
        return "缺"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        if column_name in {"成交股數", "成交張數"}:
            return f"{value:,.0f}"
        if column_name in {"折溢價率%"}:
            return f"{value:.4f}"
        if column_name in {"市價", "收盤價", "還原收盤價", "官方淨值", "淨值", "折溢價金額"}:
            return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def build_daily_history_preview_html(history: dict, limit: int = 30) -> str:
    df = build_daily_history_preview_df(history, limit=limit)
    if df.empty:
        return "<div class='daily-history-table-wrap'><table class='daily-history-table'><tbody><tr><td>目前沒有每日資料。</td></tr></tbody></table></div>"
    headers = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)
    row_html = []
    for _, row in df.iterrows():
        formatted_cells = [_maintenance_format_cell(row[col], str(col)) for col in df.columns]
        has_missing = any(cell == "缺" for cell in formatted_cells)
        cells = []
        for cell in formatted_cells:
            if cell == "缺":
                cells.append("<td><span class='cell-missing'>缺</span></td>")
            else:
                cells.append(f"<td>{html.escape(cell)}</td>")
        row_html.append(f"<tr class='{'row-has-missing' if has_missing else ''}'>" + "".join(cells) + "</tr>")
    return "<div class='daily-history-table-wrap'><table class='daily-history-table'><thead><tr>" + headers + "</tr></thead><tbody>" + "".join(row_html) + "</tbody></table></div>"


def render_native_trade_hero(data: dict, trades: list[dict]) -> None:
    latest = data.get("latest_daily", {})
    dividends = data.get("dividends", [])
    position = calc_position(trades, dividends)
    market_price = float(latest.get("market_price") or 0)
    market_value = position["shares"] * market_price
    unrealized = market_value - position["cost"]
    total_return = unrealized + position["cumulative_dividend"] + position["realized"]
    signal, reason = calc_total_signal(data, position, total_return)
    signal_text = "綠燈" if signal == "green" else "黃燈" if signal == "yellow" else "紅燈"
    st.markdown(
        f"""
        <section class="native-hero desktop-hero">
          <div class="desktop-hero__orb {'yellow' if signal == 'yellow' else 'red' if signal == 'red' else ''}">
            <span>{signal_text}</span>
            <small>{html.escape(reason[:12])}</small>
          </div>
          <div class="desktop-hero__meta">
            <p>CAPITAL HIGH DIVIDEND ETF</p>
            <h2>00919 群益台灣精選高息</h2>
            <span class="ui-status-chip hero-time-chip">資料抓取時間 {html.escape(str(data.get('fetched_at', '--')))}</span>
          </div>
          <div class="desktop-hero-summary">
            <article class="desktop-hero-summary-card">
              <span>目前股數</span>
              <strong>{money(position['shares'])} 股</strong>
            </article>
            <article class="desktop-hero-summary-card">
              <span>含息報酬</span>
              <strong>${money(total_return)}</strong>
            </article>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )



def normalize_history_date(value) -> str | None:
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        parsed = pd.NaT
    if pd.isna(parsed):
        text = str(value).strip().replace("/", "-")
        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
        if not match:
            return None
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return parsed.strftime("%Y-%m-%d")


def coerce_history_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        if text.upper() in {"N/A", "NA", "--", "-", "NONE", "NULL"}:
            return None
        numeric = float(text)
    except Exception:
        return None
    if pd.isna(numeric) or numeric <= 0:
        return None
    return round(numeric, 4)


def load_daily_history_map() -> dict:
    raw = read_json(DAILY_HISTORY_PATH, {})
    rows = raw.values() if isinstance(raw, dict) else raw
    result = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date_value = normalize_history_date(row.get("date"))
        if not date_value:
            continue
        normalized = {**row, "date": date_value}
        nav = coerce_history_float(normalized.get("official_nav") if normalized.get("official_nav") is not None else normalized.get("nav"))
        price = coerce_history_float(normalized.get("market_close") if normalized.get("market_close") is not None else normalized.get("market_price"))
        if nav is not None:
            normalized["official_nav"] = nav
            normalized["nav"] = nav
            normalized.setdefault("is_estimated_nav", False)
        if price is not None:
            normalized["market_close"] = price
            normalized["market_price"] = price
        result[date_value] = recalc_daily_history_row(normalized)
    return result


def recalc_daily_history_row(row: dict) -> dict:
    nav = coerce_history_float(row.get("official_nav") if row.get("official_nav") is not None else row.get("nav"))
    price = coerce_history_float(row.get("market_close") if row.get("market_close") is not None else row.get("market_price"))
    if nav is not None:
        row["official_nav"] = nav
        row["nav"] = nav
    if price is not None:
        row["market_close"] = price
        row["market_price"] = price
    if nav is not None and price is not None:
        row["premium_discount_amount"] = round(price - nav, 4)
        row["premium_discount_pct"] = round((price - nav) / nav * 100, 4)
        row["premium_source"] = "calculated"
    return row


def save_daily_history_map(history: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    clean = {}
    for date_value in sorted(history):
        row = recalc_daily_history_row({**history[date_value], "date": date_value})
        clean[date_value] = row
    DAILY_HISTORY_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def build_daily_history_status(history: dict) -> dict:
    rows = [history[key] for key in sorted(history)]
    nav_dates = [row["date"] for row in rows if coerce_history_float(row.get("official_nav")) is not None]
    price_dates = [row["date"] for row in rows if coerce_history_float(row.get("market_close")) is not None]
    premium_dates = [row["date"] for row in rows if row.get("premium_discount_pct") is not None]
    market_dates = set(price_dates)
    missing_nav_on_market_dates = sorted([d for d in market_dates if d not in set(nav_dates)])
    missing_price_on_nav_dates = sorted([d for d in set(nav_dates) if d not in market_dates])
    return {
        "row_count": len(rows),
        "nav_count": len(nav_dates),
        "price_count": len(price_dates),
        "premium_count": len(premium_dates),
        "first_nav_date": nav_dates[0] if nav_dates else "--",
        "latest_nav_date": nav_dates[-1] if nav_dates else "--",
        "latest_price_date": price_dates[-1] if price_dates else "--",
        "latest_premium_date": premium_dates[-1] if premium_dates else "--",
        "missing_nav_on_market_dates": missing_nav_on_market_dates,
        "missing_price_on_nav_dates": missing_price_on_nav_dates,
    }


def find_nav_excel_columns(df: pd.DataFrame) -> tuple[str | None, str | None, str | None, str | None]:
    columns = [str(col).strip() for col in df.columns]
    date_candidates = {"日期", "date", "Date", "DATE", "交易日期", "淨值日期", "資料日期"}
    nav_candidates = {"淨值", "NAV", "nav", "基金淨值", "每受益權單位淨資產價值", "每單位淨值"}
    price_candidates = {"收盤價", "市價", "market_close", "market_price", "close", "Close"}
    premium_candidates = {"折溢價率", "折溢價%", "premium_discount_pct", "折溢價", "折（溢）價率"}

    def pick(candidates):
        for original, normalized in zip(df.columns, columns):
            if normalized in candidates:
                return original
        for original, normalized in zip(df.columns, columns):
            for candidate in candidates:
                if str(candidate).lower() in normalized.lower():
                    return original
        return None

    return pick(date_candidates), pick(nav_candidates), pick(price_candidates), pick(premium_candidates)


def read_nav_excel(uploaded_file) -> tuple[pd.DataFrame, dict]:
    # Some Capital Fund exports place the real headers on the first data row.
    excel_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file
    excel_source = io.BytesIO(excel_bytes) if isinstance(excel_bytes, (bytes, bytearray)) else excel_bytes
    raw = pd.read_excel(excel_source, sheet_name=0, header=0)
    date_col, nav_col, price_col, premium_col = find_nav_excel_columns(raw)
    if not date_col or not nav_col:
        excel_source = io.BytesIO(excel_bytes) if isinstance(excel_bytes, (bytes, bytearray)) else excel_bytes
        raw2 = pd.read_excel(excel_source, sheet_name=0, header=None)
        if raw2.empty:
            raise ValueError("Excel 檔案沒有可讀取的資料。")
        header_row_index = None
        for idx, row in raw2.head(10).iterrows():
            texts = [str(v).strip() for v in row.tolist()]
            if any(text in {"日期", "date", "Date"} for text in texts) and any(text in {"淨值", "NAV", "nav"} for text in texts):
                header_row_index = idx
                break
        if header_row_index is None:
            raise ValueError("找不到日期 / 淨值欄位，請確認 Excel 至少包含『日期』與『淨值』兩欄。")
        headers = [str(v).strip() for v in raw2.iloc[header_row_index].tolist()]
        raw = raw2.iloc[header_row_index + 1:].copy()
        raw.columns = headers
        date_col, nav_col, price_col, premium_col = find_nav_excel_columns(raw)
    if not date_col or not nav_col:
        raise ValueError("找不到日期 / 淨值欄位，請確認 Excel 至少包含『日期』與『淨值』兩欄。")

    rows = []
    bad_rows = 0
    for _, item in raw.iterrows():
        date_value = normalize_history_date(item.get(date_col))
        nav_value = coerce_history_float(item.get(nav_col))
        if not date_value and nav_value is None:
            continue
        if not date_value or nav_value is None:
            bad_rows += 1
            continue
        row = {
            "date": date_value,
            "official_nav": nav_value,
            "nav": nav_value,
            "nav_source": "capitalfund_excel_import",
            "is_estimated_nav": False,
        }
        if price_col:
            price = coerce_history_float(item.get(price_col))
            if price is not None:
                row["market_close"] = price
                row["market_price"] = price
                row["price_source"] = "excel_import"
        if premium_col:
            premium = item.get(premium_col)
            try:
                premium_num = float(str(premium).replace("%", "").replace(",", "").strip())
                if pd.notna(premium_num):
                    row["imported_premium_discount_pct"] = round(premium_num, 4)
            except Exception:
                pass
        rows.append(row)
    df = pd.DataFrame(rows).drop_duplicates(subset=["date"], keep="last").sort_values("date") if rows else pd.DataFrame()
    meta = {
        "date_col": str(date_col),
        "nav_col": str(nav_col),
        "price_col": str(price_col) if price_col else None,
        "premium_col": str(premium_col) if premium_col else None,
        "bad_rows": bad_rows,
    }
    return df, meta


def import_nav_rows_to_daily_history(rows: pd.DataFrame) -> dict:
    history = load_daily_history_map()
    now = datetime.now().isoformat(timespec="seconds")
    imported = 0
    updated = 0
    for record in rows.to_dict("records"):
        date_value = record.get("date")
        if not date_value:
            continue
        old = history.get(date_value, {"date": date_value})
        existed = date_value in history and coerce_history_float(history[date_value].get("official_nav")) is not None
        merged = {**old, **{key: value for key, value in record.items() if value is not None and value != ""}}
        merged["updated_at"] = now
        history[date_value] = recalc_daily_history_row(merged)
        if existed:
            updated += 1
        else:
            imported += 1
    save_daily_history_map(history)
    sync_static_files()
    return {"imported": imported, "updated": updated, "total": len(rows)}


def refresh_dashboard_daily_from_history() -> None:
    if not DASHBOARD_PATH.exists() or not DAILY_HISTORY_PATH.exists():
        return
    data = load_dashboard()
    history = load_daily_history_map()
    rows = [history[key] for key in sorted(history)]
    if not rows:
        return
    data["daily"] = rows
    latest_complete = next(
        (row for row in reversed(rows) if row.get("market_price") is not None and row.get("nav") is not None),
        rows[-1],
    )
    data["latest_daily"] = latest_complete
    data["daily_history_meta"] = build_daily_history_status(history)
    DASHBOARD_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    sync_static_files()


def render_native_data_maintenance_page() -> None:
    sync_static_files()
    history = load_daily_history_map()
    status = build_daily_history_status(history)
    data = load_dashboard()

    st.markdown(
        """
        <style>
          .main .block-container {
            max-width: 100% !important;
            padding: 1rem 2.25rem 1.25rem !important;
            background: #f5f7f7;
          }
          div[data-testid="stHorizontalBlock"]:has(.native-sidebar) {
            gap: 1.1rem !important;
            align-items: stretch !important;
          }
          .native-sidebar {
            min-height: calc(100vh - 76px);
            height: calc(100vh - 76px);
            position: sticky;
            top: 14px;
            display: flex;
            flex-direction: column;
            gap: 18px;
            padding: 24px 20px;
            background: linear-gradient(180deg, #06251f 0%, #071723 100%);
            color: #e5f2ef;
            overflow: hidden;
          }
          .native-sidebar .brand { display:flex; gap:12px; align-items:center; padding-bottom:4px; }
          .native-sidebar .brand-mark { display:inline-flex; width:44px; height:44px; align-items:center; justify-content:center; border:1px solid rgba(16,185,129,.85); border-radius:10px; color:#fff; font-weight:900; }
          .native-sidebar h1 { margin:0; color:#fff; font-size:1.05rem; font-weight:900; }
          .native-sidebar p { margin:4px 0 0; color:#b6c9c5; font-size:.78rem; }
          .native-sidebar .nav { display:grid; gap:8px; }
          .native-sidebar .nav a { display:flex; align-items:center; gap:10px; min-height:44px; padding:10px 12px; border-radius:10px; color:#d7e5e2; text-decoration:none; font-weight:800; font-size:.94rem; }
          .native-sidebar .nav a.active, .native-sidebar .nav a[aria-current="page"] { background:linear-gradient(90deg, rgba(16,185,129,.24), rgba(255,255,255,.08)); color:#fff; box-shadow:inset 3px 0 0 #10b981; }
          .native-sidebar [data-icon] { display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:8px; background:rgba(255,255,255,.08); }
          .native-sidebar .sidebar-signal, .native-sidebar .source-card { margin-top:auto; padding:14px; border:1px solid rgba(148,163,184,.22); border-radius:12px; background:rgba(255,255,255,.06); }
          .native-sidebar .source-card { margin-top:0; }
          .native-sidebar .sidebar-signal__dot { display:inline-flex; width:24px; height:24px; margin-right:8px; border-radius:999px; background:#10b981; vertical-align:middle; }
          .native-sidebar .sidebar-signal strong, .native-sidebar .source-card strong { display:block; color:#fff; font-weight:900; }
          .native-sidebar .sidebar-signal small, .native-sidebar .source-card small, .native-sidebar .source-card span { color:#b6c9c5; font-size:.78rem; }
          .maintenance-hero { margin:0 0 14px; padding:22px 24px; border-radius:18px; background:linear-gradient(135deg,#059669 0%,#0891b2 48%,#1d4ed8 100%); color:white; box-shadow:0 18px 44px rgba(15,23,42,.16); }
          .maintenance-hero p { margin:0 0 4px; opacity:.82; font-size:.78rem; font-weight:900; letter-spacing:.08em; text-transform:uppercase; }
          .maintenance-hero h1 { margin:0; font-size:1.55rem; font-weight:950; }
          .maintenance-hero small { display:block; margin-top:8px; opacity:.88; line-height:1.55; }
          .maintenance-card { margin:8px 0; padding:12px 14px; border:1px solid #d9e2df; border-radius:16px; background:#fff; box-shadow:0 10px 24px rgba(15,23,42,.06); }
          .maintenance-card h3 { margin:0 0 4px; color:#0f172a; font-size:1.08rem; font-weight:950; }
          .maintenance-card p { margin:0; color:#64748b; font-size:.94rem; line-height:1.48; }
          .compact-maintenance-row { padding:0 !important; }
          .compact-maintenance-row h3 { margin:0 0 4px; color:#0f172a; font-size:1.08rem; font-weight:950; }
          .compact-maintenance-row p { margin:0; color:#64748b; font-size:.94rem; line-height:1.48; }
          div[data-testid="stHorizontalBlock"]:has(.maintenance-upload-marker),
          div[data-testid="stHorizontalBlock"]:has(.maintenance-tools-marker) {
            margin:8px 0 10px !important; padding:12px 14px !important; border:1px solid #d9e2df !important; border-radius:16px !important; background:#fff !important; box-shadow:0 10px 24px rgba(15,23,42,.06) !important; align-items:center !important; gap:14px !important;
          }
          div[data-testid="stHorizontalBlock"]:has(.maintenance-upload-marker) > div,
          div[data-testid="stHorizontalBlock"]:has(.maintenance-tools-marker) > div { display:flex !important; align-items:center !important; }
          div[data-testid="stFileUploader"] { margin:0 !important; width:100% !important; }
          div[data-testid="stFileUploader"] > label { display:none !important; }
          div[data-testid="stFileUploaderDropzone"] { min-height:42px !important; padding:4px 8px !important; border-radius:12px !important; background:#f8fafc !important; }
          div[data-testid="stFileUploaderDropzone"] button { background:#059669 !important; color:#fff !important; border:0 !important; border-radius:10px !important; font-weight:900 !important; min-height:34px !important; }
          div[data-testid="stFileUploaderDropzone"] small { font-size:.78rem !important; color:#64748b !important; }
          .maintenance-kpis { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:12px; }
          .maintenance-kpi { padding:14px; border:1px solid #d9e2df; border-radius:12px; background:#fbfcfc; }
          .maintenance-kpi span { display:block; color:#64748b; font-size:.82rem; font-weight:850; }
          .maintenance-kpi strong { display:block; margin-top:5px; color:#0f172a; font-size:1.18rem; font-weight:950; }
          .maintenance-table-title { margin:18px 0 8px; color:#0f172a; font-size:1.16rem; font-weight:950; }
          .maintenance-table-note { margin:0 0 10px; color:#475569; font-size:1rem; font-weight:800; }
          .maintenance-gap-card { padding:11px 14px; }
          .maintenance-card__head { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-bottom:6px; }
          .gap-status { flex:0 0 auto; padding:7px 13px; border-radius:999px; font-size:.98rem; font-weight:950; }
          .gap-status.ok { color:#047857; background:#ecfdf5; border:1px solid #a7f3d0; }
          .gap-status.warn { color:#b45309; background:#fffbeb; border:1px solid #fde68a; }
          .gap-summary { display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:8px 10px; border:1px solid #d9e2df; border-radius:12px; background:#fbfcfc; color:#0f172a; font-size:1.03rem; font-weight:900; line-height:1.45; }
          .gap-summary span { color:#475569; font-weight:950; }
          .gap-summary strong { color:#0f172a; font-weight:950; }
          .gap-summary strong.is-empty { color:#059669; }
          .daily-history-table-wrap { max-height:720px; overflow:auto; border:1px solid #d9e2df; border-radius:14px; background:#fff; box-shadow:0 12px 30px rgba(15,23,42,.06); }
          .daily-history-table { width:max-content; min-width:100%; border-collapse:separate; border-spacing:0; font-size:16px; color:#0f172a; }
          .daily-history-table th { position:sticky; top:0; z-index:2; background:#eef5f4; color:#334155; font-weight:950; text-align:left; white-space:nowrap; padding:12px 13px; border-bottom:1px solid #cbd5e1; }
          .daily-history-table td { padding:11px 13px; border-bottom:1px solid #e5e7eb; white-space:nowrap; font-weight:780; }
          .daily-history-table tbody tr:nth-child(even) td { background:#fbfcfc; }
          .daily-history-table tbody tr:hover td { background:#ecfdf5; }
          .daily-history-table tr.row-has-missing td:first-child { box-shadow:inset 4px 0 0 #f59e0b; }
          .cell-missing { display:inline-flex; align-items:center; justify-content:center; min-width:30px; padding:3px 8px; border-radius:999px; color:#b45309; background:#fffbeb; border:1px solid #fde68a; font-weight:950; }
          .mobile-maintenance-protection { display:none; }
          div[data-testid="stForm"] { border:1px solid #d9e2df; border-radius:14px; padding:16px 18px 18px; background:#fbfcfc; }
          div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
          div[data-testid="stButton"] button[kind="primary"] { background:#059669 !important; border:0 !important; border-radius:10px !important; color:#fff !important; font-weight:900 !important; min-height:42px !important; }
          @media (max-width: 1100px) { .maintenance-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); } }
          @media (max-width: 760px) {
            .main .block-container { padding:0 !important; }
            div[data-testid="stHorizontalBlock"]:has(.native-sidebar) { display:none !important; }
            .mobile-maintenance-protection { display:block; margin:10px; padding:14px; border-radius:14px; background:#ecfdf5; color:#065f46; font-weight:850; line-height:1.55; }
          }
        </style>
        <div class="mobile-maintenance-protection">手機版維持只顯示首頁總覽，只看不能修改；資料維護與 Excel 匯入請回到電腦版操作。</div>
        """,
        unsafe_allow_html=True,
    )
    install_native_sidebar_same_tab_guard()

    left, right = st.columns([0.86, 6.2])
    with left:
        render_native_sidebar("data-maintenance")
    with right:
        st.markdown(
            f"""
            <section class="maintenance-hero">
              <p>DATA MAINTENANCE</p>
              <h1>資料維護</h1>
              <small>用 navs.xlsx 建立上市以來 NAV 底稿，長期保存每日 NAV、收盤價與折溢價。更新資料時會從最後一筆 NAV 日期往前 10 天補資料。</small>
            </section>
            <section class="maintenance-card">
              <h3>每日資料庫狀態</h3>
              <p>正式檔案：data/daily_history.json；前端同步檔：static/data/daily_history.json。</p>
              <div class="maintenance-kpis">
                <div class="maintenance-kpi"><span>NAV 筆數</span><strong>{status['nav_count']}</strong></div>
                <div class="maintenance-kpi"><span>收盤價筆數</span><strong>{status['price_count']}</strong></div>
                <div class="maintenance-kpi"><span>折溢價可計算</span><strong>{status['premium_count']}</strong></div>
                <div class="maintenance-kpi"><span>最新 NAV 日期</span><strong>{html.escape(str(status['latest_nav_date']))}</strong></div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        upload_text_col, upload_btn_col = st.columns([5.1, 1.55], vertical_alignment="center")
        with upload_text_col:
            st.markdown(
                '<div class="maintenance-upload-marker compact-maintenance-row">'
                '<h3>NAV Excel 匯入</h3>'
                '<p>固定格式至少包含「日期 / 淨值」兩欄；如果同時有收盤價，系統也會一併匯入並重算折溢價。</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        with upload_btn_col:
            uploaded_nav = st.file_uploader("選擇 navs.xlsx", type=["xlsx"], key="nav_excel_importer", label_visibility="collapsed")
        if uploaded_nav is not None:
            try:
                preview_df, meta = read_nav_excel(uploaded_nav)
                st.info(
                    f"已讀取 {len(preview_df)} 筆；日期欄：{meta['date_col']}；淨值欄：{meta['nav_col']}；"
                    f"收盤價欄：{meta['price_col'] or '無'}；折溢價欄：{meta['premium_col'] or '無'}；異常列：{meta['bad_rows']}。"
                )
                st.dataframe(preview_df.head(8), use_container_width=True, hide_index=True)
                import_col, note_col = st.columns([1, 4])
                with import_col:
                    do_import = st.button("確認匯入 NAV", type="primary", use_container_width=True)
                with note_col:
                    st.caption("匯入後會寫入 daily_history.json，保留舊有效資料，並重新計算折溢價。")
                if do_import:
                    result = import_nav_rows_to_daily_history(preview_df)
                    refresh_dashboard_daily_from_history()
                    st.success(f"匯入完成：新增 {result['imported']} 筆，更新 {result['updated']} 筆，合計處理 {result['total']} 筆。")
                    st.rerun()
            except Exception as exc:
                st.error("NAV Excel 讀取失敗")
                st.code(f"{type(exc).__name__}: {exc}")

        miss_nav = status["missing_nav_on_market_dates"][-30:]
        miss_price = status["missing_price_on_nav_dates"][-30:]
        miss_nav_text = "無" if not miss_nav else "、".join(miss_nav)
        miss_price_text = "無" if not miss_price else "、".join(miss_price)
        gap_total = len(status["missing_nav_on_market_dates"]) + len(status["missing_price_on_nav_dates"])
        gap_class = "ok" if gap_total == 0 else "warn"
        gap_label = "無缺漏" if gap_total == 0 else f"{gap_total} 筆需補"
        st.markdown(
            f"""
            <section class="maintenance-card maintenance-gap-card">
              <div class="maintenance-card__head">
                <div>
                  <h3>缺漏資料檢查</h3>
                  <p>只檢查已有交易日資料內的 NAV / 收盤價互相缺漏，不把假日列入缺漏。</p>
                </div>
                <strong class="gap-status {gap_class}">{html.escape(gap_label)}</strong>
              </div>
              <div class="gap-summary">
                <span>缺 NAV</span><strong class="{'is-empty' if not miss_nav else ''}">{html.escape(miss_nav_text)}</strong>
                <span>｜缺收盤價</span><strong class="{'is-empty' if not miss_price else ''}">{html.escape(miss_price_text)}</strong>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        tool_text_col, tool_btn_col = st.columns([4.7, 2.0], vertical_alignment="center")
        with tool_text_col:
            st.markdown(
                f"<div class='maintenance-tools-marker compact-maintenance-row'><h3>資料工具</h3>"
                f"<p>重新計算折溢價屬於資料修復；下載 daily_history.json 則作為備份與檢查用。"
                f"目前 dashboard_data.json 抓取時間：{html.escape(str(data.get('fetched_at', '--')))}。</p></div>",
                unsafe_allow_html=True,
            )
        with tool_btn_col:
            action_cols = st.columns([1, 1])
            with action_cols[0]:
                if st.button("重新計算折溢價", use_container_width=True):
                    current = load_daily_history_map()
                    save_daily_history_map(current)
                    refresh_dashboard_daily_from_history()
                    st.success("已用 NAV + 收盤價重新計算折溢價。")
                    st.rerun()
            with action_cols[1]:
                if DAILY_HISTORY_PATH.exists():
                    st.download_button(
                        "備份下載 daily_history",
                        DAILY_HISTORY_PATH.read_text(encoding="utf-8").encode("utf-8"),
                        "daily_history.json",
                        "application/json",
                        use_container_width=True,
                    )

        if history:
            st.markdown(
                "<div class='maintenance-table-title'>每日資料明細（最近 30 筆）</div>"
                "<div class='maintenance-table-note'>每一列代表一個交易日；欄位出現「缺」代表該日該項資料尚未補齊。</div>"
                + build_daily_history_preview_html(history, limit=30),
                unsafe_allow_html=True,
            )

def render_native_trade_dashboard_page() -> None:
    sync_static_files()
    data = load_dashboard()
    trades, _ = load_trades_with_source()
    status_message = st.session_state.pop("last_update_message", None)
    embedded_native = str(st.query_params.get("embedded", "") or "").strip() == "1"

    st.markdown(
        """
        <style>
          .main .block-container {
            max-width: 100% !important;
            padding: 1rem 2.25rem 1.25rem !important;
            background: #f5f7f7;
          }
          body.native-trades-embedded .main .block-container {
            padding-top: .45rem !important;
          }
          div[data-testid="stHorizontalBlock"]:has(.native-sidebar) {
            gap: 1.1rem !important;
            align-items: stretch !important;
          }
          .native-sidebar {
            min-height: calc(100vh - 76px);
            height: calc(100vh - 76px);
            position: sticky;
            top: 14px;
            display: flex;
            flex-direction: column;
            gap: 18px;
            padding: 24px 20px;
            border-radius: 0;
            background: linear-gradient(180deg, #06251f 0%, #071723 100%);
            color: #e5f2ef;
            overflow: hidden;
          }
          .native-sidebar .brand {
            display: flex;
            gap: 12px;
            align-items: center;
            padding-bottom: 4px;
          }
          .native-sidebar .brand-mark {
            display: inline-flex;
            width: 44px;
            height: 44px;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(16, 185, 129, 0.85);
            border-radius: 10px;
            color: #ffffff;
            font-weight: 900;
          }
          .native-sidebar h1 { margin: 0; color: #fff; font-size: 1.05rem; font-weight: 900; }
          .native-sidebar p { margin: 4px 0 0; color: #b6c9c5; font-size: 0.78rem; }
          .native-sidebar .nav { display: grid; gap: 8px; }
          .native-sidebar .nav a {
            display: flex;
            align-items: center;
            gap: 10px;
            min-height: 44px;
            padding: 10px 12px;
            border-radius: 10px;
            color: #d7e5e2;
            text-decoration: none;
            font-weight: 800;
            font-size: 0.94rem;
          }
          .native-sidebar .nav a.active,
          .native-sidebar .nav a[aria-current="page"] {
            background: linear-gradient(90deg, rgba(16,185,129,.24), rgba(255,255,255,.08));
            color: #ffffff;
            box-shadow: inset 3px 0 0 #10b981;
          }
          .native-sidebar [data-icon] {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 8px;
            background: rgba(255,255,255,.08);
          }
          .native-sidebar .sidebar-signal,
          .native-sidebar .source-card {
            margin-top: auto;
            padding: 14px;
            border: 1px solid rgba(148, 163, 184, .22);
            border-radius: 12px;
            background: rgba(255,255,255,.06);
          }
          .native-sidebar .source-card { margin-top: 0; }
          .native-sidebar .sidebar-signal__dot {
            display: inline-flex;
            width: 24px;
            height: 24px;
            margin-right: 8px;
            border-radius: 999px;
            background: #f59e0b;
            vertical-align: middle;
          }
          .native-sidebar .sidebar-signal strong,
          .native-sidebar .source-card strong { display: block; color: #fff; font-weight: 900; }
          .native-sidebar .sidebar-signal small,
          .native-sidebar .source-card small,
          .native-sidebar .source-card span { color: #b6c9c5; font-size: 0.78rem; }
          .native-hero.desktop-hero {
            position: relative;
            overflow: hidden;
            min-height: 92px;
            margin: 0 0 12px;
            padding: 20px 24px;
            display: grid;
            grid-template-columns: auto minmax(0, 1fr) minmax(360px, .78fr);
            gap: 18px;
            align-items: center;
            border-radius: 14px;
            background: linear-gradient(120deg, #10a46e 0%, #0891b2 45%, #0f5bd7 100%);
            color: #ffffff;
            box-shadow: 0 18px 42px rgba(15, 91, 215, 0.16);
          }
          .native-hero.desktop-hero::after {
            content: "";
            position: absolute;
            inset: -45% -10% auto auto;
            width: 52%;
            height: 150%;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(255,255,255,.24), rgba(255,255,255,0) 62%);
            pointer-events: none;
          }
          .native-hero .desktop-hero__orb {
            position: relative;
            z-index: 1;
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 64px;
            height: 64px;
            border-radius: 999px;
            border: 2px solid rgba(255,255,255,.55);
            background: linear-gradient(135deg, #f59e0b, #f97316);
            box-shadow: 0 10px 28px rgba(15,23,42,.18);
          }
          .native-hero .desktop-hero__orb.yellow { background: linear-gradient(135deg, #f59e0b, #f97316); }
          .native-hero .desktop-hero__orb.red { background: linear-gradient(135deg, #ef4444, #be123c); }
          .native-hero .desktop-hero__orb span { font-size: .95rem; font-weight: 950; line-height: 1; }
          .native-hero .desktop-hero__orb small { margin-top: 5px; font-size: .58rem; font-weight: 800; opacity: .9; }
          .native-hero .desktop-hero__meta { position: relative; z-index: 1; min-width: 0; }
          .native-hero .desktop-hero__meta p { margin: 0 0 4px; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 900; opacity: .9; }
          .native-hero .desktop-hero__meta h2 { margin: 0 0 7px; font-size: 1.55rem; line-height: 1.15; font-weight: 950; color: #fff; }
          .native-hero .ui-status-chip {
            display: inline-flex;
            max-width: 100%;
            align-items: center;
            padding: 4px 9px;
            border-radius: 999px;
            background: rgba(245, 158, 11, .22);
            color: #78350f;
            font-size: .72rem;
            font-weight: 850;
            white-space: nowrap;
          }
          .native-hero .desktop-hero-summary {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
          }
          .native-hero .desktop-hero-summary-card {
            min-height: 56px;
            padding: 11px 14px;
            border-radius: 10px;
            background: rgba(255,255,255,.9);
            color: #0f172a;
          }
          .native-hero .desktop-hero-summary-card span { display:block; color:#64748b; font-size:.78rem; font-weight:800; margin-bottom:4px; }
          .native-hero .desktop-hero-summary-card strong { display:block; color:#0f172a; font-size:1rem; font-weight:950; }
          .native-trade-log {
            margin-top: 0 !important;
            border-radius: 14px !important;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08) !important;
          }
          .native-trade-stats { grid-template-columns: repeat(7, minmax(0, 1fr)); }
          .mobile-trade-protection { display: none; }
          @media (max-width: 1200px) {
            .native-trade-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
            .native-hero.desktop-hero { grid-template-columns: auto 1fr; }
            .native-hero .desktop-hero-summary { grid-column: 1 / -1; }
          }
          @media (max-width: 760px) {
            .main .block-container { padding: 0 !important; }
            div[data-testid="stHorizontalBlock"]:has(.native-sidebar) { display: none !important; }
            .mobile-trade-protection {
              display: block;
              margin: 10px;
              padding: 14px;
              border-radius: 14px;
              background: #ecfdf5;
              color: #065f46;
              font-weight: 800;
            }
          }
        </style>
        <div class="mobile-trade-protection">手機版只保留首頁總覽與更新資料按鈕，交易紀錄請回到桌機版操作。</div>
        """,
        unsafe_allow_html=True,
    )

    if embedded_native:
        st.markdown(
            """
            <style>
              div[data-testid="stAppViewBlockContainer"] { padding-top: .35rem !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        top_left, top_right = st.columns([1, 5])
        with top_left:
            if st.button("更新資料", type="primary", use_container_width=True):
                with st.spinner("正在抓取價格、月規模、配息 54C 與前十大持股..."):
                    ok, message = run_update()
                    if ok:
                        sync_static_files()
                        st.success("資料更新完成")
                        st.rerun()
                    st.error("資料更新失敗")
                    st.code(message[-2000:])
        with top_right:
            st.caption(f"目前資料抓取時間：{data.get('fetched_at', '--')}")

    left, right = st.columns([0.86, 6.2])
    with left:
        render_native_sidebar("trades")
    with right:
        render_native_trade_hero(data, trades)
        render_native_trade_log_section(status_message)




def render_trade_entry_page() -> None:
    """Standalone Streamlit-native transaction entry/import page.

    This page is intentionally opened from the HTML dashboard in a new tab.
    It keeps the original dashboard UI untouched while using real Streamlit
    widgets to write safely to Google Sheets.
    """
    data = load_dashboard()
    trades, trades_source = load_trades_with_source()
    status_message = st.session_state.pop("last_update_message", None)
    latest = data.get("latest_daily", {})
    dividends = data.get("dividends", [])
    position = calc_position(trades, dividends)
    market_price = float(latest.get("market_price") or 0)
    market_value = position["shares"] * market_price
    unrealized = market_value - position["cost"]
    total_return = unrealized + position["cumulative_dividend"] + position["realized"]

    st.markdown(
        """
        <style>
          .main .block-container {
            max-width: 1180px !important;
            padding-top: 1.25rem !important;
            padding-bottom: 2rem !important;
          }
          .entry-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            margin-bottom: 16px;
            padding: 22px 24px;
            border-radius: 18px;
            background: linear-gradient(135deg, #059669 0%, #0891b2 48%, #1d4ed8 100%);
            color: white;
            box-shadow: 0 18px 44px rgba(15, 23, 42, 0.18);
          }
          .entry-hero p { margin: 0 0 4px; opacity: .78; font-size: .78rem; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
          .entry-hero h1 { margin: 0; font-size: 1.55rem; font-weight: 950; letter-spacing: .02em; }
          .entry-hero small { display:block; margin-top: 8px; opacity:.82; }
          .entry-hero__cards { display:grid; grid-template-columns: repeat(2, minmax(150px, 1fr)); gap: 10px; min-width: 340px; }
          .entry-hero-card { padding: 12px 14px; border-radius: 12px; background: rgba(255,255,255,.92); color:#0f172a; }
          .entry-hero-card span { display:block; color:#64748b; font-size:.8rem; font-weight:800; }
          .entry-hero-card strong { display:block; margin-top:4px; font-size:1.08rem; font-weight:950; }
          .entry-panel {
            margin: 14px 0;
            padding: 18px;
            border: 1px solid #d9e2df;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
          }
          .entry-panel h3 { margin: 0 0 4px; color:#0f172a; font-size: 1.1rem; font-weight: 950; }
          .entry-panel p { margin: 0 0 12px; color:#64748b; font-size:.92rem; line-height:1.55; }
          div[data-testid="stForm"] {
            border: 1px solid #d9e2df;
            border-radius: 14px;
            padding: 16px 18px 18px;
            background: #fbfcfc;
          }
          div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
          div[data-testid="stButton"] button[kind="primary"] {
            background: #059669 !important;
            border: 0 !important;
            border-radius: 10px !important;
            color: #ffffff !important;
            font-weight: 900 !important;
            min-height: 42px !important;
          }
          div[data-testid="stDownloadButton"] button,
          div[data-testid="stLinkButton"] a {
            border-radius: 10px !important;
            font-weight: 850 !important;
          }
          .entry-success {
            margin: 0 0 12px;
            padding: 12px 14px;
            border: 1px solid #bbf7d0;
            border-radius: 12px;
            background: #f0fdf4;
            color: #166534;
            font-weight: 850;
          }
          .entry-source {
            margin-top: 8px;
            color:#64748b;
            font-size:.82rem;
          }

          /* UI19: enlarge and separate the native transaction form fields. */
          div[data-testid="stForm"] {
            margin-top: 6px !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 18px !important;
            padding: 24px 24px 22px !important;
            background: #f1f5f9 !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.9), 0 14px 32px rgba(15,23,42,.08) !important;
          }
          div[data-testid="stForm"] label,
          div[data-testid="stForm"] [data-testid="stWidgetLabel"] {
            color: #0f172a !important;
            font-size: 1.02rem !important;
            font-weight: 900 !important;
            margin-bottom: 6px !important;
          }
          div[data-testid="stForm"] input,
          div[data-testid="stForm"] textarea,
          div[data-testid="stForm"] [data-baseweb="input"] input {
            min-height: 52px !important;
            height: 52px !important;
            border-radius: 12px !important;
            background: #ffffff !important;
            color: #0f172a !important;
            font-size: 1.06rem !important;
            font-weight: 750 !important;
          }
          div[data-testid="stForm"] [data-baseweb="input"],
          div[data-testid="stForm"] [data-baseweb="select"] > div,
          div[data-testid="stForm"] [data-baseweb="textarea"] {
            min-height: 52px !important;
            border: 1px solid #94a3b8 !important;
            border-radius: 12px !important;
            background: #ffffff !important;
            box-shadow: 0 1px 0 rgba(15,23,42,.04) !important;
          }
          div[data-testid="stForm"] [data-baseweb="select"] span,
          div[data-testid="stForm"] [data-baseweb="select"] input {
            font-size: 1.06rem !important;
            font-weight: 750 !important;
            color: #0f172a !important;
          }
          div[data-testid="stForm"] [data-baseweb="radio"] {
            gap: 16px !important;
          }
          div[data-testid="stForm"] [data-baseweb="radio"] label {
            min-height: 42px !important;
            padding: 4px 10px !important;
            border-radius: 10px !important;
          }
          div[data-testid="stForm"] [data-baseweb="radio"] div {
            font-size: 1.05rem !important;
            font-weight: 850 !important;
          }
          div[data-testid="stForm"] button[aria-label="Increase"],
          div[data-testid="stForm"] button[aria-label="Decrease"],
          div[data-testid="stForm"] [data-testid="stNumberInputStepUp"],
          div[data-testid="stForm"] [data-testid="stNumberInputStepDown"] {
            min-width: 42px !important;
            width: 42px !important;
            min-height: 42px !important;
            height: 42px !important;
            border-radius: 10px !important;
            background: #059669 !important;
            color: #ffffff !important;
          }
          div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
            min-height: 52px !important;
            font-size: 1.06rem !important;
            border-radius: 12px !important;
          }
          [data-baseweb="popover"],
          [data-baseweb="menu"],
          [role="listbox"] {
            z-index: 999999 !important;
            font-size: 1.06rem !important;
          }
          [data-baseweb="menu"] li,
          [role="option"] {
            min-height: 42px !important;
            font-size: 1.06rem !important;
          }
          [data-baseweb="calendar"],
          [data-baseweb="calendar"] * {
            font-size: 1.02rem !important;
          }
          [data-baseweb="calendar"] {
            transform: scale(1.08);
            transform-origin: top left;
          }

          /* UI28: keep the recent-trades note outside the table so it is never covered by dataframe header. */
          .entry-recent-panel {
            margin-top: 18px;
            border: 1px solid #d9e2df;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
            overflow: hidden;
          }
          .entry-recent-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 14px 16px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            color: #0f172a;
            font-size: 1.02rem;
            font-weight: 950;
            line-height: 1.45;
            position: relative;
            z-index: 2;
          }
          .entry-recent-header span {
            color: #64748b;
            font-size: .92rem;
            font-weight: 800;
            text-align: right;
          }
          .entry-recent-scroll {
            max-height: 260px;
            overflow: auto;
          }
          .entry-recent-table {
            width: 100%;
            border-collapse: collapse;
            font-size: .96rem;
            color: #0f172a;
          }
          .entry-recent-table th {
            position: sticky;
            top: 0;
            z-index: 1;
            background: #eef3f1;
            color: #475569;
            font-size: .88rem;
            font-weight: 950;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid #dbe5e2;
          }
          .entry-recent-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #edf2f0;
            vertical-align: middle;
          }
          .entry-recent-table tr:last-child td { border-bottom: 0; }

          @media (max-width: 780px) {
            .entry-hero { display:grid; }
            .entry-hero__cards { min-width:0; grid-template-columns: 1fr; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <section class="entry-hero">
          <div>
            <p>Google Sheets Trade Entry</p>
            <h1>00919 新增交易 / 匯入資料</h1>
            <small>這一頁是獨立 Streamlit 原生表單，專門處理 Google Sheets 寫入；完成後回 Dashboard 按「更新資料」同步。</small>
          </div>
          <div class="entry-hero__cards">
            <div class="entry-hero-card"><span>目前股數</span><strong>{money(position['shares'])} 股</strong></div>
            <div class="entry-hero-card"><span>含息損益估算</span><strong>${money(total_return)}</strong></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    top_cols = st.columns([1.0, 1.0, 1.0, 4.2])
    with top_cols[0]:
        st.link_button("回 Dashboard", "/", use_container_width=True)
    with top_cols[1]:
        st.download_button(
            "匯出資料",
            trades_to_csv(trades),
            "00919_trades.csv",
            "text/csv",
            use_container_width=True,
        )
    with top_cols[2]:
        st.download_button(
            "下載範本",
            "trade_date,action,shares,price,note_type,note\n2026-05-27,BUY,1000,27.00,其他,範例\n",
            "00919_trade_template.csv",
            "text/csv",
            use_container_width=True,
        )

    if status_message:
        st.markdown(f"<div class='entry-success'>{html.escape(status_message)}。可以關閉此分頁，回 Dashboard 按更新資料。</div>", unsafe_allow_html=True)

    st.markdown("<div class='entry-panel'><h3>新增單筆交易</h3><p>送出後會直接 append 到 Google Sheets Trades 工作表。</p></div>", unsafe_allow_html=True)
    if append_trade_to_google_sheets is None:
        st.warning("Google Sheets 寫入模組尚未啟用；表單仍顯示，但送出時會提示設定錯誤。" + (f"目前錯誤：{GOOGLE_SHEETS_IMPORT_ERROR}" if GOOGLE_SHEETS_IMPORT_ERROR else ""))

    with st.form("standalone_google_sheets_trade_entry_form", clear_on_submit=True):
        row1 = st.columns([1.0, 1.25, 1.1, 1.1])
        action_label = row1[0].radio("買 / 賣", ["買入", "賣出"], horizontal=True)
        trade_date_value = row1[1].date_input("交易日期", value=date.today())
        shares = row1[2].number_input("交易股數（股）", min_value=1, step=1, value=1)
        price = row1[3].number_input("平均成本 / 成交價", min_value=0.0, step=0.01, value=0.0, format="%.2f")
        row2 = st.columns([1.25, 2.75])
        note_type = row2[0].selectbox(
            "資金來源 / 備註分類",
            ["股息再投入", "薪資投入", "年終投入", "定期投入", "閒置資金投入", "再平衡調整", "部位調整", "其他"],
        )
        note = row2[1].text_input("備註", placeholder="可留空或補充說明，例如：定期投入、加碼原因")
        submitted = st.form_submit_button("新增交易並寫入 Google Sheets", use_container_width=True)

    if submitted:
        action = "BUY" if action_label == "買入" else "SELL"
        if not trade_date_value or int(shares) <= 0 or float(price) <= 0:
            st.error("請確認日期、股數與成交價都已正確填寫。")
        elif append_trade_to_google_sheets is None:
            st.error("寫入 Google Sheets 失敗：Google Sheets 寫入模組尚未啟用。")
            st.info("請確認 requirements.txt 已安裝 gspread / google-auth，並確認 .streamlit/secrets.toml 已設定。" + (f"目前錯誤：{GOOGLE_SHEETS_IMPORT_ERROR}" if GOOGLE_SHEETS_IMPORT_ERROR else ""))
        else:
            trade = {
                "trade_date": trade_date_value.strftime("%Y-%m-%d"),
                "action": action,
                "shares": int(shares),
                "price": float(price),
                "note_type": note_type,
                "note": note.strip(),
                "source": "standalone_streamlit_form",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            try:
                append_trade_to_google_sheets(trade)
            except Exception as exc:
                st.error("寫入 Google Sheets 失敗")
                st.info(google_sheets_write_help())
                st.code(f"{type(exc).__name__}: {exc}")
            else:
                st.session_state["last_update_message"] = "新增交易已寫入 Google Sheets"
                st.rerun()

    st.markdown("<div class='entry-panel'><h3>批次匯入 CSV</h3><p>可下載範本填寫後上傳；系統會略過已存在的相同交易。</p></div>", unsafe_allow_html=True)
    uploaded_trades = st.file_uploader("選擇交易 CSV 檔", type=["csv"], key="standalone_trade_csv_importer")
    valid_preview_rows: list[dict] = []
    if uploaded_trades is not None:
        try:
            text = uploaded_trades.getvalue().decode("utf-8-sig")
            preview_rows = [normalize_trade(row) for row in csv.DictReader(io.StringIO(text))]
            valid_preview_rows = [row for row in preview_rows if row.get("trade_date") and int(row.get("shares") or 0) > 0 and float(row.get("price") or 0) > 0]
            st.info(f"已讀取 {len(preview_rows)} 筆，其中 {len(valid_preview_rows)} 筆格式可匯入。")
            if valid_preview_rows:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "交易日期": row.get("trade_date"),
                            "買 / 賣": "賣出" if str(row.get("action") or "").lower() in {"sell", "s", "賣", "賣出"} else "買入",
                            "股數": int(row.get("shares") or 0),
                            "價格": float(row.get("price") or 0),
                            "分類": row.get("note_type") or "其他",
                            "備註": row.get("note") or "",
                        }
                        for row in valid_preview_rows[:12]
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as exc:
            st.error("CSV 讀取失敗，請確認欄位名稱與編碼。")
            st.code(f"{type(exc).__name__}: {exc}")

    import_cols = st.columns([1.2, 5])
    do_import = import_cols[0].button("確認匯入", type="primary", use_container_width=True)
    if do_import:
        if uploaded_trades is None:
            st.error("請先選擇 CSV 檔案。")
        elif append_trade_to_google_sheets is None:
            st.error("目前 Google Sheets 寫入模組尚未啟用，無法匯入到正式資料庫。")
        else:
            try:
                text = uploaded_trades.getvalue().decode("utf-8-sig")
                imported_rows = [normalize_trade(row) for row in csv.DictReader(io.StringIO(text))]
                imported_rows = [row for row in imported_rows if row.get("trade_date") and int(row.get("shares") or 0) > 0 and float(row.get("price") or 0) > 0]
                existing_keys = {
                    (
                        str(row.get("trade_date") or ""),
                        "sell" if str(row.get("action") or "").lower() in {"sell", "s", "賣", "賣出"} else "buy",
                        int(row.get("shares") or 0),
                        round(float(row.get("price") or 0), 4),
                        str(row.get("note") or ""),
                    )
                    for row in [normalize_trade(item) for item in trades]
                }
                appended_count = 0
                skipped_count = 0
                for row in imported_rows:
                    action_norm = "sell" if str(row.get("action") or "").lower() in {"sell", "s", "賣", "賣出"} else "buy"
                    key = (
                        str(row.get("trade_date") or ""),
                        action_norm,
                        int(row.get("shares") or 0),
                        round(float(row.get("price") or 0), 4),
                        str(row.get("note") or ""),
                    )
                    if key in existing_keys:
                        skipped_count += 1
                        continue
                    append_trade_to_google_sheets({
                        "trade_date": row.get("trade_date"),
                        "action": "SELL" if action_norm == "sell" else "BUY",
                        "shares": int(row.get("shares") or 0),
                        "price": float(row.get("price") or 0),
                        "note_type": row.get("note_type") or "其他",
                        "note": row.get("note") or "",
                        "source": "standalone_csv_import",
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    })
                    existing_keys.add(key)
                    appended_count += 1
                st.session_state["last_update_message"] = f"匯入完成：新增 {appended_count} 筆，略過重複 {skipped_count} 筆"
                st.rerun()
            except Exception as exc:
                st.error("匯入失敗")
                st.code(f"{type(exc).__name__}: {exc}")

    recent = pd.DataFrame([normalize_trade(row) for row in trades])
    if not recent.empty:
        recent = recent.sort_values("trade_date", ascending=False)
        recent_rows = []
        for _, row in recent.iterrows():
            action_raw = str(row.get("action") or "").lower()
            action_label = "賣出" if action_raw in {"sell", "s", "賣", "賣出"} else "買入"
            recent_rows.append(
                "<tr>"
                f"<td>{html.escape(str(row.get('trade_date') or ''))}</td>"
                f"<td>{html.escape(action_label)}</td>"
                f"<td>{money(pd.to_numeric(row.get('shares'), errors='coerce') or 0)} 股</td>"
                f"<td>{float(pd.to_numeric(row.get('price'), errors='coerce') or 0):.2f}</td>"
                f"<td>{html.escape(str(row.get('note_type') or '其他'))}</td>"
                f"<td>{html.escape(str(row.get('note') or ''))}</td>"
                "</tr>"
            )
        source_message = html.escape(trades_source.get("message", ""))
        st.markdown(
            f"""
            <section class="entry-recent-panel">
              <div class="entry-recent-header">
                <strong>最近交易預覽</strong>
                <span>{source_message}</span>
              </div>
              <div class="entry-recent-scroll">
                <table class="entry-recent-table">
                  <thead>
                    <tr>
                      <th>交易日期</th>
                      <th>買 / 賣</th>
                      <th>交易股數</th>
                      <th>成交價</th>
                      <th>分類</th>
                      <th>備註</th>
                    </tr>
                  </thead>
                  <tbody>{''.join(recent_rows)}</tbody>
                </table>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

def render_embedded_html_ui(initial_hash: str = "#home") -> None:
    sync_static_files()
    st.session_state.pop("last_update_message", None)
    left, right = st.columns([1, 5])
    with left:
        if st.button("更新資料", type="primary", use_container_width=True):
            with st.spinner("正在抓取價格、月規模、配息 54C 與前十大持股..."):
                ok, message = run_update()
                if ok:
                    sync_static_files()
                    # UI59: 更新完成一律回首頁總覽，避免沿用上一個 target_page
                    # 導致更新後跳到燈號設定或其他分頁。
                    st.query_params.clear()
                    st.query_params["target_page"] = "home"
                    st.success("資料更新完成")
                    st.rerun()
                st.error("資料更新失敗")
                st.code(message[-2000:])
    with right:
        fetched = load_dashboard().get("fetched_at", "--")
        st.caption(f"目前資料抓取時間：{fetched}")

    render_iframe_navigation_bridge()
    components.html(build_embedded_dashboard_html("full", initial_hash=initial_hash), height=900, scrolling=True)


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
    consume_direct_append_test_request()
    consume_embedded_trade_append_request()
    consume_embedded_trade_sync_request()
    consume_embedded_update_request()

    native_page = str(st.query_params.get("native_page", "") or "").strip()
    target_page = str(st.query_params.get("target_page", "home") or "home").strip()
    if native_page in {"trade_entry", "add_trade"}:
        render_trade_entry_page()
        return
    if native_page == "trades":
        render_native_trade_dashboard_page()
        return
    if native_page in {"data_maintenance", "data-maintenance"}:
        render_native_data_maintenance_page()
        return

    render_embedded_html_ui(target_page_hash_from_query())


if __name__ == "__main__":
    main()
