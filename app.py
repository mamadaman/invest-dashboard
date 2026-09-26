import streamlit as st
import pandas as pd
import yfinance as yf
import google.generativeai as genai
import time

# ページ設定
st.set_page_config(page_title="プロの投資意図ダッシュボード", layout="wide")
st.title("🎯 プロの投資意図ダッシュボード")

# APIキーの設定（秘密の金庫から読み込み）
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# --- 1. エクセルデータの読み込みと株価の自動計算（キャッシュで高速化） ---
@st.cache_data(ttl=3600) # 1時間に1回だけ読み込み直す（動作を軽くするため）
def load_and_calculate():
    # エクセルの読み込み
    try:
        df = pd.read_excel("target_list.xlsx")
    except Exception as e:
        st.error("エクセルファイル（target_list.xlsx）が見つからないか、読み込めません。")
        return pd.DataFrame()

    # yfinance用に銘柄コードを「1234.T」の形に変換
    tickers = [f"{str(code).strip()}.T" for code in df['銘柄コード']]
    
    # 過去7日分のデータを一括取得
    with st.spinner("最新の株価データを取得中..."):
        data = yf.download(tickers, period="7d", group_by='ticker', progress=False)

    current_prices, diff_amounts, diff_percents = [], [], []

    # 各銘柄の増減を計算
    for code in df['銘柄コード']:
        ticker = f"{code}.T"
        try:
            # 終値（Close）のデータを取得
            if len(tickers) == 1:
                hist = data['Close'].dropna()
            else:
                hist = data[ticker]['Close'].dropna()
                
            if len(hist) >= 2:
                current = float(hist.iloc[-1])
                past = float(hist.iloc[0]) # 約7日前の価格
                diff = current - past
                pct = (diff / past) * 100
            else:
                current, diff, pct = 0.0, 0.0, 0.0
        except:
            current, diff, pct = 0.0, 0.0, 0.0
            
        current_prices.append(round(current, 1))
        diff_amounts.append(round(diff, 1))
        diff_percents.append(round(pct, 2))

    # 計算結果をデータフレームに追加
    df['現在値(円)'] = current_prices
    df['7日増減額'] = diff_amounts
    df['7日増減率(%)'] = diff_percents

    # 画面表示用に列の順番を整理
    display_df = df[['銘柄コード', '企業名', '取得日', '取得時の状況', '現在値(円)', '7日増減額', '7日増減率(%)']]
    return display_df

# --- 2. 画面上部：一覧表の表示 ---
st.subheader("📊 プロの投資動向一覧")
st.write("IR BANKの取得履歴と直近1週間の株価変動（一時的な下落・押し目を探す）")

df_display = load_and_calculate()

if not df_display.empty:
    # データフレームを画面に表示（列をクリックして並べ替え可能）
    st.dataframe(
        df_display, 
        use_container_width=True,
        hide_index=True
    )

    # --- 3. 画面下部：AI深掘り分析 ---
    st.divider()
    st.subheader("💡 気になる銘柄をAIで深掘り（プロ視点）")
    
    # セレクトボックスで表の中から銘柄を選択
    company_options = df_display['企業名'].tolist()
    selected_company = st.selectbox("分析したい企業を選択してください", company_options)
    
    if st.button("AI分析を実行する"):
        # 選択された企業のデータを抽出
        target_row = df_display[df_display['企業名'] == selected_company].iloc[0]
        
        # AIへ投げる指示書（プロンプト）
        prompt = f"""
        あなたは機関投資家や事業会社の動向を分析するプロの株式アナリストです。
        以下の企業について、プロが大量保有（買い増し）した意図と、現在の株価下落が「買い場」かどうかを分析してください。

        【対象銘柄】
        企業名: {target_row['企業名']} (コード: {target_row['銘柄コード']})
        プロの取得状況: {target_row['取得時の状況']}
        直近7日の株価増減率: {target_row['7日増減率(%)']}%

        以下の3点を簡潔に解説してください。
        1. 【プロの投資意図】なぜ事業会社やプロはこの銘柄を買ったと推測されるか（純投資か、シナジー狙いか等）
        2. 【下落の要因】もし直近で株価が下落している場合、それは企業特有の致命的な悪材料か、市場全体のノイズか
        3. 【投資判断】ファンダメンタルズが崩れていない一時的な下落（押し目）として、個人投資家も追随して買うべきか
        """
        
        with st.spinner(f"{selected_company} の投資意図をAIが分析中..."):
            try:
                response = model.generate_content(prompt)
                st.success("分析完了")
                st.write(response.text)
            except Exception as e:
                st.error("AI分析中にエラーが発生しました。")
