import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ======================
# 1. 頁面設定
# ======================
st.set_page_config(page_title="台股雲端監控系統", layout="wide")

st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] { background-color: #000000; }
.stock-up { color: #FF3333; font-weight: bold; }
.stock-down { color: #00FF00; font-weight: bold; }
.stock-none { color: #FFFFFF; }

.custom-table {
    width: 100%;
    border-collapse: collapse;
    background-color: #111;
    color: white;
    font-family: Consolas, monospace;
}
.custom-table th {
    background-color: #002D5E;
    color: #FFFF00;
    padding: 10px;
    border: 1px solid #444;
}
.custom-table td {
    padding: 14px;
    border: 1px solid #333;
    text-align: center;
    font-size: 22px;
    font-weight: bold;
}

.group-header {
    border-left: 8px solid orange;
    padding-left: 10px;
    margin: 25px 0 10px;
    color: #00D2FF;
    font-size: 24px;
}

.col-vol { color: #00D2FF; }
.col-ratio { color: #FF00FF; }
.col-avg { color: #BBBBBB; }
.col-est { color: #FFA500; }
</style>
""",
    unsafe_allow_html=True,
)


# ======================
# 2. 登入
# ======================
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        user = st.text_input("授權帳號")
        if st.button("登入"):
            if user in st.secrets["auth"]["allowed_users"]:
                st.session_state.logged_in = True
                st.session_state.current_user = user
                st.rerun()
        st.stop()


check_login()


# ======================
# 3. Google Sheet
# ======================
@st.cache_resource
def init_gs():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    return gspread.authorize(creds)


client = init_gs()
sheet1 = client.open_by_key(
    "10Oz6imH-bywS6sk23HquvgUw-3rKHLMU4g8MCC8ek-M"
).get_worksheet(0)


# ======================
# 4. 資料函式
# ======================
@st.cache_data(ttl=3600)
def get_history(stock, n):
    now = datetime.now().replace(day=1)
    data = []
    while len(data) < n + 5:
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={now.strftime('%Y%m%d')}&stockNo={stock}&response=html"
        soup = BeautifulSoup(requests.get(url).text, "html.parser")
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]
            month = []
            for r in rows:
                td = [x.text.strip() for x in r.find_all("td")]
                if len(td) >= 9:
                    month.append(
                        {
                            "p": float(td[6].replace(",", "")),
                            "v": int(td[1].replace(",", "")) / 1000,
                        }
                    )
            data = month + data
        now = (now - timedelta(days=1)).replace(day=1)
    return data


def realtime(stock):
    j = requests.get(
        f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock}.tw&json=1"
    ).json()
    if not j["msgArray"]:
        return None
    i = j["msgArray"][0]
    price = float(i["z"]) if i["z"] not in ("-", "0") else float(i["y"])
    return {"name": i["n"], "price": price, "y": float(i["y"]), "vol": int(i["v"]) / 1}


# ======================
# 5. 主畫面
# ======================
placeholder = st.empty()

while True:
    with placeholder.container():
        df = pd.DataFrame(sheet1.get_all_records())
        user_df = df[df["username"] == st.session_state.current_user]

        for grp, g in user_df.groupby("class"):
            st.markdown(
                f"<div class='group-header'>📁 {grp}</div>", unsafe_allow_html=True
            )

            html = """
            <table class="custom-table">
            <thead>
            <tr>
                <th>代號</th><th>名稱</th><th>成交價</th><th>漲跌</th>
                <th>MA差</th><th>MA5</th><th>5</th>
                <th>MA20</th><th>20</th>
                <th>量</th><th>量比</th><th>均量</th><th>估量</th>
            </tr>
            </thead><tbody>
            """

            for _, r in g.iterrows():
                rt = realtime(r["no"])
                hist = get_history(r["no"], max(r["day_a"], r["day_b"]))
                if not rt or not hist:
                    continue

                p = [x["p"] for x in hist]
                v = [x["v"] for x in hist]

                ma5 = sum(p[-5:]) / 5
                ma20 = sum(p[-20:]) / 20
                mv = sum(v[-6:-1]) / 5

                diff = rt["price"] - rt["y"]
                cls = "stock-up" if diff > 0 else "stock-down"

                html += f"""
                <tr>
                    <td>{r["no"]}</td>
                    <td>{rt["name"]}</td>
                    <td class="{cls}">{rt["price"]:.2f}</td>
                    <td class="{cls}">{diff:+.2f}</td>
                    <td>{(rt["price"]-ma5)/ma5*100:+.2f}%</td>
                    <td>{ma5:.2f}</td><td>5</td>
                    <td>{ma20:.2f}</td><td>20</td>
                    <td class="col-vol">{rt["vol"]:.0f}</td>
                    <td class="col-ratio">{rt["vol"]/mv*100:.1f}%</td>
                    <td class="col-avg">{mv:.0f}</td>
                    <td class="col-est">{rt["vol"]*2:.0f}</td>
                </tr>
                """

            html += "</tbody></table>"
            st.write(html, unsafe_allow_html=True)

        st.markdown(
            f"<div style='text-align:right;color:#666'>更新 {datetime.now().strftime('%H:%M:%S')}</div>",
            unsafe_allow_html=True,
        )

    time.sleep(10)
    st.rerun()
