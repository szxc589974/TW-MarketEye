import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd


# --- 0. 登入邏輯檢查 ---
def check_login():
    """檢查登入狀態，若未登入則顯示登入畫面"""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.subheader("🔐 系統登入")
        user_input = st.text_input("請輸入授權帳號", type="default")

        # 從 secrets 讀取名單
        allowed_users = st.secrets["auth"]["allowed_users"]

        if st.button("進入系統"):
            if user_input in allowed_users:
                st.session_state.logged_in = True
                st.session_state.current_user = user_input  # 記住目前使用者
                st.success("登入成功！")
                st.rerun()
            else:
                st.error("帳號錯誤，請聯繫管理員。")
        st.stop()  # 強制停止執行後面的程式碼


# 執行登入檢查
check_login()


# --- 1. 初始化與連線 ---
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    return client


client = init_connection()
spreadsheet = client.open_by_key("10Oz6imH-bywS6sk23HquvgUw-3rKHLMU4g8MCC8ek-M")
sheet1 = spreadsheet.get_worksheet(0)
sheet2 = spreadsheet.get_worksheet(1)

st.title("📈 股票參數永久保存系統")
st.caption(f"當前使用者：{st.session_state.current_user}")

# --- 2. 側邊欄開始 ---
with st.sidebar:
    if st.button("🚪 登出系統"):
        st.session_state.logged_in = False
        st.rerun()

    st.header("📂 群組管理")
    new_group_name = st.text_input("建立新群組名稱")
    if st.button("➕ 建立群組", use_container_width=True):
        if new_group_name:
            sheet2.append_row([new_group_name])
            st.success(f"群組 '{new_group_name}' 建立成功！")
            st.rerun()
        else:
            st.warning("請輸入群組名稱")

    st.divider()

    group_data = sheet2.get_all_values()
    group_options = (
        [row[0] for row in group_data[1:] if row] if len(group_data) > 1 else []
    )

    st.header("⚙️ 參數設定")
    with st.form("input_form"):
        stock_no = st.text_input("股票代號 (No)")
        if not group_options:
            category = st.selectbox("分類 (Class)", ["目前無群組"], disabled=True)
        else:
            category = st.selectbox("分類 (Class)", group_options)

        day_a = st.number_input("天數 A (day_a)", min_value=1, value=5)
        day_b = st.number_input("天數 B (day_b)", min_value=1, value=20)
        submitted = st.form_submit_button("💾 永久儲存至雲端", use_container_width=True)

# --- 3. 處理參數寫入 (核心邏輯修改處) ---
if submitted:
    if not group_options:
        st.sidebar.error("❌ 請先建立群組後再儲存！")
    elif stock_no:
        # 讀取現有資料進行比對
        records = sheet1.get_all_records()
        df_existing = pd.DataFrame(records)

        current_user = st.session_state.current_user
        now_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        # 檢查是否已有相同 帳號 + 股票代號 的紀錄
        # 註：請確保 Google Sheet 的欄位名稱與此處一致 (username, no, day_a, day_b)
        existing_row_index = None
        if not df_existing.empty:
            match = df_existing[
                (df_existing["username"] == current_user)
                & (df_existing["no"].astype(str) == str(stock_no))
            ]
            if not match.empty:
                existing_row_index = match.index[0]
                old_day_a = match.iloc[0]["day_a"]
                old_day_b = match.iloc[0]["day_b"]

        if existing_row_index is not None:
            # 狀況 1：完全相同 -> 不動作
            if old_day_a == day_a and old_day_b == day_b:
                st.sidebar.info(f"ℹ️ {stock_no} 參數相同，無需更新。")
            else:
                # 狀況 2：帳號股票同，但天數不同 -> 修改資料
                # gspread 的 index 是從 1 開始，且第一列是標題，所以 row index 要 + 2
                row_to_update = int(existing_row_index) + 2

                # 更新 Day A, Day B 以及 時間 (假設欄位順序：時間=1, username=2, no=3, day_a=4, day_b=5, class=6)
                sheet1.update_cell(row_to_update, 1, now_time)  # 更新時間
                sheet1.update_cell(row_to_update, 4, day_a)  # 更新 Day A
                sheet1.update_cell(row_to_update, 5, day_b)  # 更新 Day B
                sheet1.update_cell(row_to_update, 6, category)  # 同步更新分類

                st.sidebar.success(f"🔄 {stock_no} 的天數已更新！")
                st.rerun()
        else:
            # 狀況 3：全新資料 -> 新增一行
            new_row = [now_time, current_user, stock_no, day_a, day_b, category]
            sheet1.append_row(new_row)
            st.sidebar.success(f"✅ {stock_no} 已新增儲存！")
            st.rerun()
    else:
        st.sidebar.error("請填寫股票代號 (No)")

# --- 4. 主畫面：顯示資料 ---
st.subheader("📜 歷史保存紀錄")
records = sheet1.get_all_records()

if records:
    df = pd.DataFrame(records)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "時間": st.column_config.DatetimeColumn("儲存時間", format="MM-DD HH:mm"),
            "username": "使用者",
            "no": "股票代號",
            "day_a": "天數 A",
            "day_b": "天數 B",
            "class": "策略分類",
        },
    )
else:
    st.info("目前雲端試算表中尚無任何紀錄。")
