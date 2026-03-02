import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd


# --- 0. 登入邏輯檢查 ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.subheader("🔐 系統登入")
        user_input = st.text_input("請輸入授權帳號", type="default")
        allowed_users = st.secrets["auth"]["allowed_users"]

        if st.button("進入系統"):
            if user_input in allowed_users:
                st.session_state.logged_in = True
                st.session_state.current_user = user_input
                st.success("登入成功！")
                st.rerun()
            else:
                st.error("帳號錯誤，請聯繫管理員。")
        st.stop()


check_login()


# --- 1. 初始化與連線 ---
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    # 請確保您的 creds.json 檔案存在
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    return client


client = init_connection()
spreadsheet = client.open_by_key("10Oz6imH-bywS6sk23HquvgUw-3rKHLMU4g8MCC8ek-M")
sheet1 = spreadsheet.get_worksheet(0)  # 參數紀錄
sheet2 = spreadsheet.get_worksheet(1)  # 群組定義

current_user = st.session_state.current_user

st.title("📈 股票參數永久保存系統")
st.caption(f"當前使用者：{current_user}")

# --- 2. 側邊欄：群組管理 (篩選使用者) ---
with st.sidebar:
    if st.button("🚪 登出系統"):
        st.session_state.logged_in = False
        st.rerun()

    st.header("📂 群組管理")
    new_group_name = st.text_input("建立新群組名稱")
    if st.button("➕ 建立群組", use_container_width=True):
        if new_group_name:
            # 工作表二：第一欄 username, 第二欄 class
            sheet2.append_row([current_user, new_group_name])
            st.success(f"群組 '{new_group_name}' 建立成功！")
            st.rerun()
        else:
            st.warning("請輸入群組名稱")

    st.divider()

    # 讀取群組並篩選屬於目前使用者的群組
    group_data = sheet2.get_all_records()  # 使用 get_all_records 較易根據欄位篩選
    df_groups = pd.DataFrame(group_data)

    if not df_groups.empty and "username" in df_groups.columns:
        user_groups = df_groups[df_groups["username"] == current_user]["class"].tolist()
    else:
        user_groups = []

    st.header("⚙️ 參數設定")
    with st.form("input_form"):
        stock_no = st.text_input("股票代號 (No)")
        category = st.selectbox(
            "分類 (Class)",
            user_groups if user_groups else ["請先建立群組"],
            disabled=not user_groups,
        )

        day_a = st.number_input("天數 A (day_a)", min_value=1, value=5)
        day_b = st.number_input("天數 B (day_b)", min_value=1, value=20)
        day_c = st.number_input("天數 C (day_c)", min_value=1, value=60)  # 新增 day_c
        submitted = st.form_submit_button("💾 永久儲存至雲端", use_container_width=True)

# --- 3. 處理參數寫入 (加入資料隔離與 Day C) ---
if submitted:
    if not user_groups:
        st.sidebar.error("❌ 請先建立群組後再儲存！")
    elif stock_no:
        records = sheet1.get_all_records()
        df_existing = pd.DataFrame(records)
        now_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        existing_row_index = None
        if not df_existing.empty:
            # 嚴格篩選：必須是該使用者且代號相同
            match = df_existing[
                (df_existing["username"] == current_user)
                & (df_existing["no"].astype(str) == str(stock_no))
            ]
            if not match.empty:
                existing_row_index = match.index[0]
                old_day_a = match.iloc[0]["day_a"]
                old_day_b = match.iloc[0]["day_b"]
                old_day_c = match.iloc[0].get("day_c", 0)  # 取得舊的 day_c

        if existing_row_index is not None:
            # 檢查是否有變動 (包含 day_c)
            if old_day_a == day_a and old_day_b == day_b and old_day_c == day_c:
                st.sidebar.info(f"ℹ️ {stock_no} 參數相同，無需更新。")
            else:
                # 更新邏輯 (假設欄位：1.時間, 2.username, 3.no, 4.day_a, 5.day_b, 6.day_c, 7.class)
                row_to_update = int(existing_row_index) + 2
                sheet1.update_cell(row_to_update, 1, now_time)
                sheet1.update_cell(row_to_update, 4, day_a)
                sheet1.update_cell(row_to_update, 5, day_b)
                sheet1.update_cell(row_to_update, 6, day_c)  # 更新 Day C
                sheet1.update_cell(row_to_update, 7, category)  # 更新 Class 移至第 7 欄

                st.sidebar.success(f"🔄 {stock_no} 的參數已更新！")
                st.rerun()
        else:
            # 新增資料：時間, username, no, day_a, day_b, day_c, class
            new_row = [now_time, current_user, stock_no, day_a, day_b, day_c, category]
            sheet1.append_row(new_row)
            st.sidebar.success(f"✅ {stock_no} 已新增儲存！")
            st.rerun()
    else:
        st.sidebar.error("請填寫股票代號 (No)")

# --- 4. 主畫面：顯示資料 (只顯示該使用者的資料) ---
st.subheader("📜 歷史保存紀錄")
records = sheet1.get_all_records()

if records:
    df_all = pd.DataFrame(records)
    # 關鍵：只篩選當前登入者的資料
    df_user = df_all[df_all["username"] == current_user]
    print(df_user)
    print(type(df_user))
    if not df_user.empty:
        st.dataframe(
            df_user,
            use_container_width=True,
            hide_index=True,
            column_config={
                "時間": st.column_config.DatetimeColumn(
                    "儲存時間", format="MM-DD HH:mm"
                ),
                "username": "使用者",
                "no": "股票代號",
                "day_a": "天數 A",
                "day_b": "天數 B",
                "day_c": "天數 C",
                "class": "策略分類",
            },
        )
    else:
        st.info(f"您（{current_user}）目前尚無任何紀錄。")
else:
    st.info("目前雲端試算表中尚無任何紀錄。")


# _______________________________以下是股票程式___________________________________________
