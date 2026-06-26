import re
import ssl
import time
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

import pandas as pd
import requests
import streamlit as st

FILTERED_URL = (
    "https://www.twse.com.tw/zh/ETFortune/dividendList"
    "?stkNo=00919&startDate=2026&endDate=2026"
)
BASE_URL = "https://www.twse.com.tw/zh/ETFortune/dividendList"

# Exact headers currently used by U75f fetch_data.py
U75F_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/json",
}

# Browser-like headers proven by the first independent probe
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def html_to_text(value: str) -> str:
    value = re.sub(
        r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>",
        " ",
        value,
        flags=re.S | re.I,
    )
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def pct(text: str, label: str):
    match = re.search(re.escape(label) + r"\s*[:：]?\s*([0-9.]+)\s*%", text)
    return float(match.group(1)) if match else None


def parse_00919(html: str):
    text = html_to_text(html)
    pattern = re.compile(
        r"(?:^|\s)(?:\d{3}\s+)?00919\s+群益台灣精選高息\s+"
        r"(?P<ex>\d{3}年\d{1,2}月\d{1,2}日)\s+"
        r"(?P<record>\d{3}年\d{1,2}月\d{1,2}日)\s+"
        r"(?P<pay>\d{3}年\d{1,2}月\d{1,2}日)\s+"
        r"(?P<amount>[0-9]+(?:\.[0-9]+)?)\s+詳細資料\s*"
        r"(?P<details>.*?)"
        r"(?=(?:\s+\d{3}\s+[0-9]{4,6}[A-Z]?\s+)|(?:\s+×\s+)|\Z)",
        flags=re.S,
    )
    rows = []
    for match in pattern.finditer(text):
        details = match.group("details")
        rows.append(
            {
                "ex_date_roc": match.group("ex"),
                "record_date_roc": match.group("record"),
                "pay_date_roc": match.group("pay"),
                "dividend_per_share": float(match.group("amount")),
                "dividend_income_pct": pct(details, "股利所得占比"),
                "interest_income_pct": pct(details, "利息所得占比"),
                "equalization_pct": pct(details, "收益平準金占比"),
                "capital_gain_pct": pct(details, "已實現資本利得占比"),
                "other_income_pct": pct(details, "其他所得占比"),
            }
        )
    return rows


def is_complete(rows):
    if not rows:
        return False
    latest = rows[0]
    keys = (
        "dividend_income_pct",
        "interest_income_pct",
        "equalization_pct",
        "capital_gain_pct",
        "other_income_pct",
    )
    return all(latest.get(key) is not None for key in keys)


def urllib_probe(url: str, headers: dict):
    opener = build_opener(
        ProxyHandler({}),
        HTTPSHandler(context=ssl._create_unverified_context()),
    )
    req = Request(url, headers=headers)
    started = time.perf_counter()
    try:
        with opener.open(req, timeout=30) as response:
            body = response.read().decode("utf-8", "ignore")
            elapsed = time.perf_counter() - started
            return {
                "status": getattr(response, "status", None),
                "elapsed_sec": round(elapsed, 3),
                "final_url": response.geturl(),
                "location": response.headers.get("Location"),
                "content_length": len(body.encode("utf-8")),
                "contains_00919": "00919" in body,
                "contains_composition": "已實現資本利得占比" in body,
                "response_server": response.headers.get("Server"),
                "html": body,
            }
    except HTTPError as exc:
        elapsed = time.perf_counter() - started
        return {
            "error": f"HTTPError {exc.code}: {exc.reason}",
            "status": exc.code,
            "elapsed_sec": round(elapsed, 3),
            "final_url": exc.geturl(),
            "location": exc.headers.get("Location") if exc.headers else None,
            "response_headers": dict(exc.headers.items()) if exc.headers else {},
            "html": "",
        }
    except URLError as exc:
        elapsed = time.perf_counter() - started
        return {
            "error": f"URLError: {exc.reason}",
            "elapsed_sec": round(elapsed, 3),
            "html": "",
        }


def requests_probe(url: str, headers: dict):
    started = time.perf_counter()
    try:
        with requests.Session() as session:
            response = session.get(
                url,
                headers=headers,
                timeout=(8, 30),
                allow_redirects=True,
            )
        elapsed = time.perf_counter() - started
        return {
            "status": response.status_code,
            "elapsed_sec": round(elapsed, 3),
            "final_url": response.url,
            "location": response.headers.get("Location"),
            "history": [
                {
                    "status": item.status_code,
                    "url": item.url,
                    "location": item.headers.get("Location"),
                }
                for item in response.history
            ],
            "content_length": len(response.content),
            "contains_00919": "00919" in response.text,
            "contains_composition": "已實現資本利得占比" in response.text,
            "response_server": response.headers.get("Server"),
            "html": response.text,
        }
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_sec": round(elapsed, 3),
            "html": "",
        }


def public_result(result):
    return {key: value for key, value in result.items() if key != "html"}


st.set_page_config(page_title="TWSE 54C Header/Intermittency Probe", layout="wide")
st.title("TWSE 00919 54C 第二階段獨立測試")
st.caption(
    "比較 U75f 原始標頭與完整瀏覽器標頭，並重複測試是否為偶發 307。"
    "不讀寫 Dashboard、Google Sheets 或任何 data/*.json。"
)

attempts = st.slider("每種方式重複次數", min_value=1, max_value=5, value=3)
pause_sec = st.slider("每次請求間隔（秒）", min_value=0.0, max_value=2.0, value=0.5, step=0.5)

if st.button("執行第二階段測試", type="primary", use_container_width=True):
    methods = [
        ("urllib｜U75f 原始標頭｜帶參數", urllib_probe, FILTERED_URL, U75F_HEADERS),
        ("urllib｜完整瀏覽器標頭｜帶參數", urllib_probe, FILTERED_URL, BROWSER_HEADERS),
        ("requests｜U75f 原始標頭｜帶參數", requests_probe, FILTERED_URL, U75F_HEADERS),
        ("requests｜完整瀏覽器標頭｜帶參數", requests_probe, FILTERED_URL, BROWSER_HEADERS),
        ("requests｜完整瀏覽器標頭｜無參數", requests_probe, BASE_URL, BROWSER_HEADERS),
    ]

    summary_rows = []
    raw_results = []

    total = len(methods) * attempts
    progress = st.progress(0)
    current = 0

    for label, func, url, headers in methods:
        for attempt in range(1, attempts + 1):
            result = func(url, headers)
            rows = parse_00919(result.get("html") or "")
            complete = is_complete(rows)
            latest = rows[0] if rows else {}
            summary_rows.append(
                {
                    "method": label,
                    "attempt": attempt,
                    "status": result.get("status"),
                    "elapsed_sec": result.get("elapsed_sec"),
                    "redirect_count": len(result.get("history") or []),
                    "location": result.get("location"),
                    "content_length": result.get("content_length"),
                    "parsed_rows": len(rows),
                    "five_parts_complete": complete,
                    "latest_ex_date": latest.get("ex_date_roc"),
                    "capital_gain_pct": latest.get("capital_gain_pct"),
                    "error": result.get("error"),
                }
            )
            raw_results.append((label, attempt, result, rows))
            current += 1
            progress.progress(current / total)
            if pause_sec:
                time.sleep(pause_sec)

    summary_df = pd.DataFrame(summary_rows)
    st.subheader("總表")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    failures = summary_df[
        (summary_df["status"] != 200)
        | (summary_df["parsed_rows"] < 1)
        | (~summary_df["five_parts_complete"])
    ]

    if failures.empty:
        st.success(
            "所有測試皆為 HTTP 200，且每次都成功解析 00919 五項配息組成。"
            "先前 307 較可能是 TWSE 偶發回應，而不是固定程式錯誤。"
        )
    else:
        st.warning(
            f"共有 {len(failures)} 次未完整通過。請比較 U75f 原始標頭與完整瀏覽器標頭，"
            "即可判斷是標頭差異或偶發連線問題。"
        )

    st.subheader("各次詳細結果")
    for label, attempt, result, rows in raw_results:
        with st.expander(f"{label}｜第 {attempt} 次", expanded=False):
            st.json(public_result(result))
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
                if is_complete(rows):
                    st.success("五項配息組成完整。")
                else:
                    st.error("有解析到 00919，但五項配息組成不完整。")
            else:
                st.error("未解析到 00919。")

    st.subheader("判讀方式")
    st.markdown(
        """
- **只有 U75f 原始標頭失敗、完整瀏覽器標頭成功**：主程式需補完整標頭。
- **urllib 偶發失敗、requests 穩定成功**：主程式改用 `requests.Session()` 並保留 urllib 備援。
- **所有方式偶發 307**：TWSE 端為暫時性回應，主程式需加入 307 重試與無參數頁備援。
- **所有方式每次都成功**：先前 307 是短暫事件；主程式仍應補重試與備援，避免再次卡住。
        """
    )
else:
    st.info("按上方按鈕後，會對五種方式各重複測試，判斷 307 是否與標頭、函式庫或偶發性有關。")
