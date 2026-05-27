from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
WORKSHEET_NAME = "Trades"
DEFAULT_HEADERS = ["trade_date", "action", "shares", "price", "note_type", "note"]


@dataclass
class TradesLoadResult:
    rows: list[dict]
    source: str
    message: str


def _clean_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _pick(row: dict, *keys: str, default: Any = "") -> Any:
    normalized = {_clean_key(key): value for key, value in row.items()}
    for key in keys:
        value = normalized.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return default


def _to_int(value: Any) -> int:
    text = str(value or "0").replace(",", "").strip()
    return int(float(text or 0))


def _to_float(value: Any) -> float:
    text = str(value or "0").replace(",", "").strip()
    return float(text or 0)


def _normalize_action(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"sell", "s", "賣", "賣出"}:
        return "sell"
    return "buy"


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip().replace("/", "-").replace(".", "-")
    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = parts
        return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
    return text


def normalize_sheet_trade(row: dict, index: int) -> dict:
    trade_date = _normalize_date(_pick(row, "trade_date", "date", "交易日期"))
    action = _normalize_action(_pick(row, "action", "buy_sell", "type", "買賣", "買 / 賣"))
    shares = _to_int(_pick(row, "shares", "qty", "quantity", "交易股數", "股數"))
    price = _to_float(_pick(row, "price", "trade_price", "成交價位", "成交價格", "價位"))
    note_type = str(_pick(row, "note_type", "category", "資金來源", "備註分類", default="其他")).strip() or "其他"
    note = str(_pick(row, "note", "memo", "remark", "備註", default="")).strip()

    return {
        "id": f"sheets-{trade_date}-{index}-{action}-{shares}-{price}",
        "trade_date": trade_date,
        "action": action,
        "shares": shares,
        "price": price,
        "fee": _to_float(_pick(row, "fee", "手續費", default=0)),
        "tax": _to_float(_pick(row, "tax", "交易稅", default=0)),
        "note_type": note_type,
        "note": note,
    }


def load_google_sheets_trades() -> TradesLoadResult:
    service_account = dict(st.secrets["gcp_service_account"])
    sheet_id = st.secrets["GOOGLE_SHEET_ID"]

    credentials = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key(sheet_id).worksheet(WORKSHEET_NAME)
    records = worksheet.get_all_records()

    trades = [
        normalize_sheet_trade(row, index)
        for index, row in enumerate(records)
        if any(str(value).strip() for value in row.values())
    ]
    return TradesLoadResult(
        rows=trades,
        source="google_sheets",
        message=f"使用 Google Sheets Trades：成功讀取 {len(trades)} 筆",
    )


def append_trade_to_google_sheets(trade: dict) -> dict:
    service_account = dict(st.secrets["gcp_service_account"])
    sheet_id = st.secrets["GOOGLE_SHEET_ID"]

    credentials = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key(sheet_id).worksheet(WORKSHEET_NAME)

    headers = [str(item).strip() for item in worksheet.row_values(1)]
    if not headers:
        headers = DEFAULT_HEADERS
        worksheet.append_row(headers, value_input_option="USER_ENTERED")

    normalized = normalize_sheet_trade(trade, 0)
    values_by_header = {
        "trade_date": normalized["trade_date"],
        "action": normalized["action"].upper(),
        "shares": normalized["shares"],
        "price": normalized["price"],
        "note_type": normalized["note_type"],
        "note": normalized["note"],
        "fee": normalized.get("fee", 0),
        "tax": normalized.get("tax", 0),
    }
    row_values = [values_by_header.get(header, "") for header in headers]
    worksheet.append_row(row_values, value_input_option="USER_ENTERED")
    return {
        "ok": True,
        "message": "新增交易已寫入 Google Sheets",
        "trade": normalized,
    }
