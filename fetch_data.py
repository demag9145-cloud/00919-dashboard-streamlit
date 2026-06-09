import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DAILY_HISTORY_PATH = DATA_DIR / "daily_history.json"

MONEYDJ_NAV_URL = "https://www.moneydj.com/etf/x/basic/basic0003.xdjhtm?etfid=00919.tw"
MONEYDJ_MONTHLY_SIZE_URL = "https://www.moneydj.com/ETF/X/Basic/Basic0019.xdjhtm?etfid=00919.TW"
MONEYDJ_HOLDINGS_URL = "https://www.moneydj.com/etf/x/basic/basic0007.xdjhtm?etfid=00919.tw"
MONEYDJ_DIVIDEND_URL = "https://www.moneydj.com/etf/x/basic/basic0005.xdjhtm?etfid=00919.tw"
ETFORTUNE_DIVIDEND_URL = (
    "https://www.twse.com.tw/zh/ETFortune/dividendList"
    "?stkNo=00919&startDate=2022&endDate=2026"
)
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
ETFORTUNE_INFO_URL = "https://www.twse.com.tw/zh/ETFortune/etfInfo/00919"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/00919.TW"
CAPITALFUND_TREND_URL = "https://www.capitalfund.com.tw/etf/product/detail/195/trend"
CAPITALFUND_PORTFOLIO_URL = "https://www.capitalfund.com.tw/etf/product/detail/195/portfolio"
CAPITALFUND_BUYBACK_URL = "https://www.capitalfund.com.tw/etf/product/detail/195/buyback"
CAPITALFUND_INTEREST_URL = "https://www.capitalfund.com.tw/etf/product/detail/195/interest"


def opener():
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
    )


def fetch_text(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/json",
        },
    )
    with opener().open(req, timeout=25) as resp:
        return resp.read().decode("utf-8", "ignore")


def clean_text(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_number(value):
    """Parse a numeric value from scraped table text.

    MoneyDJ occasionally returns merged cell text such as
    "-4.4N/A 2026/041317373-0.83" when the page layout changes or
    hidden/mobile cells are included.  Older versions called float() on the
    whole cleaned string and crashed during manual refresh.  This parser keeps
    the first meaningful number before an N/A marker and returns None for empty
    or non-numeric cells.
    """
    text = clean_text(str(value)).replace(",", "").replace("(台幣)", "").replace("%", "").strip()
    if not text:
        return None

    upper = text.upper()
    if upper in {"-", "--", "N/A", "NA", "NONE", "NULL"}:
        return None

    # If N/A appears after a real number, keep the value before it; if N/A is
    # the only meaningful content, treat the cell as missing.
    na_pos = upper.find("N/A")
    if na_pos >= 0:
        before_na = text[:na_pos].strip()
        text = before_na if before_na else ""
    if not text:
        return None

    # Ignore pure date-like strings such as 2026/04.
    if re.fullmatch(r"\d{4}[/-]\d{1,2}(?:[/-]\d{1,2})?", text):
        return None

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def roc_date_to_iso(value):
    value = clean_text(value)
    m = re.match(r"(\d{3})[年/](\d{1,2})[月/](\d{1,2})", value)
    if not m:
        return value
    year = int(m.group(1)) + 1911
    return f"{year:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def iso_to_twse_month(date_value):
    return date_value[:7].replace("-", "") + "01"




def roc_ymd_to_iso(year, month, day):
    return f"{int(year) + 1911:04d}-{int(month):02d}-{int(day):02d}"


def normalize_date_text(value):
    """Convert common Taiwan ETF date formats to ISO yyyy-mm-dd."""
    text = clean_text(str(value)).replace(".", "/").replace("-", "/")
    roc = re.search(r"(\d{3})年(\d{1,2})月(\d{1,2})日", text)
    if roc:
        return roc_ymd_to_iso(roc.group(1), roc.group(2), roc.group(3))
    western = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", text)
    if western:
        return f"{int(western.group(1)):04d}-{int(western.group(2)):02d}-{int(western.group(3)):02d}"
    return None


def current_twse_dividend_url():
    year = datetime.now(ZoneInfo("Asia/Taipei")).year
    return (
        "https://www.twse.com.tw/zh/ETFortune/dividendList"
        f"?stkNo=00919&startDate=2022&endDate={year}"
    )


def to_iso_date(value):
    text = clean_text(str(value)).replace(".", "/").replace("-", "/")
    match = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", text)
    if not match:
        return None
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def parse_twd_amount(value):
    text = clean_text(str(value)).replace("TWD", "").replace("NTD", "")
    return parse_number(text)


def pct_to_number(value):
    return parse_number(str(value).replace("％", "%"))



def normalize_beneficiary_count(value):
    """Normalize 00919 beneficiary count parsed from MoneyDJ monthly table.

    MoneyDJ can glue hidden/mobile cells together.  A known failure is
    1,328,370 being parsed as 13,283,701, which makes the monthly chart spike.
    Keep normal 6~7 digit values, and repair one-extra-trailing-digit values
    when dividing by 10 falls back into the sane range.
    """
    if value is None:
        return None
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if 100_000 <= number <= 5_000_000:
        return number
    if number > 5_000_000:
        divided_by_10 = int(round(number / 10))
        if 100_000 <= divided_by_10 <= 5_000_000:
            return divided_by_10
    return None


def recompute_beneficiary_change_pct(rows):
    """Use the normalized beneficiary counts to keep month-change % consistent."""
    previous_count = None
    for row in rows:
        current_count = normalize_beneficiary_count(row.get("beneficiary_count"))
        row["beneficiary_count"] = current_count
        if current_count is not None and previous_count:
            row["beneficiary_change_pct"] = round(((current_count - previous_count) / previous_count) * 100, 2)
        previous_count = current_count if current_count is not None else previous_count
    return rows

def first_match_number(text, pattern):
    match = re.search(pattern, text, flags=re.S)
    return parse_twd_amount(match.group(1)) if match else None


def first_match_text(text, pattern):
    match = re.search(pattern, text, flags=re.S)
    return clean_text(match.group(1)) if match else None



def fetch_etfortune_current_info():
    """Fetch current AUM / beneficiary summary from TWSE ETF e添富.

    This is a latest-summary source, not a strict month-end source.  It is used
    to enrich the current month while MoneyDJ's monthly AUM row is still N/A.
    Completed monthly AUM rows remain protected by monthly_history.json and are
    never overwritten by empty values.
    """
    html = fetch_text(ETFORTUNE_INFO_URL)
    text = clean_text(html)
    aum_100m = None
    beneficiary_count = None
    date_value = None

    aum_match = re.search(r"資產規模\(億元\)\s*([0-9,]+(?:\.\d+)?)\s*億元", text)
    if aum_match:
        aum_100m = parse_number(aum_match.group(1))

    beneficiary_match = re.search(r"受益人次\(萬人\)\s*([0-9,]+(?:\.\d+)?)\s*萬人", text)
    if beneficiary_match:
        beneficiary_wan = parse_number(beneficiary_match.group(1))
        if beneficiary_wan is not None:
            beneficiary_count = int(round(beneficiary_wan * 10000))

    date_match = re.search(r"資料日期[:：]\s*(20\d{2}-\d{1,2}-\d{1,2})", text)
    if not date_match:
        date_match = re.search(r"資料日期[:：]\s*(20\d{2}/\d{1,2}/\d{1,2})", text)
    if date_match:
        date_value = to_iso_date(date_match.group(1))

    # The page can expose a performance date later in the text.  If the summary
    # date is not explicit, using today's month would make the row unstable, so
    # leave data_date empty and let the caller decide whether to merge it.
    return {
        "data_date": date_value,
        "aum_100m_twd": aum_100m,
        "aum_million_twd": round(aum_100m * 100, 4) if aum_100m is not None else None,
        "beneficiary_count": beneficiary_count,
        "source": "TWSE e添富最新摘要",
        "aum_is_current_snapshot": True,
    }



def build_latest_snapshot(capital_buyback=None, capital_portfolio=None, etfortune_info=None):
    """Build a latest AUM/NAV snapshot without contaminating monthly history.

    Monthly AUM is a month-end series and should stay sourced from MoneyDJ/TWSE
    monthly data.  Capital Fund portfolio/buyback pages and TWSE ETF Fortune
    summary are latest snapshots, so they are stored separately for homepage
    cards, source diagnostics and cross-checks.
    """
    candidates = []
    for source in (capital_buyback or {}, capital_portfolio or {}, etfortune_info or {}):
        if not isinstance(source, dict) or not source:
            continue
        net_asset = source.get("fund_net_asset_value_twd")
        aum_100m = source.get("aum_100m_twd")
        aum_million = source.get("aum_million_twd")
        if aum_100m is None and net_asset:
            aum_100m = round(net_asset / 100_000_000, 4)
        if aum_million is None and net_asset:
            aum_million = round(net_asset / 1_000_000, 4)
        if net_asset is None and aum_100m is not None:
            net_asset = round(aum_100m * 100_000_000)
        has_core = any(value is not None for value in (net_asset, aum_100m, aum_million, source.get("nav"), source.get("issued_units"), source.get("beneficiary_count")))
        if not has_core:
            continue
        candidates.append({
            "data_date": source.get("data_date"),
            "fund_net_asset_value_twd": net_asset,
            "aum_100m_twd": aum_100m,
            "aum_million_twd": aum_million,
            "nav": source.get("nav"),
            "issued_units": source.get("issued_units"),
            "issued_lots": source.get("issued_lots"),
            "beneficiary_count": source.get("beneficiary_count"),
            "source": source.get("source") or "官方最新摘要",
            "is_monthly_aum": False,
            "snapshot_type": "latest",
        })
    priority = {
        "群益投信申購買回清單": 1,
        "群益投信投資組合": 2,
        "TWSE e添富最新摘要": 3,
    }
    candidates.sort(key=lambda row: (priority.get(row.get("source"), 99), row.get("data_date") or "9999-99-99"))
    primary = candidates[0] if candidates else {}
    return {
        **primary,
        "candidates": candidates,
        "note": "最新快照只供首頁與資料維護顯示，不回填月度 AUM。",
    }


def build_source_inventory():
    return {
        "daily_price": {
            "label": "每日收盤價 / 成交量",
            "primary": "Yahoo / TWSE 日成交",
            "fallback": ["群益淨值走勢頁收盤價", "舊有效 daily_history"],
            "trust": "高",
            "stability": "高",
            "fields": ["收盤價", "市價", "成交股數", "成交張數"],
        },
        "nav": {
            "label": "NAV / 淨值",
            "primary": "群益淨值與績效走勢",
            "fallback": ["MoneyDJ 近 30 日", "navs.xlsx 匯入底稿", "舊有效 daily_history"],
            "trust": "最高",
            "stability": "中高",
            "fields": ["官方 NAV", "NAV 日期", "群益頁面收盤價", "網站折溢價驗證值"],
        },
        "monthly_aum": {
            "label": "月度 AUM / 受益人數",
            "primary": "MoneyDJ 月規模表",
            "fallback": ["TWSE / 其他月度來源（待擴充）"],
            "trust": "中高",
            "stability": "中",
            "fields": ["月份", "受益人數", "月增率", "月度 AUM"],
            "rule": "群益與 TWSE 最新 AUM 只做快照，不補月度 AUM。",
        },
        "latest_snapshot": {
            "label": "最新 AUM / 單位數快照",
            "primary": "群益申購買回清單",
            "fallback": ["群益投資組合", "TWSE e添富最新摘要"],
            "trust": "最高",
            "stability": "高",
            "fields": ["基金淨資產價值", "每單位 NAV", "已發行單位數", "最新受益人次"],
        },
        "holdings": {
            "label": "持股 / 前十大 / 產業",
            "primary": "群益投資組合（官方確認）",
            "fallback": ["群益申購買回清單", "MoneyDJ 持股與產業分布（較快時先標示）"],
            "trust": "最高",
            "stability": "高",
            "fields": ["持股代號", "名稱", "權重", "股數", "期貨", "其他資產"],
            "rule": "若非官方來源較快，可先顯示並標示來源；正式判斷仍以群益官網為主。",
        },
        "dividend": {
            "label": "配息 / 54C（第三階段）",
            "primary": "事件以群益官方確認；組成以 TWSE e添富 / 公告為主",
            "fallback": ["MoneyDJ 最新配息事件（先顯示 pending）", "群益公告 PDF", "券商所得資料"],
            "trust": "高",
            "stability": "中高",
            "fields": ["除息日", "發放日", "每單位配息", "54C", "收益平準金", "資本利得"],
            "rule": "MoneyDJ 若較快公布配息，可先畫柱狀圖並標示 pending；54C / 收益平準金 / 資本利得待 TWSE 或官方補齊後改 complete。",
        },
    }

def fetch_capitalfund_trend_rows():
    """Fetch recent official NAV rows from Capital Fund's 00919 trend page.

    The page exposes a recent NAV / close / discount table in HTML text.  It also
    has a custom-range download UI, but the endpoint can change.  This parser is
    intentionally conservative: it uses the visible recent rows as the primary
    official NAV source and lets daily_history.json preserve older valid rows.
    """
    html = fetch_text(CAPITALFUND_TREND_URL)
    text = clean_text(html)
    rows_by_date = {}

    pattern = re.compile(
        r"(?P<nav>\d+(?:\.\d+)?)\s*\((?P<nav_date>20\d{2}/\d{1,2}/\d{1,2})\)\s*"
        r"[-+]?\d+(?:\.\d+)?%\s*查看\s*"
        r"(?P<close>\d+(?:\.\d+)?)\s*\((?P<close_date>20\d{2}/\d{1,2}/\d{1,2})\)\s*"
        r"(?P<discount_amount>[-+]?\d+(?:\.\d+)?)\s*\(\s*(?P<discount_pct>[-+]?\d+(?:\.\d+)?)\s*%\s*\)",
        flags=re.S,
    )
    for match in pattern.finditer(text):
        date_value = to_iso_date(match.group("nav_date"))
        close_date = to_iso_date(match.group("close_date"))
        if not date_value:
            continue
        nav = parse_number(match.group("nav"))
        close = parse_number(match.group("close"))
        amount = parse_number(match.group("discount_amount"))
        pct = parse_number(match.group("discount_pct"))
        if nav is None:
            continue
        rows_by_date[date_value] = {
            "date": date_value,
            "nav": nav,
            "official_nav": nav,
            "market_price": close,
            "capitalfund_market_close": close,
            "capitalfund_close_date": close_date,
            "capitalfund_premium_discount_amount": amount,
            "capitalfund_premium_discount_pct": pct,
            "premium_discount_pct": pct,
            "source": "群益投信官網",
            "nav_source": "群益淨值走勢",
            "is_estimated_nav": False,
        }

    return [rows_by_date[date] for date in sorted(rows_by_date)]


def parse_capitalfund_holdings_from_text(text):
    rows = []
    seen = set()
    # The Capital Fund page includes desktop and mobile duplicate blocks.  The
    # rows with stock shares are the reliable complete rows; later duplicate
    # mobile rows usually omit shares, so this pattern naturally skips them.
    for code, name, weight, shares in re.findall(
        r"\b(\d{4})\s+([^\s]+?)\s+([0-9]+(?:\.[0-9]+)?)%\s+([0-9,]{4,})",
        text,
    ):
        if code in seen:
            continue
        seen.add(code)
        rows.append(
            {
                "rank": len(rows) + 1,
                "code": code,
                "name": clean_text(name),
                "weight_pct": parse_number(weight),
                "shares": int(parse_number(shares) or 0),
            }
        )
    return rows


def parse_capitalfund_futures_from_text(text):
    rows = []
    future_match = re.search(
        r"台指期(\d{6}).*?持股權重\(%\)\s*([0-9]+(?:\.[0-9]+)?)%\s*口數\s*([0-9,]+)\s*契約年月\s*(\d{6})",
        text,
        flags=re.S,
    )
    if future_match:
        rows.append(
            {
                "name": f"台指期{future_match.group(1)}",
                "weight_pct": parse_number(future_match.group(2)),
                "contracts": int(parse_number(future_match.group(3)) or 0),
                "contract_month": future_match.group(4),
            }
        )
    return rows


def parse_capitalfund_other_assets(text):
    return {
        "margin_twd": first_match_number(text, r"保證金\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
        "receivable_payable_securities_twd": first_match_number(text, r"應收付證券款\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
        "payable_redemption_twd": first_match_number(text, r"應付贖回款\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
        "cash_twd": first_match_number(text, r"現金\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
    }


def fetch_capitalfund_portfolio_data():
    html = fetch_text(CAPITALFUND_PORTFOLIO_URL)
    text = clean_text(html)
    holdings = parse_capitalfund_holdings_from_text(text)
    latest_date = None
    latest_date_match = re.search(r"最新預估淨值\s*[0-9.]+\s*(20\d{2}/\d{1,2}/\d{1,2})", text)
    if latest_date_match:
        latest_date = to_iso_date(latest_date_match.group(1))
    net_asset = first_match_number(text, r"基金淨資產價值\(元\)\s*TWD\s*([0-9,]+(?:\.\d+)?)")
    nav = first_match_number(text, r"每受益權單位淨資產價值\(元\)-台幣交易\s*TWD\s*([0-9,]+(?:\.\d+)?)")
    issued_units = first_match_number(text, r"已發行受益權單位總數-台幣交易\s*([0-9,]+)")
    return {
        "data_date": latest_date,
        "fund_net_asset_value_twd": net_asset,
        "nav": nav,
        "issued_units": int(issued_units) if issued_units is not None else None,
        "issued_lots": round(issued_units / 1000) if issued_units else None,
        "holdings": holdings,
        "top10": holdings[:10],
        "futures": parse_capitalfund_futures_from_text(text),
        "other_assets": parse_capitalfund_other_assets(text),
        "source": "群益投信投資組合",
    }


def fetch_capitalfund_buyback_data():
    html = fetch_text(CAPITALFUND_BUYBACK_URL)
    text = clean_text(html)
    data_date = None
    date_match = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})\s*每基數申購總價金差額", text)
    if not date_match:
        date_match = re.search(r"\((20\d{2}/\d{1,2}/\d{1,2})\)", text)
    if date_match:
        data_date = to_iso_date(date_match.group(1))
    holdings = parse_capitalfund_holdings_from_text(text)
    pcf = {
        "estimated_creation_cash_twd": first_match_number(text, r"每申購基數之預收申購總價金\(元\)\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
        "fund_net_asset_value_twd": first_match_number(text, r"基金淨資產價值\(元\)\s*TWD\s*([0-9,]+(?:\.\d+)?)"),
        "nav": first_match_number(text, r"每受益權單位淨資產價值\(元\)-台幣交易\s*TWD\s*([0-9,]+(?:\.\d+)?)"),
        "issued_units": first_match_number(text, r"已發行受益權單位總數-台幣交易\s*([0-9,]+)"),
        "issued_unit_diff": first_match_number(text, r"與前日已發行單位差異數-台幣交易\s*([-0-9,]+)"),
        "cash_creation_unit_etf_units": first_match_number(text, r"每現金申購單位之受益權單位數\s*([0-9,]+)"),
        "creation_unit_market_value_twd": first_match_number(text, r"每現金申購買回基數約當市值\(元\)\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
        "creation_cash_difference_twd": first_match_number(text, r"每基數申購總價金差額\(元\)\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
        "actual_creation_price_twd": first_match_number(text, r"每基數實際申購總價金\(元\)\s*TWD\s*([-0-9,]+(?:\.\d+)?)"),
    }
    if pcf.get("issued_units") is not None:
        pcf["issued_units"] = int(pcf["issued_units"])
        pcf["issued_lots"] = round(pcf["issued_units"] / 1000)
    return {
        "data_date": data_date,
        "fund_net_asset_value_twd": pcf.get("fund_net_asset_value_twd"),
        "nav": pcf.get("nav"),
        "issued_units": pcf.get("issued_units"),
        "issued_lots": pcf.get("issued_lots"),
        "holdings": holdings,
        "top10": holdings[:10],
        "futures": parse_capitalfund_futures_from_text(text),
        "other_assets": parse_capitalfund_other_assets(text),
        "pcf": pcf,
        "source": "群益投信申購買回清單",
    }


def merge_nav_rows_by_priority(primary_rows, fallback_rows):
    by_date = {}
    for row in fallback_rows or []:
        date_value = row.get("date")
        if not date_value:
            continue
        by_date[date_value] = {**row, "nav_source_rank": 2, "sources": [row.get("source") or "MoneyDJ"]}
    for row in primary_rows or []:
        date_value = row.get("date")
        if not date_value:
            continue
        old = by_date.get(date_value, {})
        merged = {**old, **row, "nav_source_rank": 1}
        merged["sources"] = sorted(set(old.get("sources", [])) | {row.get("source") or "群益投信官網"})
        by_date[date_value] = merged
    return [by_date[date] for date in sorted(by_date)]


def merge_monthly_size_sources(moneydj_rows, capital_data=None, etfortune_data=None):
    """Keep monthly AUM as a true month-end series.

    Capital Fund and TWSE summary pages provide latest snapshots, not month-end
    monthly AUM rows.  They are intentionally NOT merged here.  If MoneyDJ has
    a beneficiary row but AUM is N/A, the row is kept with a pending status so
    the chart can draw the beneficiary line and show the AUM bar as 待補.
    """
    rows_by_month = {row.get("month"): {**row} for row in moneydj_rows or [] if row.get("month")}
    for row in rows_by_month.values():
        has_aum = row.get("aum_100m_twd") is not None or row.get("aum_million_twd") is not None
        has_beneficiary = row.get("beneficiary_count") is not None
        row["beneficiary_source"] = row.get("beneficiary_source") or (row.get("source") if has_beneficiary else None)
        row["monthly_aum_source"] = row.get("monthly_aum_source") or (row.get("source") if has_aum else None)
        if has_aum:
            row["monthly_aum_status"] = "complete"
            row["aum_pending"] = False
        elif has_beneficiary:
            row["monthly_aum_status"] = "pending"
            row["aum_pending"] = True
            row["aum_pending_reason"] = "MoneyDJ 已更新受益人數，但月度 AUM 仍為 N/A，等待月表補齊。"
        else:
            row["monthly_aum_status"] = "missing"
            row["aum_pending"] = True
            row["aum_pending_reason"] = "尚未取得月度 AUM / 受益人數。"
    return [rows_by_month[month] for month in sorted(rows_by_month)]

def choose_holdings_data(capital_portfolio, capital_buyback, moneydj_data):
    primary = capital_portfolio if (capital_portfolio or {}).get("holdings") else None
    if primary is None and (capital_buyback or {}).get("holdings"):
        primary = capital_buyback
    if primary is None:
        primary = moneydj_data or {}
    industries = (moneydj_data or {}).get("industries", [])
    source_details = {
        "holdings_primary": primary.get("source"),
        "portfolio_available": bool((capital_portfolio or {}).get("holdings")),
        "buyback_available": bool((capital_buyback or {}).get("holdings")),
        "moneydj_available": bool((moneydj_data or {}).get("holdings")),
        "industry_source": (moneydj_data or {}).get("source") if industries else None,
    }
    result = {
        **(moneydj_data or {}),
        **primary,
        "holdings": primary.get("holdings", []),
        "top10": primary.get("top10", primary.get("holdings", [])[:10]),
        "industries": industries,
        "industry_date": (moneydj_data or {}).get("industry_date"),
        "source": primary.get("source") or (moneydj_data or {}).get("source") or "unknown",
        "source_details": source_details,
    }
    # Keep buyback PCF even when portfolio holdings are the primary source.
    if (capital_buyback or {}).get("pcf"):
        result["pcf"] = capital_buyback.get("pcf")
        result["buyback"] = capital_buyback
    if capital_portfolio:
        result["portfolio"] = capital_portfolio
    return result

def fetch_moneydj_nav_rows():
    html = fetch_text(MONEYDJ_NAV_URL)
    pattern = re.compile(
        r"<tr>\s*"
        r'<td class="col(?:07|10)">\s*(\d{4}/\d{2}/\d{2})\s*</td>\s*'
        r'<td class="col(?:08|11)">\s*([0-9.]+)\s*</td>\s*'
        r'<td class="col(?:09|12)">\s*([0-9.]+)\s*</td>\s*'
        r'<td class="col09">\s*<span class="(?:negative|positive|zero)?">\s*([-0-9.]+)\s*</span>',
        re.S,
    )
    rows = []
    seen = set()
    for date_value, nav, market_price, discount_pct in pattern.findall(html):
        iso_date = date_value.replace("/", "-")
        if iso_date in seen:
            continue
        seen.add(iso_date)
        rows.append(
            {
                "date": iso_date,
                "market_price": parse_number(market_price),
                "nav": parse_number(nav),
                "premium_discount_pct": parse_number(discount_pct),
                "source": "MoneyDJ",
            }
        )
    return sorted(rows, key=lambda row: row["date"])


def extract_numeric_tokens(text):
    """Return numeric tokens from scraped text, excluding date/month tokens.

    MoneyDJ's ETF size page sometimes concatenates hidden/mobile cells at month
    boundaries, for example: "-4.4N/A 2026/041317373-0.83".  A cell-based
    parser can then miss the month or mistake the merged text for one value.
    Tokenising the whole row is more resilient.
    """
    cleaned = clean_text(str(text)).replace("，", ",")
    # Add a separator when MoneyDJ glues a month and the next numeric cell,
    # e.g. 2026/041317373-0.83 -> 2026/04 1317373-0.83.
    cleaned = re.sub(r"(20\d{2}[/-](?:0[1-9]|1[0-2]))(?=\d)", r"\1 ", cleaned)
    cleaned = re.sub(r"20\d{2}[/-]\d{1,2}(?!\d)(?:[/-]\d{1,2}(?!\d))?", " ", cleaned)
    cleaned = re.sub(r"N\s*/\s*A|NA|--|—", " ", cleaned, flags=re.I)
    tokens = []
    for match in re.finditer(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?", cleaned):
        raw = match.group(0)
        value = parse_number(raw)
        if value is None:
            continue
        tokens.append({"raw": raw, "value": value})
    return tokens


def fetch_moneydj_monthly_size_rows():
    html = fetch_text(MONEYDJ_MONTHLY_SIZE_URL)
    rows_by_month = {}

    # Basic0019 tends to change at month boundaries: a new month can appear in
    # price data before the AUM table has a clean complete row, and MoneyDJ may
    # include hidden mobile cells that merge month / beneficiary / change pct.
    # Parse every row by text tokens instead of fixed column positions.
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        cells = [clean_text(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", block, flags=re.S)]
        row_text = " | ".join(cells) if cells else clean_text(block)
        month_match = re.search(r"(20\d{2})[/-](0?[1-9]|1[0-2])", row_text)
        if not month_match:
            continue

        month_key = f"{int(month_match.group(1)):04d}-{int(month_match.group(2)):02d}"
        tokens = extract_numeric_tokens(row_text)
        if not tokens:
            continue

        values = [item["value"] for item in tokens]

        # Beneficiary count: usually 6~7 digits. Avoid using AUM-in-million as
        # beneficiary by preferring integer-like values with a comma pattern or
        # the largest 100k~5m value not followed by a decimal raw token.
        beneficiary_candidates = [
            item for item in tokens
            if 100_000 <= item["value"] <= 5_000_000 and "." not in item["raw"]
        ]
        beneficiaries = None
        if beneficiary_candidates:
            beneficiaries = normalize_beneficiary_count(max(beneficiary_candidates, key=lambda item: item["value"])["value"])

        # AUM can be either NT$ million (e.g. 363300) or already in 100m TWD
        # (e.g. 3633).  Prefer explicit large values first, then a 500~20000
        # range value that is not the beneficiary count.
        aum_million = None
        aum_100m = None
        for item in tokens:
            value = item["value"]
            if beneficiaries is not None and abs(value - beneficiaries) < 1e-6:
                continue
            if 50_000 <= value <= 2_000_000:
                aum_million = value
                aum_100m = round(value / 100, 4)
                break
        if aum_million is None:
            for item in tokens:
                value = item["value"]
                if beneficiaries is not None and abs(value - beneficiaries) < 1e-6:
                    continue
                if 500 <= value <= 20_000:
                    aum_100m = value
                    aum_million = round(value * 100, 4)
                    break

        # Change pct is the last small signed/decimal number that is not 0/1 and
        # not the month value.  This intentionally ignores AUM monthly change if
        # a later beneficiary change is available.
        pct_candidates = [
            item["value"] for item in tokens
            if -100 <= item["value"] <= 100 and item["value"] not in {0, 1}
        ]
        beneficiary_change_pct = pct_candidates[-1] if pct_candidates else None

        # Skip rows that contain only an incomplete new-month stub.  This is the
        # key month-boundary guard: the dashboard should keep showing the latest
        # valid AUM row instead of creating a 0-AUM current month.
        if aum_100m is None and beneficiaries is None and beneficiary_change_pct is None:
            continue

        existing = rows_by_month.get(month_key, {})
        candidate = {
            "month": month_key,
            "beneficiary_count": int(beneficiaries) if beneficiaries is not None else existing.get("beneficiary_count"),
            "beneficiary_change_pct": beneficiary_change_pct if beneficiary_change_pct is not None else existing.get("beneficiary_change_pct"),
            "aum_million_twd": aum_million if aum_million is not None else existing.get("aum_million_twd"),
            "aum_100m_twd": aum_100m if aum_100m is not None else existing.get("aum_100m_twd"),
            "source": "MoneyDJ",
            "beneficiary_source": "MoneyDJ" if beneficiaries is not None else existing.get("beneficiary_source"),
            "monthly_aum_source": "MoneyDJ" if aum_100m is not None else existing.get("monthly_aum_source"),
        }
        # Prefer the candidate with a valid AUM; otherwise keep the richer row.
        if not existing or candidate.get("aum_100m_twd") or len([v for v in candidate.values() if v is not None]) > len([v for v in existing.values() if v is not None]):
            rows_by_month[month_key] = candidate

    # Fallback: parse the full visible text.  This catches month-boundary rows
    # such as "2026/05 1,259,337 -4.41 N/A" even when hidden/mobile HTML cells
    # break the <tr>/<td> parser.
    plain_text = clean_text(html)
    plain_text = re.sub(r"(20\d{2}[/-](?:0?[1-9]|1[0-2]))(?=[0-9,])", r"\1 ", plain_text)
    month_row_pattern = re.compile(
        r"(20\d{2})[/-](0?[1-9]|1[0-2])\s+([0-9,]{5,})\s*([-+]?\d+(?:\.\d+)?)\s*(N/A|NA|--|[0-9,]+(?:\.\d+)?)",
        flags=re.I,
    )
    for year, month, beneficiaries_text, change_text, aum_text in month_row_pattern.findall(plain_text):
        month_key = f"{int(year):04d}-{int(month):02d}"
        beneficiaries = normalize_beneficiary_count(parse_number(beneficiaries_text))
        beneficiary_change_pct = parse_number(change_text)
        aum_value = None if str(aum_text).upper() in {"N/A", "NA", "--"} else parse_number(aum_text)
        aum_million = None
        aum_100m = None
        if aum_value is not None:
            if aum_value >= 50_000:
                aum_million = aum_value
                aum_100m = round(aum_value / 100, 4)
            else:
                aum_100m = aum_value
                aum_million = round(aum_value * 100, 4)
        existing = rows_by_month.get(month_key, {})
        candidate = {
            "month": month_key,
            "beneficiary_count": int(beneficiaries) if beneficiaries is not None else existing.get("beneficiary_count"),
            "beneficiary_change_pct": beneficiary_change_pct if beneficiary_change_pct is not None else existing.get("beneficiary_change_pct"),
            "aum_million_twd": aum_million if aum_million is not None else existing.get("aum_million_twd"),
            "aum_100m_twd": aum_100m if aum_100m is not None else existing.get("aum_100m_twd"),
            "source": "MoneyDJ",
            "beneficiary_source": "MoneyDJ" if beneficiaries is not None else existing.get("beneficiary_source"),
            "monthly_aum_source": "MoneyDJ" if aum_100m is not None else existing.get("monthly_aum_source"),
        }
        if not existing:
            rows_by_month[month_key] = candidate
        else:
            merged = {**existing}
            # The row-based parser is more reliable for AUM.  The plain-text
            # fallback should only fill blanks, not overwrite a complete row
            # with hidden/mobile fragments such as 294 / 934.
            for key, value in candidate.items():
                if key in {"month", "source", "beneficiary_source", "monthly_aum_source"}:
                    merged[key] = value or merged.get(key)
                elif value is not None and merged.get(key) is None:
                    merged[key] = value
            rows_by_month[month_key] = merged

    return recompute_beneficiary_change_pct([rows_by_month[month] for month in sorted(rows_by_month)])


def extract_table_section(html, table_id):
    pattern = re.compile(
        rf'<table[^>]+id="{re.escape(table_id)}"[^>]*>.*?<tbody>(.*?)</tbody>',
        re.S,
    )
    match = pattern.search(html)
    return match.group(1) if match else ""


def extract_section_date(html, date_id):
    pattern = re.compile(rf'id="{re.escape(date_id)}"[^>]*>\s*資料日期：\s*([0-9/]+)', re.S)
    match = pattern.search(html)
    return match.group(1).replace("/", "-") if match else None


def fetch_moneydj_holdings_data():
    html = fetch_text(MONEYDJ_HOLDINGS_URL)
    holdings_date = extract_section_date(html, "ctl00_ctl00_MainContent_MainContent_sdate3")
    industry_date = extract_section_date(html, "ctl00_ctl00_MainContent_MainContent_sdate2")

    holdings_body = extract_table_section(html, "ctl00_ctl00_MainContent_MainContent_stable3")
    holding_rows = []
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", holdings_body, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", block, flags=re.S)
        if len(cells) < 3:
            continue
        name_text = clean_text(cells[0])
        match = re.match(r"(.+?)\((\d{4})\.TW\)", name_text)
        holding_rows.append(
            {
                "rank": len(holding_rows) + 1,
                "name": match.group(1) if match else name_text,
                "code": match.group(2) if match else None,
                "weight_pct": parse_number(cells[1]),
                "shares": parse_number(cells[2]),
            }
        )

    industry_body = extract_table_section(html, "ctl00_ctl00_MainContent_MainContent_stable2")
    industry_rows = []
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", industry_body, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", block, flags=re.S)
        if len(cells) < 4:
            continue
        industry_rows.append(
            {
                "industry": clean_text(cells[1]),
                "amount_10k_twd": parse_number(cells[2]),
                "weight_pct": parse_number(cells[3]),
            }
        )

    return {
        "data_date": holdings_date,
        "industry_date": industry_date,
        "holdings": holding_rows,
        "top10": holding_rows[:10],
        "industries": industry_rows,
        "source": "MoneyDJ",
    }


def fetch_yahoo_history_rows():
    period1 = int(datetime(2022, 1, 1).timestamp())
    period2 = int(time.time()) + 86400
    query = urllib.parse.urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    data = json.loads(fetch_text(f"{YAHOO_CHART_URL}?{query}"))
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        return []
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0]
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    adjusted_closes = adjusted.get("adjclose") or []

    rows = []
    for index, timestamp in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue
        volume = volumes[index] if index < len(volumes) else None
        adjusted_close = adjusted_closes[index] if index < len(adjusted_closes) else None
        rows.append(
            {
                "date": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d"),
                "market_price": round(float(close), 4),
                "adjusted_close": round(float(adjusted_close), 4)
                if adjusted_close is not None
                else None,
                "volume_shares": int(volume) if volume is not None else None,
                "volume_lots": round(int(volume) / 1000) if volume is not None else None,
                "source": "Yahoo",
            }
        )
    return sorted(rows, key=lambda row: row["date"])



def has_valid_number(value, allow_zero=True):
    if value is None or value == "":
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    if not allow_zero and numeric <= 0:
        return False
    return True


def keep_valid_value(new_value, old_value, allow_zero=True):
    if not has_valid_number(new_value, allow_zero=allow_zero):
        return old_value
    return new_value


def load_daily_history_map():
    if not DAILY_HISTORY_PATH.exists():
        return {}
    try:
        raw = json.loads(DAILY_HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = raw.values() if isinstance(raw, dict) else raw
    result = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date_value = str(row.get("date") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
            continue
        normalized = {**row, "date": date_value}
        # Backward-compatible aliases used by the existing HTML dashboard.
        if normalized.get("official_nav") is None and normalized.get("nav") is not None:
            normalized["official_nav"] = normalized.get("nav")
        if normalized.get("nav") is None and normalized.get("official_nav") is not None:
            normalized["nav"] = normalized.get("official_nav")
        if normalized.get("market_close") is None and normalized.get("market_price") is not None:
            normalized["market_close"] = normalized.get("market_price")
        if normalized.get("market_price") is None and normalized.get("market_close") is not None:
            normalized["market_price"] = normalized.get("market_close")
        result[date_value] = normalized
    return result


def recalc_daily_premium(row):
    market_price = row.get("market_price") if row.get("market_price") is not None else row.get("market_close")
    nav = row.get("nav") if row.get("nav") is not None else row.get("official_nav")
    if has_valid_number(market_price, allow_zero=False):
        row["market_price"] = round(float(market_price), 4)
        row["market_close"] = round(float(market_price), 4)
    if has_valid_number(nav, allow_zero=False):
        row["nav"] = round(float(nav), 4)
        row["official_nav"] = round(float(nav), 4)
        row["is_estimated_nav"] = bool(row.get("is_estimated_nav", False))
    if has_valid_number(row.get("market_price"), allow_zero=False) and has_valid_number(row.get("nav"), allow_zero=False):
        discount_amount = round(float(row["market_price"]) - float(row["nav"]), 4)
        row["premium_discount_amount"] = discount_amount
        row["premium_discount_pct"] = round(discount_amount / float(row["nav"]) * 100, 4)
        row["premium_source"] = "calculated"
    return row


def save_daily_history_map(history_map):
    clean = {}
    for date_value in sorted(history_map):
        row = recalc_daily_premium({**history_map[date_value], "date": date_value})
        clean[date_value] = row
    DAILY_HISTORY_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def update_daily_history(nav_rows, yahoo_rows, fetched_at):
    """Merge NAV and price rows into a long-lived daily history file.

    NAV history should never be lost just because a site only exposes recent
    rows.  Existing valid values are preserved when a source returns empty/N/A.
    """
    history = load_daily_history_map()

    for row in yahoo_rows or []:
        date_value = row.get("date")
        if not date_value:
            continue
        old = history.get(date_value, {"date": date_value})
        market_price = keep_valid_value(row.get("market_price"), old.get("market_price"), allow_zero=False)
        merged = {
            **old,
            "date": date_value,
            "market_price": market_price,
            "market_close": market_price,
            "adjusted_close": keep_valid_value(row.get("adjusted_close"), old.get("adjusted_close"), allow_zero=False),
            "volume_shares": keep_valid_value(row.get("volume_shares"), old.get("volume_shares"), allow_zero=False),
            "volume_lots": keep_valid_value(row.get("volume_lots"), old.get("volume_lots"), allow_zero=False),
            "price_source": row.get("source") or old.get("price_source") or "Yahoo",
            "updated_at": fetched_at,
        }
        history[date_value] = recalc_daily_premium(merged)

    # TWSE volume/close is a useful patch for dates covered by freshly fetched NAV.
    months = sorted({iso_to_twse_month(row["date"]) for row in nav_rows or [] if row.get("date")})
    volume_rows = {}
    for month in months:
        try:
            volume_rows.update(fetch_twse_month_volume(month))
        except Exception:
            pass

    for row in nav_rows or []:
        date_value = row.get("date")
        if not date_value:
            continue
        old = history.get(date_value, {"date": date_value})
        volume = volume_rows.get(date_value, {})
        market_price = keep_valid_value(
            row.get("market_price") or volume.get("twse_close"),
            old.get("market_price"),
            allow_zero=False,
        )
        nav = keep_valid_value(row.get("nav"), old.get("nav") or old.get("official_nav"), allow_zero=False)
        merged = {
            **old,
            "date": date_value,
            "market_price": market_price,
            "market_close": market_price,
            "nav": nav,
            "official_nav": nav,
            "nav_source": row.get("nav_source") or row.get("source") or old.get("nav_source") or "MoneyDJ",
            "nav_source_rank": row.get("nav_source_rank") or old.get("nav_source_rank"),
            "nav_sources": row.get("sources") or old.get("nav_sources"),
            "is_estimated_nav": row.get("is_estimated_nav", old.get("is_estimated_nav", False)),
            "capitalfund_market_close": keep_valid_value(row.get("capitalfund_market_close"), old.get("capitalfund_market_close"), allow_zero=False),
            "capitalfund_close_date": row.get("capitalfund_close_date") or old.get("capitalfund_close_date"),
            "capitalfund_premium_discount_amount": keep_valid_value(row.get("capitalfund_premium_discount_amount"), old.get("capitalfund_premium_discount_amount"), allow_zero=True),
            "capitalfund_premium_discount_pct": keep_valid_value(row.get("capitalfund_premium_discount_pct"), old.get("capitalfund_premium_discount_pct"), allow_zero=True),
            "volume_lots": keep_valid_value(volume.get("volume_lots"), old.get("volume_lots"), allow_zero=False),
            "volume_shares": keep_valid_value(volume.get("volume_shares"), old.get("volume_shares"), allow_zero=False),
            "updated_at": fetched_at,
        }
        history[date_value] = recalc_daily_premium(merged)

    saved = save_daily_history_map(history)
    return [saved[date_value] for date_value in sorted(saved)]

def enrich_monthly_size_rows(monthly_size_rows, daily_rows):
    month_end_nav = {}
    for row in daily_rows:
        date_value = row.get("date")
        nav = row.get("nav")
        if not date_value or nav is None:
            continue
        month = date_value[:7]
        current = month_end_nav.get(month)
        if not current or date_value > current["date"]:
            month_end_nav[month] = {"date": date_value, "nav": nav}

    enriched = []
    for row in monthly_size_rows:
        nav_row = month_end_nav.get(row["month"])
        issued_units = None
        if nav_row and row.get("aum_million_twd") is not None and nav_row.get("nav"):
            issued_units = row["aum_million_twd"] * 1_000_000 / nav_row["nav"]
        enriched.append(
            {
                **row,
                "month_end_nav": nav_row.get("nav") if nav_row else None,
                "issued_units_estimated": round(issued_units) if issued_units else None,
                "issued_lots_estimated": round(issued_units / 1000) if issued_units else None,
                "issued_units_is_estimated": issued_units is not None,
            }
        )
    return enriched


def build_monthly_market_rows(daily_rows):
    months = {}
    for row in daily_rows:
        date_value = row.get("date")
        if not date_value:
            continue
        month = date_value[:7]
        current = months.setdefault(
            month,
            {
                "month": month,
                "price_sum": 0,
                "price_count": 0,
                "nav_sum": 0,
                "nav_count": 0,
                "discount_sum": 0,
                "discount_count": 0,
                "end_date": date_value,
                "end_market_price": None,
                "end_nav": None,
                "end_premium_discount_pct": None,
            },
        )
        market_price = row.get("market_price")
        nav = row.get("nav")
        discount_pct = row.get("premium_discount_pct")
        if market_price is not None:
            current["price_sum"] += market_price
            current["price_count"] += 1
        if nav is not None:
            current["nav_sum"] += nav
            current["nav_count"] += 1
        if discount_pct is not None:
            current["discount_sum"] += discount_pct
            current["discount_count"] += 1
        if date_value >= current["end_date"]:
            current["end_date"] = date_value
            current["end_market_price"] = market_price
            current["end_nav"] = nav
            current["end_premium_discount_pct"] = discount_pct

    rows = []
    for item in months.values():
        rows.append(
            {
                "month": item["month"],
                "avg_market_price": round(item["price_sum"] / item["price_count"], 4)
                if item["price_count"]
                else None,
                "end_market_price": item["end_market_price"],
                "avg_nav": round(item["nav_sum"] / item["nav_count"], 4)
                if item["nav_count"]
                else None,
                "end_nav": item["end_nav"],
                "avg_premium_discount_pct": round(item["discount_sum"] / item["discount_count"], 4)
                if item["discount_count"]
                else None,
                "end_premium_discount_pct": item["end_premium_discount_pct"],
                "month_end_date": item["end_date"],
            }
        )
    return sorted(rows, key=lambda row: row["month"])


def update_monthly_history(daily_rows, monthly_size_rows, fetched_at):
    history_path = DATA_DIR / "monthly_history.json"
    existing_rows = []
    if history_path.exists():
        try:
            existing_rows = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            existing_rows = []

    by_month = {
        row.get("month"): row
        for row in existing_rows
        if isinstance(row, dict) and row.get("month")
    }
    market_by_month = {row["month"]: row for row in build_monthly_market_rows(daily_rows)}
    size_by_month = {row["month"]: row for row in monthly_size_rows}

    for month in sorted(set(market_by_month) | set(size_by_month)):
        old = by_month.get(month, {})
        market = market_by_month.get(month, {})
        size = size_by_month.get(month, {})
        def keep_valid(new_value, old_value, allow_zero=False):
            if new_value is None or new_value == "":
                return old_value
            try:
                numeric = float(new_value)
            except (TypeError, ValueError):
                return new_value
            if not allow_zero and numeric <= 0:
                return old_value
            return new_value

        merged = {
            **old,
            "month": month,
            **market,
            # At the start of a new month MoneyDJ can expose an incomplete
            # current-month row. Never overwrite a previously valid AUM /
            # beneficiary value with None or 0.
            "aum_100m_twd": keep_valid(size.get("aum_100m_twd"), old.get("aum_100m_twd")),
            "aum_million_twd": keep_valid(size.get("aum_million_twd"), old.get("aum_million_twd")),
            "beneficiary_count": keep_valid(size.get("beneficiary_count"), old.get("beneficiary_count")),
            "beneficiary_change_pct": keep_valid(
                size.get("beneficiary_change_pct"), old.get("beneficiary_change_pct"), allow_zero=True
            ),
            "monthly_aum_status": size.get("monthly_aum_status") or old.get("monthly_aum_status") or ("complete" if (size.get("aum_100m_twd") or old.get("aum_100m_twd")) else ("pending" if (size.get("beneficiary_count") or old.get("beneficiary_count")) else "missing")),
            "monthly_aum_source": size.get("monthly_aum_source") or old.get("monthly_aum_source"),
            "beneficiary_source": size.get("beneficiary_source") or old.get("beneficiary_source"),
            "aum_pending": size.get("aum_pending") if "aum_pending" in size else old.get("aum_pending"),
            "aum_pending_reason": size.get("aum_pending_reason") or old.get("aum_pending_reason"),
            "sources": sorted(
                set(old.get("sources", []))
                | ({"Yahoo"} if market else set())
                | ({size.get("source") or "MoneyDJ"} if size else set())
            ),
            "source": size.get("source") or old.get("source"),
            "fund_net_asset_value_twd": keep_valid(size.get("fund_net_asset_value_twd"), old.get("fund_net_asset_value_twd")),
            "issued_units": keep_valid(size.get("issued_units"), old.get("issued_units")),
            "issued_lots": keep_valid(size.get("issued_lots"), old.get("issued_lots")),
            "updated_at": fetched_at,
        }
        by_month[month] = merged

    rows = [by_month[month] for month in sorted(by_month)]
    history_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def update_holdings_history(holdings_data, fetched_at):
    history_path = DATA_DIR / "holdings_history.json"
    existing_rows = []
    if history_path.exists():
        try:
            existing_rows = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            existing_rows = []

    by_date = {
        row.get("data_date"): row
        for row in existing_rows
        if isinstance(row, dict) and row.get("data_date")
    }
    data_date = holdings_data.get("data_date") or fetched_at[:10]
    by_date[data_date] = {
        "data_date": data_date,
        "industry_date": holdings_data.get("industry_date"),
        "top10": holdings_data.get("top10", []),
        "holdings": holdings_data.get("holdings", []),
        "industries": holdings_data.get("industries", []),
        "futures": holdings_data.get("futures", []),
        "other_assets": holdings_data.get("other_assets", {}),
        "pcf": holdings_data.get("pcf", {}),
        "portfolio": holdings_data.get("portfolio", {}),
        "buyback": holdings_data.get("buyback", {}),
        "fund_net_asset_value_twd": holdings_data.get("fund_net_asset_value_twd"),
        "nav": holdings_data.get("nav"),
        "issued_units": holdings_data.get("issued_units"),
        "issued_lots": holdings_data.get("issued_lots"),
        "source": holdings_data.get("source", "MoneyDJ"),
        "source_details": holdings_data.get("source_details", {}),
        "updated_at": fetched_at,
    }
    rows = [by_date[date] for date in sorted(by_date)]
    history_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def fetch_twse_month_volume(month):
    query = urllib.parse.urlencode(
        {"date": month, "stockNo": "00919", "response": "json"}
    )
    data = json.loads(fetch_text(f"{TWSE_STOCK_DAY_URL}?{query}"))
    rows = {}
    if data.get("stat") != "OK":
        return rows
    for item in data.get("data", []):
        iso_date = roc_date_to_iso(item[0])
        rows[iso_date] = {
            "date": iso_date,
            "volume_shares": int(item[1].replace(",", "")),
            "volume_lots": round(int(item[1].replace(",", "")) / 1000),
            "twse_close": parse_number(item[6]),
        }
    return rows


def merge_daily_rows(nav_rows, yahoo_rows=None):
    yahoo_rows = yahoo_rows or []
    months = sorted({iso_to_twse_month(row["date"]) for row in nav_rows})
    volume_rows = {}
    for month in months:
        try:
            volume_rows.update(fetch_twse_month_volume(month))
        except Exception:
            pass

    merged_by_date = {row["date"]: {**row} for row in yahoo_rows}
    for row in nav_rows:
        volume = volume_rows.get(row["date"], {})
        market_price = row.get("market_price") or volume.get("twse_close")
        nav = row.get("nav")
        discount_amount = (
            round(market_price - nav, 4)
            if market_price is not None and nav is not None
            else None
        )
        discount_pct = row.get("premium_discount_pct")
        if discount_pct is None and discount_amount is not None and nav:
            discount_pct = round(discount_amount / nav * 100, 2)
        existing = merged_by_date.get(row["date"], {})
        merged_by_date[row["date"]] = (
            {
                **existing,
                **row,
                "market_price": market_price,
                "premium_discount_amount": discount_amount,
                "premium_discount_pct": discount_pct,
                "volume_lots": volume.get("volume_lots") or existing.get("volume_lots"),
                "volume_shares": volume.get("volume_shares") or existing.get("volume_shares"),
                "source": "Yahoo + MoneyDJ + TWSE",
            }
        )
    return sorted(merged_by_date.values(), key=lambda row: row["date"])



def load_existing_dividend_rows():
    dashboard_path = DATA_DIR / "dashboard_data.json"
    if not dashboard_path.exists():
        return []
    try:
        data = json.loads(dashboard_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("dividends") or []
    return [normalize_dividend_row(row, source_hint=row.get("source") or "既有資料") for row in rows if isinstance(row, dict)]


def dividend_component_status(row):
    component_keys = ["dividend_income_pct", "interest_income_pct", "equalization_pct", "capital_gain_pct", "other_income_pct"]
    if row.get("composition_status") == "complete":
        return "complete"
    if any(row.get(key) is not None for key in component_keys):
        return "complete"
    return "pending"


def normalize_dividend_row(row, source_hint=None):
    result = dict(row or {})
    result["ex_date"] = normalize_date_text(result.get("ex_date") or result.get("除息日") or "") or result.get("ex_date")
    result["record_date"] = normalize_date_text(result.get("record_date") or result.get("登記日") or "") or result.get("record_date")
    result["pay_date"] = normalize_date_text(result.get("pay_date") or result.get("發放日") or "") or result.get("pay_date")
    result["base_date"] = normalize_date_text(result.get("base_date") or result.get("配息基準日") or result.get("評價日") or "") or result.get("base_date")
    if result.get("dividend_per_share") is None:
        result["dividend_per_share"] = parse_number(result.get("per_share") or result.get("每單位分配金額") or "")
    for key in ["dividend_income_pct", "interest_income_pct", "equalization_pct", "capital_gain_pct", "other_income_pct"]:
        if key in result and result.get(key) is not None:
            result[key] = parse_number(result.get(key))
    source = source_hint or result.get("source") or "未標示來源"
    result["source"] = result.get("source") or source
    result["event_source"] = result.get("event_source") or source
    result["composition_source"] = result.get("composition_source") or (source if dividend_component_status(result) == "complete" else None)
    result["event_status"] = result.get("event_status") or ("complete" if result.get("ex_date") and result.get("dividend_per_share") is not None else "pending")
    result["composition_status"] = dividend_component_status(result)
    result["composition_pending"] = result["composition_status"] != "complete"
    if result.get("estimated_54c_per_share") is None:
        if result.get("dividend_per_share") is not None and result.get("dividend_income_pct") is not None:
            result["estimated_54c_per_share"] = round(float(result["dividend_per_share"]) * float(result["dividend_income_pct"]) / 100, 6)
        else:
            result["estimated_54c_per_share"] = None
    if not result.get("status_note"):
        if result["composition_status"] == "complete":
            result["status_note"] = f"配息事件與組成資料已完成；組成來源：{result.get('composition_source') or source}。"
        else:
            result["status_note"] = f"已取得配息事件；54C / 收益平準金 / 資本利得組成待 TWSE 或官方公告補齊。事件來源：{result.get('event_source') or source}。"
    return result


def parse_moneydj_dividend_rows():
    """MoneyDJ usually exposes the newest dividend event earlier.

    Use it for ex-date, pay-date and per-unit distribution only.  It does not
    provide 54C / equalization / capital-gain composition, so rows are marked
    composition_status=pending and later completed by TWSE or official data.
    """
    html = fetch_text(MONEYDJ_DIVIDEND_URL)
    rows = []
    for block in re.findall(r"<tr[^>]*>.*?</tr>", html, flags=re.S | re.I):
        cells = [clean_text(cell).replace("\xa0", " ") for cell in re.findall(r"<td[^>]*>(.*?)</td>", block, flags=re.S | re.I)]
        row_text = " ".join(cell for cell in cells if cell) if cells else clean_text(block).replace("\xa0", " ")
        if not re.search(r"20\d{2}/\d{1,2}/\d{1,2}", row_text) or "台幣" not in row_text:
            continue
        dates = re.findall(r"20\d{2}/\d{1,2}/\d{1,2}", row_text)
        if len(dates) < 2:
            continue
        amount = None
        distribution_yield_pct = None
        if cells and "台幣" in cells:
            currency_index = cells.index("台幣")
            numeric_after_currency = [parse_number(cell) for cell in cells[currency_index + 1:]]
            numeric_after_currency = [value for value in numeric_after_currency if value is not None]
            if numeric_after_currency:
                amount = numeric_after_currency[0]
                if len(numeric_after_currency) >= 2:
                    distribution_yield_pct = numeric_after_currency[1]
        if amount is None:
            after_currency = row_text.split("台幣", 1)[1]
            numeric_after_currency = re.findall(r"[0-9]+(?:\.[0-9]+)?", after_currency)
            amount = parse_number(numeric_after_currency[0]) if numeric_after_currency else None
            distribution_yield_pct = parse_number(numeric_after_currency[1]) if len(numeric_after_currency) >= 2 else None
        if amount is None:
            continue
        row = normalize_dividend_row(
            {
                "base_date": normalize_date_text(dates[0]),
                "ex_date": normalize_date_text(dates[1]),
                "record_date": normalize_date_text(dates[2]) if len(dates) >= 4 else None,
                "pay_date": normalize_date_text(dates[-1]) if len(dates) >= 3 else None,
                "dividend_per_share": amount,
                "distribution_yield_pct": distribution_yield_pct,
                "event_source": "MoneyDJ 配息",
                "source": "MoneyDJ 配息",
                "composition_source": None,
                "composition_status": "pending",
                "is_estimated": True,
            },
            source_hint="MoneyDJ 配息",
        )
        rows.append(row)
    return sorted_dedup_dividend_rows(rows)


def parse_capitalfund_dividend_rows():
    """Parse Capital Fund official history page.

    The public page often renders only the latest dividend in static HTML; this
    is still useful as the official event source when available.  Composition is
    not taken from this page.
    """
    html = fetch_text(CAPITALFUND_INTEREST_URL)
    text = clean_text(html)
    pattern = re.compile(
        r"評價日\s*(20\d{2}/\d{1,2}/\d{1,2}).*?"
        r"參與配息\s*最後申購日\s*(20\d{2}/\d{1,2}/\d{1,2}).*?"
        r"除息日\s*(20\d{2}/\d{1,2}/\d{1,2}).*?"
        r"發放日\s*(20\d{2}/\d{1,2}/\d{1,2}).*?"
        r"每單位分配金額\(元\)\s*([0-9.]+)",
        flags=re.S,
    )
    rows = []
    for match in pattern.finditer(text):
        base_date, last_buy_date, ex_date, pay_date, amount = match.groups()
        rows.append(
            normalize_dividend_row(
                {
                    "valuation_date": normalize_date_text(base_date),
                    "last_buy_date": normalize_date_text(last_buy_date),
                    "base_date": normalize_date_text(base_date),
                    "ex_date": normalize_date_text(ex_date),
                    "pay_date": normalize_date_text(pay_date),
                    "dividend_per_share": parse_number(amount),
                    "event_source": "群益投信歷史配息",
                    "source": "群益投信歷史配息",
                    "composition_source": None,
                    "composition_status": "pending",
                    "is_estimated": False,
                },
                source_hint="群益投信歷史配息",
            )
        )
    return sorted_dedup_dividend_rows(rows)


def parse_pct_from_chunk(chunk, labels):
    for label in labels:
        match = re.search(label + r"\s*[:：]?\s*([0-9.]+)\s*%", chunk)
        if match:
            return parse_number(match.group(1))
    return None


def parse_twse_dividend_rows():
    """Parse TWSE ETF e-Fortune dividend list and composition detail.

    TWSE is treated as the primary source for 54C / income composition.  Rows
    without a cash-dividend amount are ignored as events and only used when they
    actually contain composition data.
    """
    html = fetch_text(current_twse_dividend_url())
    text = clean_text(html)
    # Remove excessive whitespace introduced by modal text but keep row order.
    row_pattern = re.compile(r"(1\d{2})\s+00919\s+群益台灣精選高息\s+(.*?)(?=\s+1\d{2}\s+\d{4,6}\s|\Z)", flags=re.S)
    rows = []
    for match in row_pattern.finditer(text):
        chunk = clean_text(match.group(2))
        date_matches = re.findall(r"(\d{3})年(\d{1,2})月(\d{1,2})日", chunk)
        if len(date_matches) < 3:
            continue
        ex_date = roc_ymd_to_iso(*date_matches[0])
        record_date = roc_ymd_to_iso(*date_matches[1])
        pay_date = roc_ymd_to_iso(*date_matches[2])
        amount_match = re.search(r"\d{3}年\d{1,2}月\d{1,2}日\s+([0-9]+(?:\.\d+)?)\s+詳細資料", chunk)
        dividend_per_share = parse_number(amount_match.group(1)) if amount_match else None
        dividend_income_pct = parse_pct_from_chunk(chunk, [r"股利所得占比"])
        interest_income_pct = parse_pct_from_chunk(chunk, [r"利息所得占比"])
        equalization_pct = parse_pct_from_chunk(chunk, [r"收益平準金占比"])
        capital_gain_pct = parse_pct_from_chunk(chunk, [r"已實現資本利得占比"])
        other_income_pct = parse_pct_from_chunk(chunk, [r"其他所得占比"])
        has_components = any(v is not None for v in [dividend_income_pct, interest_income_pct, equalization_pct, capital_gain_pct, other_income_pct])
        if dividend_per_share is None and not has_components:
            continue
        row = {
            "ex_date": ex_date,
            "record_date": record_date,
            "pay_date": pay_date,
            "dividend_per_share": dividend_per_share,
            "dividend_income_pct": dividend_income_pct,
            "interest_income_pct": interest_income_pct,
            "equalization_pct": equalization_pct,
            "capital_gain_pct": capital_gain_pct,
            "other_income_pct": other_income_pct,
            "event_source": "TWSE ETF e添富",
            "composition_source": "TWSE ETF e添富" if has_components else None,
            "source": "TWSE ETF e添富",
            "composition_status": "complete" if has_components else "pending",
            "is_estimated": True,
        }
        rows.append(normalize_dividend_row(row, source_hint="TWSE ETF e添富"))
    return sorted_dedup_dividend_rows(rows)


def sorted_dedup_dividend_rows(rows):
    by_key = {}
    for row in rows:
        row = normalize_dividend_row(row, source_hint=row.get("source"))
        key = row.get("ex_date")
        if not key:
            continue
        by_key[key] = merge_two_dividend_rows(by_key.get(key, {}), row)
    return sorted(by_key.values(), key=lambda item: item.get("ex_date") or "")


def dividend_event_priority(source):
    source = source or ""
    if "群益" in source:
        return 1
    if "TWSE" in source or "e添富" in source:
        return 2
    if "MoneyDJ" in source:
        return 3
    return 9


def merge_two_dividend_rows(existing, candidate):
    existing = normalize_dividend_row(existing, source_hint=existing.get("source") or "既有資料") if existing else {}
    candidate = normalize_dividend_row(candidate, source_hint=candidate.get("source") or "未標示來源")
    if not existing:
        return candidate
    merged = {**existing}

    # Event fields: prefer official Capital Fund, then TWSE, then MoneyDJ.  But
    # always fill missing values from any source so a fast MoneyDJ row can show
    # as pending before official composition arrives.
    candidate_event_source = candidate.get("event_source") or candidate.get("source")
    existing_event_source = merged.get("event_source") or merged.get("source")
    candidate_better_event = dividend_event_priority(candidate_event_source) < dividend_event_priority(existing_event_source)
    for key in ["base_date", "valuation_date", "last_buy_date", "ex_date", "record_date", "pay_date", "dividend_per_share", "distribution_yield_pct"]:
        if candidate.get(key) is not None and (merged.get(key) is None or candidate_better_event):
            merged[key] = candidate.get(key)
    if candidate_better_event or not merged.get("event_source"):
        merged["event_source"] = candidate_event_source

    # Composition fields: only TWSE / complete rows should overwrite existing
    # composition.  Pending event rows must not erase completed 54C history.
    candidate_complete = candidate.get("composition_status") == "complete"
    existing_complete = merged.get("composition_status") == "complete" or dividend_component_status(merged) == "complete"
    if candidate_complete or not existing_complete:
        for key in ["dividend_income_pct", "interest_income_pct", "equalization_pct", "capital_gain_pct", "other_income_pct", "estimated_54c_per_share"]:
            if candidate.get(key) is not None:
                merged[key] = candidate.get(key)
        if candidate_complete:
            merged["composition_status"] = "complete"
            merged["composition_source"] = candidate.get("composition_source") or candidate.get("source")
    if merged.get("composition_status") != "complete":
        merged["composition_status"] = "pending"
        merged["composition_pending"] = True
        merged["estimated_54c_per_share"] = None
    else:
        merged["composition_pending"] = False
        if merged.get("dividend_per_share") is not None and merged.get("dividend_income_pct") is not None:
            merged["estimated_54c_per_share"] = round(float(merged["dividend_per_share"]) * float(merged["dividend_income_pct"]) / 100, 6)
    merged["event_status"] = "complete" if merged.get("ex_date") and merged.get("dividend_per_share") is not None else "pending"
    merged["source"] = build_dividend_source_label(merged)
    if merged.get("composition_status") == "complete":
        merged["status_note"] = f"配息事件來源：{merged.get('event_source') or '--'}；54C 組成來源：{merged.get('composition_source') or '--'}。"
    else:
        merged["status_note"] = f"已取得配息事件，54C / 收益平準金 / 資本利得待 TWSE 或官方公告補齊。事件來源：{merged.get('event_source') or '--'}。"
    return merged


def build_dividend_source_label(row):
    event_source = row.get("event_source") or row.get("source") or "未標示來源"
    composition_source = row.get("composition_source")
    if row.get("composition_status") == "complete" and composition_source:
        return f"{event_source} + {composition_source}" if event_source != composition_source else event_source
    return event_source


def merge_dividend_sources(*source_lists):
    by_ex_date = {}
    for source_rows in source_lists:
        for row in source_rows or []:
            normalized = normalize_dividend_row(row, source_hint=row.get("source") if isinstance(row, dict) else None)
            ex_date = normalized.get("ex_date")
            if not ex_date:
                continue
            by_ex_date[ex_date] = merge_two_dividend_rows(by_ex_date.get(ex_date, {}), normalized)
    return sorted(by_ex_date.values(), key=lambda row: row.get("ex_date") or "")


def build_dividend_fetch_status(rows, fetched_counts):
    latest = rows[-1] if rows else {}
    return {
        "latest_ex_date": latest.get("ex_date"),
        "latest_per_share": latest.get("dividend_per_share"),
        "latest_event_source": latest.get("event_source"),
        "latest_composition_source": latest.get("composition_source"),
        "latest_composition_status": latest.get("composition_status") or "pending",
        "source_counts": fetched_counts,
        "note": latest.get("status_note") or "尚未取得配息事件。",
    }


# Backward-compatible name used by older code paths.
def parse_dividend_rows():
    return parse_twse_dividend_rows()


def calc_signals(latest_daily, latest_dividend):
    signals = []

    discount_pct = latest_daily.get("premium_discount_pct")
    if discount_pct is None:
        signals.append({"name": "折溢價", "level": "unknown", "reason": "折溢價資料未更新"})
    elif abs(discount_pct) <= 1:
        signals.append({"name": "折溢價", "level": "green", "reason": "折溢價落在 +/-1% 內"})
    elif abs(discount_pct) <= 2:
        signals.append({"name": "折溢價", "level": "yellow", "reason": "折溢價超過 +/-1%"})
    else:
        signals.append({"name": "折溢價", "level": "red", "reason": "折溢價超過 +/-2%"})

    volume = latest_daily.get("volume_lots")
    signals.append(
        {
            "name": "成交量",
            "level": "green" if volume else "unknown",
            "reason": "成交量已更新" if volume else "成交量資料未更新",
        }
    )

    signals.append({"name": "規模人氣", "level": "green", "reason": "第一版暫以月資料更新後判斷"})

    if latest_dividend:
        if latest_dividend.get("composition_status") == "complete" and latest_dividend.get("estimated_54c_per_share") is not None:
            signals.append(
                {
                    "name": "配息稅務",
                    "level": "green",
                    "reason": "已抓到最近配息組成，可依股數試算 54C",
                }
            )
        else:
            signals.append(
                {
                    "name": "配息稅務",
                    "level": "yellow",
                    "reason": "已抓到最新配息事件，但 54C / 收益平準金 / 資本利得組成待補。",
                }
            )
    else:
        signals.append({"name": "配息稅務", "level": "unknown", "reason": "尚未抓到配息資料"})

    order = {"red": 3, "yellow": 2, "unknown": 1, "green": 0}
    worst = max(signals, key=lambda item: order[item["level"]])
    total_level = worst["level"] if worst["level"] != "unknown" else "yellow"
    if total_level == "green":
        reason = "折溢價、成交量與配息資料目前正常。"
    else:
        reason = worst["reason"]
    return {"level": total_level, "reason": reason, "items": signals}




def safe_fetch(label, func, default):
    try:
        return func()
    except Exception as exc:
        print(f"[WARN] {label} fetch failed: {exc}")
        return default

def main():
    DATA_DIR.mkdir(exist_ok=True)
    fetched_at = datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None).isoformat(timespec="seconds")

    yahoo_rows = safe_fetch("Yahoo history", fetch_yahoo_history_rows, [])
    capital_nav_rows = safe_fetch("CapitalFund trend", fetch_capitalfund_trend_rows, [])
    moneydj_nav_rows = safe_fetch("MoneyDJ NAV", fetch_moneydj_nav_rows, [])
    nav_rows = merge_nav_rows_by_priority(capital_nav_rows, moneydj_nav_rows)
    daily_rows = update_daily_history(nav_rows, yahoo_rows, fetched_at)

    existing_dividend_rows = load_existing_dividend_rows()
    moneydj_dividend_rows = safe_fetch("MoneyDJ dividend events", parse_moneydj_dividend_rows, [])
    capitalfund_dividend_rows = safe_fetch("CapitalFund dividend events", parse_capitalfund_dividend_rows, [])
    twse_dividend_rows = safe_fetch("TWSE dividend composition", parse_twse_dividend_rows, [])
    dividend_rows = merge_dividend_sources(
        existing_dividend_rows,
        moneydj_dividend_rows,
        capitalfund_dividend_rows,
        twse_dividend_rows,
    )
    dividend_fetch_status = build_dividend_fetch_status(
        dividend_rows,
        {
            "existing": len(existing_dividend_rows),
            "MoneyDJ": len(moneydj_dividend_rows),
            "CapitalFund": len(capitalfund_dividend_rows),
            "TWSE": len(twse_dividend_rows),
        },
    )

    moneydj_monthly_rows = safe_fetch("MoneyDJ monthly size", fetch_moneydj_monthly_size_rows, [])
    capital_portfolio = safe_fetch("CapitalFund portfolio", fetch_capitalfund_portfolio_data, {})
    capital_buyback = safe_fetch("CapitalFund buyback", fetch_capitalfund_buyback_data, {})
    etfortune_info = safe_fetch("TWSE eFortune summary", fetch_etfortune_current_info, {})
    moneydj_holdings = safe_fetch("MoneyDJ holdings", fetch_moneydj_holdings_data, {})
    holdings_data = choose_holdings_data(capital_portfolio, capital_buyback, moneydj_holdings)
    latest_snapshot = build_latest_snapshot(capital_buyback, capital_portfolio, etfortune_info)

    monthly_size_rows = enrich_monthly_size_rows(moneydj_monthly_rows, daily_rows)
    monthly_size_rows = merge_monthly_size_sources(monthly_size_rows)
    monthly_history_rows = update_monthly_history(daily_rows, monthly_size_rows, fetched_at)
    holdings_history_rows = update_holdings_history(holdings_data, fetched_at)

    latest_daily = next(
        (row for row in reversed(daily_rows) if row.get("nav") is not None),
        daily_rows[-1] if daily_rows else {},
    )
    latest_dividend = dividend_rows[-1] if dividend_rows else {}

    payload = {
        "symbol": "00919",
        "name": "群益台灣精選高息",
        "fetched_at": fetched_at,
        "daily": daily_rows,
        "dividends": dividend_rows,
        "monthly_size": monthly_size_rows,
        "monthly_history": monthly_history_rows,
        "holdings": holdings_data,
        "holdings_history": holdings_history_rows,
        "latest_daily": latest_daily,
        "latest_dividend": latest_dividend,
        "dividend_fetch_status": dividend_fetch_status,
        "signals": calc_signals(latest_daily, latest_dividend),
        "data_source_priority": {
            "nav": ["群益投信官網淨值與績效走勢", "MoneyDJ 淨值", "navs.xlsx / daily_history 舊有效值"],
            "price": ["Yahoo / TWSE 日成交", "群益投信官網收盤價", "daily_history 舊有效值"],
            "monthly_aum": ["MoneyDJ 月規模表", "TWSE / 其他月度來源（待擴充）"],
            "latest_aum_snapshot": ["群益投信申購買回清單", "群益投信投資組合", "TWSE e添富最新摘要"],
            "beneficiaries": ["MoneyDJ 月規模表", "TWSE e添富最新摘要（僅最新快照）"],
            "holdings": ["群益投信投資組合", "群益投信申購買回清單", "MoneyDJ 持股與產業"],
            "dividend": ["MoneyDJ 最新配息事件（可先顯示 pending）", "群益歷史配息 / 官方確認", "TWSE 54C / 收益平準金 / 資本利得組成"],
        },
        "source_inventory": build_source_inventory(),
        "latest_snapshot": latest_snapshot,
        "capitalfund": {
            "trend_rows": capital_nav_rows,
            "portfolio": capital_portfolio,
            "buyback": capital_buyback,
        },
        "etfortune": {
            "current_info": etfortune_info,
            "dividend_rows": twse_dividend_rows,
        },
        "moneydj": {
            "dividend_rows": moneydj_dividend_rows,
        },
    }

    (DATA_DIR / "dashboard_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {DATA_DIR / 'dashboard_data.json'}")
    print(f"Daily rows: {len(daily_rows)}")
    print(f"Daily history rows: {len(daily_rows)}")
    print(f"Yahoo history rows: {len(yahoo_rows)}")
    print(f"CapitalFund NAV rows: {len(capital_nav_rows)}")
    print(f"MoneyDJ NAV rows: {len(moneydj_nav_rows)}")
    print(f"Dividend rows: {len(dividend_rows)}")
    print(f"Dividend source rows: existing={len(existing_dividend_rows)}, MoneyDJ={len(moneydj_dividend_rows)}, CapitalFund={len(capitalfund_dividend_rows)}, TWSE={len(twse_dividend_rows)}")
    print(f"Monthly size rows: {len(monthly_size_rows)}")
    print(f"Monthly history rows: {len(monthly_history_rows)}")
    print(f"Holding rows: {len(holdings_data.get('holdings', []))}")
    print(f"Holding source: {holdings_data.get('source')}")
    print(f"Holding history rows: {len(holdings_history_rows)}")


if __name__ == "__main__":
    main()
