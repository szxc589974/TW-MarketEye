import requests
import time
import streamlit as st
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ======================
# 1. 頁面基本設定 (保持不變)
# ======================
st.set_page_config(page_title="台股 1-12 項極速監控", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] { background-color: #000000; }
    .stock-up { color: #FF3333 !important; font-weight: bold; }
    .stock-down { color: #00FF00 !important; font-weight: bold; }
    .stock-none { color: #FFFFFF !important; }
    .custom-table {
        width: 100%; border-collapse: collapse; background-color: #111111; color: white; font-family: 'Consolas', monospace;
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
            "volume": int(info.get("v", 0)) * 1000,  # 修正為股數
            "yesterday_close": y,
            "time": info.get("t", ""),
            "sys_time": datetime.now().strftime("%H:%M:%S"),
        }
    except:
        return None


# ======================
# 3. 側邊欄設定
# ======================
with st.sidebar:
    st.header("⚙️ 參數設定")
    user_stock = st.text_input("股票代號", value="2330")
    day_a = st.number_input("天數 A (MA/MV)", value=5)
    day_b = st.number_input("天數 B (MA)", value=20)
    st.write("---")
    st.info("💡 系統已啟動無感背景更新 (每10秒)")

# ======================
# 4. 核心動態更新區域
# ======================

# 建立一個空容器，後面的 while 迴圈會不斷更新這裡
placeholder = st.empty()

# 進入無窮迴圈進行「內部更新」
while True:
    with placeholder.container():
        max_target = max(day_a, day_b)
        history_data = get_history_base(user_stock, max_target)
        realtime = get_realtime_info(user_stock)

        if history_data and realtime:
            # 算法邏輯
            prices = [item["收盤價"] for item in history_data]
            volumes = [
                item["成交股數"] / 1000 for item in history_data
            ]  # 以張為單位計算

            ma_daya = sum(prices[-day_a:]) / day_a
            ma_dayb = sum(prices[-day_b:]) / day_b
            mv_daya = sum(volumes[-(day_a + 1) : -1]) / day_a

            diff = realtime["price"] - realtime["yesterday_close"]
            diff_percent = (diff / realtime["yesterday_close"]) * 100

            # 計算預估量 (簡易邏輯)
            now = datetime.now()
            market_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
            minutes_passed = (now - market_start).total_seconds() / 60
            minutes_passed = max(1, min(270, minutes_passed))

            # 成交量轉換為「張」來顯示與計算
            vol_shares = realtime["volume"]
            vol_lots = vol_shares / 1000
            est_vol_lots = (vol_lots / minutes_passed) * 270

            price_ma_diff = ((realtime["price"] - ma_daya) / ma_daya) * 100
            vol_ratio = (vol_lots / mv_daya) * 100

            color_cls = (
                "stock-up" if diff > 0 else "stock-down" if diff < 0 else "stock-none"
            )

            st.markdown(f"### 📊 {realtime['name']} ({user_stock}) 盤中即時行情")

            html_code = f"""
            <table class="custom-table">
                <thead>
                    <tr>
                        <th>1.代號</th><th>2.名稱</th><th>3.成交價</th><th>4.漲跌(%)</th><th>4a.MA{day_a}差比</th>
                        <th>5.MA{day_a}</th><th>6.天數A</th><th>7.MA{day_b}</th><th>8.天數B</th>
                        <th>9.成交張數</th><th>10.量增比</th><th>11.日均量(張)</th><th>12.預估量(張)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{user_stock}</td><td>{realtime['name']}</td>
                        <td class="{color_cls}">{realtime['price']:.2f}</td>
                        <td class="{color_cls}">{diff:+.2f} ({diff_percent:+.2f}%)</td>
                        <td class="{color_cls}">{price_ma_diff:+.2f}%</td>
                        <td>{ma_daya:.2f}</td><td>{day_a}</td><td>{ma_dayb:.2f}</td><td>{day_b}</td>
                        <td style="color: #00D2FF;">{vol_lots:,.0f}</td>
                        <td style="color: #FF00FF;">{vol_ratio:.2f}%</td>
                        <td style="color: #BBBBBB;">{mv_daya:.2f}</td>
                        <td style="color: #FFA500;">{est_vol_lots:.0f}</td>
                    </tr>
                </tbody>
            </table>
            """
            st.write(html_code, unsafe_allow_html=True)
            st.markdown(
                f'<div style="text-align: right; color: #888; font-size: 12px;">最後更新：{realtime["sys_time"]} (每10秒自動同步)</div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("抓取資料中...")

    # 關鍵：停頓 10 秒後重複執行
    time.sleep(10)
