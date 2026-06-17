import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
import ssl

import requests
import streamlit as st

FILTERED_URL = (
    "https://www.twse.com.tw/zh/ETFortune/dividendList"
    "?stkNo=00919&startDate=2026&endDate=2026"
)
BASE_URL = "https://www.twse.com.tw/zh/ETFortune/dividendList"
HEADERS = {
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
    value = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def pct(text: str, label: str):
    m = re.search(re.escape(label) + r"\s*[:：]?\s*([0-9.]+)\s*%", text)
    return float(m.group(1)) if m else None


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
        rows.append({
            "ex_date_roc": match.group("ex"),
            "record_date_roc": match.group("record"),
            "pay_date_roc": match.group("pay"),
            "dividend_per_share": float(match.group("amount")),
            "dividend_income_pct": pct(details, "股利所得占比"),
            "interest_income_pct": pct(details, "利息所得占比"),
            "equalization_pct": pct(details, "收益平準金占比"),
            "capital_gain_pct": pct(details, "已實現資本利得占比"),
            "other_income_pct": pct(details, "其他所得占比"),
        })
    return rows


def requests_probe(url: str, allow_redirects: bool):
    session = requests.Session()
    response = session.get(
        url,
        headers=HEADERS,
        timeout=(8, 30),
        allow_redirects=allow_redirects,
    )
    return {
        "status": response.status_code,
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
        "html": response.text,
    }


def urllib_probe(url: str):
    opener = build_opener(
        ProxyHandler({}),
        HTTPSHandler(context=ssl._create_unverified_context()),
    )
    req = Request(url, headers=HEADERS)
    try:
        with opener.open(req, timeout=30) as response:
            body = response.read().decode("utf-8", "ignore")
            return {
                "status": getattr(response, "status", None),
                "final_url": response.geturl(),
                "location": response.headers.get("Location"),
                "content_length": len(body.encode("utf-8")),
                "contains_00919": "00919" in body,
                "contains_composition": "已實現資本利得占比" in body,
                "html": body,
            }
    except HTTPError as exc:
        return {
            "error": f"HTTPError {exc.code}: {exc.reason}",
            "status": exc.code,
            "final_url": exc.geturl(),
            "location": exc.headers.get("Location") if exc.headers else None,
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "html": "",
        }
    except URLError as exc:
        return {"error": f"URLError: {exc.reason}", "html": ""}


def public_view(result):
    return {key: value for key, value in result.items() if key != "html"}


st.set_page_config(page_title="TWSE 00919 54C 獨立測試", layout="wide")
st.title("TWSE e添富 00919 配息組成獨立測試")
st.caption("只做連線、重新導向與五項配息組成解析；不讀寫 Dashboard 資料。")

if st.button("執行獨立測試", type="primary", use_container_width=True):
    tests = []

    with st.spinner("測試 urllib（目前主程式方式）…"):
        urllib_filtered = urllib_probe(FILTERED_URL)
        tests.append(("urllib｜帶篩選參數", urllib_filtered))

    with st.spinner("測試 requests｜帶篩選參數，不跟轉址…"):
        try:
            req_no_redirect = requests_probe(FILTERED_URL, allow_redirects=False)
        except Exception as exc:
            req_no_redirect = {"error": f"{type(exc).__name__}: {exc}", "html": ""}
        tests.append(("requests｜帶參數｜不跟轉址", req_no_redirect))

    with st.spinner("測試 requests｜帶篩選參數，自動跟轉址…"):
        try:
            req_redirect = requests_probe(FILTERED_URL, allow_redirects=True)
        except Exception as exc:
            req_redirect = {"error": f"{type(exc).__name__}: {exc}", "html": ""}
        tests.append(("requests｜帶參數｜跟轉址", req_redirect))

    with st.spinner("測試 requests｜無參數官方清單頁…"):
        try:
            req_base = requests_probe(BASE_URL, allow_redirects=True)
        except Exception as exc:
            req_base = {"error": f"{type(exc).__name__}: {exc}", "html": ""}
        tests.append(("requests｜官方清單基底網址", req_base))

    st.subheader("連線測試結果")
    for label, result in tests:
        with st.expander(label, expanded=True):
            st.json(public_view(result))
            html = result.get("html") or ""
            if html:
                rows = parse_00919(html)
                st.write(f"00919 解析筆數：**{len(rows)}**")
                if rows:
                    st.dataframe(rows, use_container_width=True)
                    latest = rows[0]
                    complete = all(
                        latest.get(key) is not None
                        for key in (
                            "dividend_income_pct",
                            "interest_income_pct",
                            "equalization_pct",
                            "capital_gain_pct",
                            "other_income_pct",
                        )
                    )
                    if complete:
                        st.success("五項配息組成解析完整。")
                    else:
                        st.error("有抓到 00919，但五項配息組成不完整。")

    st.subheader("判定")
    base_rows = parse_00919(req_base.get("html") or "")
    redirected_rows = parse_00919(req_redirect.get("html") or "")
    if base_rows:
        st.success("無參數官方清單頁可取得並解析 00919；可作為避開 307 的候選來源。")
    else:
        st.error("無參數官方清單頁仍未解析到 00919。")
    if redirected_rows:
        st.success("帶參數網址經 requests 跟隨轉址後可取得並解析 00919。")
    else:
        st.warning("帶參數網址在此環境仍無法取得完整 00919 組成。")
else:
    st.info("按上方按鈕後，會顯示 307 的 Location、轉址歷史、最終 HTTP 狀態及五項組成解析結果。")
