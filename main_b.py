import streamlit as st
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


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
st.set_page_config(page_title="台股 1-15 項極速監控", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] { background-color: #000000; }
    .stock-up { color: #FF3333 !important; font-weight: bold; }
    .stock-down { color: #00FF00 !important; font-weight: bold; }
    .stock-none { color: #FFFFFF !important; }
    .highlight-gold { color: #FFD700 !important; font-weight: bold; } /* 線價比 5% 內 */
    .highlight-purple { color: #FF00FF !important; font-weight: bold; } /* 量增比 2倍以上 */
    .normal-white { color: #FFFFFF !important; }
    .custom-table {
        width: 100%; border-collapse: collapse; background-color: #111111; color: white; font-family: 'Consolas', monospace;
        margin-bottom: 20px;
    }
    .custom-table th { background-color: #003366; color: #FFFF00; padding: 10px; border: 1px solid #444; font-size: 14px; }
    .custom-table td { padding: 18px 10px; border: 1px solid #444; text-align: center; font-size: 22px; font-weight: bold; }
    </style>
""",
    unsafe_allow_html=True,
)


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


# _______________________________以下是股票程式___________________________________________


# ======================
# 2. 資料抓取函數 (保持不變)
# ======================
@st.cache_data(ttl=3600)
def get_history_base(stock_no, max_count):
    now = datetime.now()
    current_date = now.replace(day=1)
    all_data = []
    while len(all_data) < max_count + 5:
        date_str = current_date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date_str}&stockNo={stock_no}&response=html"
        try:
            resp = requests.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                month_data = []
                for row in rows:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 9:
                        month_data.append(
                            {
                                "收盤價": float(cols[6].replace(",", "")),
                                "成交股數": int(cols[1].replace(",", "")),
                            }
                        )
                all_data = month_data + all_data
            current_date = (current_date.replace(day=1) - timedelta(days=1)).replace(
                day=1
            )
            time.sleep(0.3)
        except:
            break
    return all_data


def get_realtime_info(stock_no):
    try:
        timestamp = int(time.time() * 1000)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_no}.tw&json=1&delay=0&_={timestamp}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
        }
        resp = requests.get(url, headers=headers, timeout=5)
        json_data = resp.json()
        if not json_data.get("msgArray"):
            return None
        info = json_data["msgArray"][0]
        z = info.get("z", "-")
        y = float(info.get("y", 0))
        if z != "-" and float(z) != 0:
            latest_price = float(z)
        else:
            b_list = info.get("b", "").split("_")
            latest_price = float(b_list[0]) if b_list[0] and b_list[0] != "-" else y

        return {
            "name": info.get("n", ""),
            "price": latest_price,
            "volume": int(info.get("v", 0)) * 1000,
            "yesterday_close": y,
            "time": info.get("t", ""),
            "sys_time": datetime.now().strftime("%H:%M:%S"),
        }
    except:
        return None


# ======================
# 3. 預估量權重表 (保持不變)
# ======================
EST_FACTORS = {
    "09:05": 14.99,
    "09:10": 9.48,
    "09:15": 7.12,
    "09:20": 5.83,
    "09:25": 4.99,
    "09:30": 4.42,
    "09:35": 3.99,
    "09:40": 3.66,
    "09:45": 3.39,
    "09:50": 3.18,
    "09:55": 2.99,
    "10:00": 2.83,
    "10:05": 2.70,
    "10:10": 2.58,
    "10:15": 2.48,
    "10:20": 2.39,
    "10:25": 2.30,
    "10:30": 2.23,
    "10:35": 2.15,
    "10:40": 2.09,
    "10:45": 2.03,
    "10:50": 1.97,
    "10:55": 1.92,
    "11:00": 1.87,
    "11:05": 1.83,
    "11:10": 1.79,
    "11:15": 1.74,
    "11:20": 1.71,
    "11:25": 1.67,
    "11:30": 1.63,
    "11:35": 1.60,
    "11:40": 1.57,
    "11:45": 1.54,
    "11:50": 1.51,
    "11:55": 1.48,
    "12:00": 1.46,
    "12:05": 1.43,
    "12:10": 1.41,
    "12:15": 1.38,
    "12:20": 1.36,
    "12:25": 1.34,
    "12:30": 1.32,
    "12:35": 1.30,
    "12:40": 1.28,
    "12:45": 1.25,
    "12:50": 1.23,
    "12:55": 1.21,
    "13:00": 1.19,
    "13:05": 1.17,
    "13:10": 1.14,
    "13:15": 1.12,
    "13:20": 1.09,
    "13:25": 1.06,
    "13:30": 1.00,
}


def get_est_factor(current_time_str):
    keys = sorted(EST_FACTORS.keys())
    factor = 1.0
    for k in keys:
        if current_time_str <= k:
            factor = EST_FACTORS[k]
            break
    if current_time_str > "13:30":
        factor = 1.0
    if current_time_str < "09:05":
        factor = 14.99
    return factor


# ======================
# 4. 資料清單設定
# ======================
# 1. 依照登入的帳號去 sheet2 拿取所有 class
group_data = sheet2.get_all_records()
df_groups = pd.DataFrame(group_data)

if not df_groups.empty and "username" in df_groups.columns:
    # 篩選出該使用者的群組，並轉成清單 (使用 unique() 避免重複)
    all_class = (
        df_groups[df_groups["username"] == current_user]["class"].unique().tolist()
    )
else:
    all_class = []

# 2. 依照登入的帳號去 sheet1 拿取 stock_no, day_a, day_b, day_c
records = sheet1.get_all_records()
df_records = pd.DataFrame(records)

all_stock = {}

if not df_records.empty and "username" in df_records.columns:
    # 步驟 A: 先篩選出目前登入使用者的資料
    user_df = df_records[df_records["username"] == current_user]

    # 步驟 B: 依照 'class' 分群處理
    for group_name, group_df in user_df.groupby("class"):
        # 步驟 C: 將每一列轉成 [no, day_a, day_b, day_c] 的格式
        stock_list = group_df[["no", "day_a", "day_b", "day_c"]].values.tolist()

        # 強制轉型：確保 no 是字串，天數是整數 (避免從 Sheet 抓下來型別混亂)
        clean_stock_list = [
            [
                str((str(item[0]).split(".")[0]).zfill(4)),
                int(item[1]),
                int(item[2]),
                int(item[3]),
            ]
            for item in stock_list
        ]

        # 存入字典
        all_stock[group_name] = clean_stock_list
else:
    all_stock = {}
# all_class = ["A", "B"]
# all_stock = {
#     "A": [["2330", 5, 20, 60], ["0053", 5, 10, 15]],
#     "B": [["0050", 8, 25, 68]],
# }
print(f"all_class:{all_class}")
print(f"all_stock:{all_stock}")
# ======================
# 5. 核心動態更新區域
# ======================
placeholder = st.empty()

while True:
    with placeholder.container():
        # 按照 all_class 列表順序取出群組
        for group in all_class:
            if group in all_stock:
                st.markdown(f"## 📁 {group}")  # 顯示群組名稱標題

                # 取出該群組內的所有股票設定
                for config in all_stock[group]:
                    user_stock, day_a, day_b, day_c = config

                    max_target = max(day_a, day_b, day_c)
                    history_data = get_history_base(user_stock, max_target)
                    realtime = get_realtime_info(user_stock)

                    if history_data and realtime:
                        # --- 算法邏輯 (完全保留) ---
                        prices = [item["收盤價"] for item in history_data]
                        volumes = [item["成交股數"] / 1000 for item in history_data]

                        ma_daya = sum(prices[-day_a:]) / day_a
                        ma_dayb = sum(prices[-day_b:]) / day_b
                        ma_dayc = sum(prices[-day_c:]) / day_c

                        last_4_vol = sum(volumes[-4:])
                        diff = realtime["price"] - realtime["yesterday_close"]
                        diff_percent = (diff / realtime["yesterday_close"]) * 100

                        current_t = datetime.now().strftime("%H:%M")
                        factor = get_est_factor(current_t)
                        vol_lots = realtime["volume"] / 1000
                        est_vol_lots = vol_lots * factor
                        mv_custom = (est_vol_lots + last_4_vol) / 5

                        price_ma_diff = ((realtime["price"] - ma_daya) / ma_daya) * 100
                        vol_ratio = (
                            (est_vol_lots / mv_custom) * 100 if mv_custom > 0 else 0
                        )

                        color_cls = (
                            "stock-up"
                            if diff > 0
                            else "stock-down" if diff < 0 else "stock-none"
                        )
                        ma_diff_color = (
                            "highlight-gold"
                            if abs(price_ma_diff) <= 5
                            else "normal-white"
                        )
                        vol_ratio_color = (
                            "highlight-purple" if vol_ratio >= 200 else "normal-white"
                        )

                        # --- HTML 寫法 (照原本的，不多做結構改動) ---
                        html_code = f"""
                        <table class="custom-table">
                            <thead>
                                <tr>
                                    <th>1.代號</th><th>2.名稱</th><th>3.成交價</th><th>4.漲跌(%)</th><th>5.線價比</th>
                                    <th>6.均線A</th><th>7.天數A</th><th>8.均線B</th><th>9.天數B</th>
                                    <th>10.均線C</th><th>11.天數C</th>
                                    <th>12.成交張數</th><th>13.量增比</th><th>14.日均量(張)</th><th>15.預估量(張)</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>{user_stock}</td><td>{realtime['name']}</td>
                                    <td class="{color_cls}">{realtime['price']:.2f}</td>
                                    <td class="{color_cls}">{diff:+.2f} ({diff_percent:+.2f}%)</td>
                                    <td class="{ma_diff_color}">{price_ma_diff:+.2f}%</td>
                                    <td>{ma_daya:.2f}</td><td>{day_a}</td><td>{ma_dayb:.2f}</td><td>{day_b}</td>
                                    <td>{ma_dayc:.2f}</td><td>{day_c}</td>
                                    <td style="color: #00D2FF;">{vol_lots:,.0f}</td>
                                    <td class="{vol_ratio_color}">{vol_ratio:.2f}%</td>
                                    <td style="color: #BBBBBB;">{mv_custom:.2f}</td>
                                    <td style="color: #FFA500;">{est_vol_lots:.0f}</td>
                                </tr>
                            </tbody>
                        </table>
                        """
                        st.write(html_code, unsafe_allow_html=True)
                    else:
                        st.warning(f"正在抓取 {user_stock} 資料中...")
        realtime = get_realtime_info(user_stock)
        print("DEBUG:", user_stock, realtime)
        st.markdown(
            f'<div style="text-align: right; color: #888; font-size: 12px;">最後更新：{datetime.now().strftime("%H:%M:%S")}</div>',
            unsafe_allow_html=True,
        )

    time.sleep(10)
