import requests
import time
import streamlit as st
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ======================
# 1. 頁面基本設定 (保持不變)
# ======================
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
all_class = ["A", "B"]
all_stock = {
    "A": [["2330", 5, 20, 60], ["0053", 5, 10, 15]],
    "B": [["0050", 8, 25, 68]],
}

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

        st.markdown(
            f'<div style="text-align: right; color: #888; font-size: 12px;">最後更新：{datetime.now().strftime("%H:%M:%S")}</div>',
            unsafe_allow_html=True,
        )

    time.sleep(10)
