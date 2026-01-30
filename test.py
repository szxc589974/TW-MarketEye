import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd


# 設定 Google Sheets 連線
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    # 確保 creds.json 與此程式碼在同一資料夾
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    return client


# 開啟試算表
client = init_connection()
# 請把 '你的試算表名稱' 改成你 Google Sheet 的實際標題
sheet = client.open("stock").sheet1

st.title("永久資料保存系統 (gspread 版)")

# 輸入介面
with st.form("input_form"):
    user_data = st.text_input("輸入要保存的內容：")
    submitted = st.form_submit_button("送出")

if submitted and user_data:
    # 寫入資料到試算表最後一行
    sheet.append_row([pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), user_data])
    st.success("資料已成功寫入 Google Sheets！")

# 讀取並顯示資料
st.subheader("歷史紀錄")
records = sheet.get_all_records()
if records:
    df = pd.DataFrame(records)
    st.table(df)
else:
    st.info("目前尚無資料")
