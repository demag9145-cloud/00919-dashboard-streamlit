from __future__ import annotations

import traceback

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
PRIVATE_FIELDS = {"private_key", "private_key_id", "client_email", "client_id"}


def mask_secret(value: object) -> str:
    text = str(value or "")
    if not text:
        return "(empty)"
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def sanitize_error_message(message: str, service_account: dict | None = None, sheet_id: str | None = None) -> str:
    sanitized = str(message or "")
    if service_account:
        for key in PRIVATE_FIELDS:
            value = service_account.get(key)
            if value:
                sanitized = sanitized.replace(str(value), mask_secret(value))
    if sheet_id:
        sanitized = sanitized.replace(str(sheet_id), mask_secret(sheet_id))
    return sanitized


def read_trades_preview() -> list[list[str]]:
    service_account = dict(st.secrets["gcp_service_account"])
    sheet_id = st.secrets["GOOGLE_SHEET_ID"]

    credentials = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key(sheet_id).worksheet("Trades")
    return worksheet.get("A1:Z5")


def main() -> None:
    st.set_page_config(page_title="Google Sheets 連線測試", page_icon="GS", layout="centered")
    st.title("Google Sheets 連線測試")

    try:
        rows = read_trades_preview()
    except KeyError as exc:
        st.error(f"缺少 Streamlit secrets 欄位：{exc}")
        st.info("請確認已設定 st.secrets['gcp_service_account'] 與 st.secrets['GOOGLE_SHEET_ID']。")
        return
    except Exception as exc:
        service_account = None
        sheet_id = None
        try:
            service_account = dict(st.secrets.get("gcp_service_account", {}))
            sheet_id = st.secrets.get("GOOGLE_SHEET_ID")
        except Exception:
            pass

        st.error("Google Sheets 連線或 Trades 工作表讀取失敗")
        st.code(sanitize_error_message(str(exc), service_account, sheet_id))

        with st.expander("除錯資訊（已遮蔽敏感資料）"):
            st.code(sanitize_error_message(traceback.format_exc(), service_account, sheet_id))
        return

    st.success("Google Sheets 連線成功")
    st.success("Trades 工作表讀取成功")
    st.write(f"讀到 {len(rows)} 列資料")

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Trades 工作表 A1:Z5 目前沒有資料。")


if __name__ == "__main__":
    main()
