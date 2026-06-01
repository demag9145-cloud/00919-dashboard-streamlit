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

MONEYDJ_NAV_URL = "https://www.moneydj.com/etf/x/basic/basic0003.xdjhtm?etfid=00919.tw"
MONEYDJ_MONTHLY_SIZE_URL = "https://www.moneydj.com/ETF/X/Basic/Basic0019.xdjhtm?etfid=00919.TW"
MONEYDJ_HOLDINGS_URL = "https://www.moneydj.com/etf/x/basic/basic0007.xdjhtm?etfid=00919.tw"
ETFORTUNE_DIVIDEND_URL = (
    "https://www.twse.com.tw/zh/ETFortune/dividendList"
    "?stkNo=00919&startDate=2022&endDate=2026"
)
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/00919.TW"


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
            beneficiaries = max(beneficiary_candidates, key=lambda item: item["value"])["value"]

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
        }
        # Prefer the candidate with a valid AUM; otherwise keep the richer row.
        if not existing or candidate.get("aum_100m_twd") or len([v for v in candidate.values() if v is not None]) > len([v for v in existing.values() if v is not None]):
            rows_by_month[month_key] = candidate

    return [rows_by_month[month] for month in sorted(rows_by_month)]


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
            "sources": sorted(
                set(old.get("sources", []))
                | ({"Yahoo"} if market else set())
                | ({"MoneyDJ"} if size else set())
            ),
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
        "source": holdings_data.get("source", "MoneyDJ"),
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


def parse_dividend_rows():
    html = fetch_text(ETFORTUNE_DIVIDEND_URL)
    blocks = re.findall(r"<tr onclick=.*?</tr>", html, flags=re.S)
    rows = []
    for block in blocks:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", block, flags=re.S)
        if len(cells) < 8 or "00919" not in clean_text(cells[0]):
            continue
        percentage_text = clean_text(cells[6])

        def pct(label):
            m = re.search(label + r"\s*([0-9.]+)\s*%", percentage_text)
            return parse_number(m.group(1)) if m else 0.0

        dividend_per_share = parse_number(cells[5])
        # TWSE e添富在新配息尚未完全公告時，可能先出現日期或空白列，
        # 但每股配息欄位仍是空值 / N/A。這種列不能拿來計算 54C，
        # 否則會出現 dividend_per_share * pct 的 TypeError，造成更新失敗。
        if dividend_per_share is None:
            continue
        dividend_income_pct = pct(r"股利所得占比")
        estimated_54c = round(dividend_per_share * dividend_income_pct / 100, 6)
        row = {
            "ex_date": roc_date_to_iso(cells[2]),
            "record_date": roc_date_to_iso(cells[3]),
            "pay_date": roc_date_to_iso(cells[4]),
            "dividend_per_share": dividend_per_share,
            "dividend_income_pct": dividend_income_pct,
            "interest_income_pct": pct(r"利息所得占比"),
            "equalization_pct": pct(r"收益平準金占比"),
            "capital_gain_pct": pct(r"已實現資本利得占比"),
            "other_income_pct": pct(r"其他所得占比"),
            "estimated_54c_per_share": estimated_54c,
            "source": "TWSE ETF e添富",
            "is_estimated": True,
        }
        rows.append(row)
    return sorted(rows, key=lambda row: row["ex_date"])


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
        signals.append(
            {
                "name": "配息稅務",
                "level": "green",
                "reason": "已抓到最近配息組成，可依股數試算 54C",
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


def main():
    DATA_DIR.mkdir(exist_ok=True)
    fetched_at = datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None).isoformat(timespec="seconds")

    yahoo_rows = fetch_yahoo_history_rows()
    daily_rows = merge_daily_rows(fetch_moneydj_nav_rows(), yahoo_rows)
    dividend_rows = parse_dividend_rows()
    monthly_size_rows = enrich_monthly_size_rows(fetch_moneydj_monthly_size_rows(), daily_rows)
    monthly_history_rows = update_monthly_history(daily_rows, monthly_size_rows, fetched_at)
    holdings_data = fetch_moneydj_holdings_data()
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
        "signals": calc_signals(latest_daily, latest_dividend),
    }

    (DATA_DIR / "dashboard_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {DATA_DIR / 'dashboard_data.json'}")
    print(f"Daily rows: {len(daily_rows)}")
    print(f"Yahoo history rows: {len(yahoo_rows)}")
    print(f"Dividend rows: {len(dividend_rows)}")
    print(f"Monthly size rows: {len(monthly_size_rows)}")
    print(f"Monthly history rows: {len(monthly_history_rows)}")
    print(f"Holding rows: {len(holdings_data.get('holdings', []))}")
    print(f"Holding history rows: {len(holdings_history_rows)}")


if __name__ == "__main__":
    main()
