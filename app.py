import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# --- 1. ページ全体の基本設定 ---
st.set_page_config(page_title="AI投資スカウト", layout="wide")
st.title("🤖 コーポレート・インベスター・スカウト")
st.write("ターゲット企業（光通信・商社）の投資動向とAI分析を監視するダッシュボード")

# --- 2. ターゲット企業とEDINETコード ---
TARGET_COMPANIES = {
    "光通信 (9435)": {"ticker": "9435.T", "edinet_code": "E04430"},
    "伊藤忠商事 (8001)": {"ticker": "8001.T", "edinet_code": "E02502"},
    "三菱商事 (8058)": {"ticker": "8058.T", "edinet_code": "E02529"}
}

# --- 3. サイドバーの操作メニュー ---
st.sidebar.header("🎯 監視ターゲット")
selected_company = st.sidebar.selectbox(
    "投資動向をチェックしたい企業を選んでください", 
    list(TARGET_COMPANIES.keys())
)
ticker_symbol = TARGET_COMPANIES[selected_company]["ticker"]
edinet_code = TARGET_COMPANIES[selected_company]["edinet_code"]

# --- 4. EDINETダミーデータ取得 ---
@st.cache_data(ttl=3600) 
def get_edinet_documents(target_edinet_code):
    doc_list = []
    if target_edinet_code == "E04430":
        doc_list.append({
            "date": "2026-09-25",
            "title": "変更報告書（大量保有）: Ｎｏ．１(3562)",
            "submitter": "株式会社光通信"
        })
    return doc_list

# --- 5. ダッシュボードの画面表示 ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"📊 {selected_company} の株価推移（直近6ヶ月）")
    @st.cache_data 
    def load_stock_data(ticker):
        end_date = datetime.today()
        start_date = end_date - timedelta(days=180)
        df = yf.download(ticker, start=start_date, end=end_date)
        return df

    data = load_stock_data(ticker_symbol)
    if not data.empty:
        st.line_chart(data['Close'])
    else:
        st.warning("データが取得できませんでした。")

with col2:
    st.subheader("🚨 最新の検知アラート")
    st.caption("※金融庁EDINETより自動取得")
    
    docs = get_edinet_documents(edinet_code)
    if docs:
        for doc in docs:
            st.error(f"**検知日:** {doc['date']}\n\n**書類:** {doc['title']}")
    else:
        st.success("直近7日間で新しい投資の動きはありませんでした。")

st.divider()

# --- 6. AI分析結果の表示枠 ---
st.subheader("💡 投資意図のAI分析（プロ目線）")

# ▼▼▼ あなたの「AQ.」から始まる正しいAPIキーを貼り付けてください ▼▼▼
GOOGLE_API_KEY = 'あとでクラウドの金庫に設定します'
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

if GOOGLE_API_KEY != 'ここに取得したAPIキーを貼り付けてください':
    genai.configure(api_key=GOOGLE_API_KEY)
    
    if docs:
        st.write("🤖 最新モデル（Gemini 3.8 Flash）が分析中...")
        
        target_name = selected_company
        bought_stock = docs[0]['title']
        
        prompt = f"""
        あなたはプロの機関投資家です。
        {target_name} が、最近「{bought_stock}」に関する大量保有・変更報告書を出しました。
        
        以下の3点を、プロの目線で簡潔に（300文字程度で）分析してください。
        1. なぜ {target_name} はこの銘柄を買った（または買い増した）と推測できるか？
        2. この銘柄の投資家から見た強みは何か？
        3. この動きから、一般の個人投資家はどう参考にすべきか？
        """
        
        try:
            # あなたが発見した「最新バージョン 3.8」を指定！
            model = genai.GenerativeModel('gemini-3.8-flash')
            response = model.generate_content(prompt)
            st.success(f"【分析レポート】\n\n{response.text}")
                
        except Exception as e:
            st.error(f"AI分析中に通信エラーが発生しました: {e}")
else:
    st.error("⚠️ APIキーが設定されていません。")