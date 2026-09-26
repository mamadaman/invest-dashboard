import streamlit as st
import pandas as pd
import yfinance as yf
import google.generativeai as genai

# ページ設定
st.set_page_config(page_title="プロの投資意図ダッシュボード", layout="wide")
st.title("🎯 プロの投資意図ダッシュボード")

# APIキーの設定（秘密の金庫から読み込み）
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# --- 1. エクセルデータの読み込みと株価の自動計算 ---
@st.cache_data(ttl=3600)
def load_and_calculate():
    try:
        df = pd.read_excel("target_list.xlsx")
    except Exception as e:
        st.error("エクセルファイル（target_list.xlsx）が見つからないか、読み込めません。")
        return pd.DataFrame()

    tickers = [f"{str(code).strip()}.T" for code in df['銘柄コード']]
    
    with st.spinner("最新の株価データを取得中..."):
        data = yf.download(tickers, period="7d", group_by='ticker', progress=False)

    current_prices, diff_amounts, diff_percents, histories = [], [], [], []

    for code in df['銘柄コード']:
        ticker = f"{code}.T"
        try:
            if len(tickers) == 1:
                hist = data['Close'].dropna()
            else:
                hist = data[ticker]['Close'].dropna()
                
            if len(hist) >= 2:
                current = float(hist.iloc[-1])
                past = float(hist.iloc[0])
                diff = current - past
                pct = (diff / past) * 100
                # 7日間の日々の価格をリストにまとめる（ミニグラフ用）
                hist_list = hist.tolist() 
            else:
                current, diff, pct, hist_list = 0.0, 0.0, 0.0, []
        except:
            current, diff, pct, hist_list = 0.0, 0.0, 0.0, []
            
        current_prices.append(round(current, 1))
        diff_amounts.append(round(diff, 1))
        diff_percents.append(round(pct, 2))
        histories.append(hist_list)

    df['現在値(円)'] = current_prices
    df['7日増減額'] = diff_amounts
    df['7日増減率(%)'] = diff_percents
    df['7日間の推移'] = histories # ミニグラフ用のデータを追加

    # 取得日の 00:00:00 を消して日付だけにする
    df['取得日'] = pd.to_datetime(df['取得日']).dt.strftime('%Y-%m-%d')

    display_df = df[['銘柄コード', '企業名', '取得日', '取得時の状況', '現在値(円)', '7日増減額', '7日増減率(%)', '7日間の推移']]
    return display_df

# --- 2. 画面上部：一覧表の表示 ---
st.subheader("📊 プロの投資動向一覧")
st.write("IR BANKの取得履歴と直近1週間の株価変動（一時的な下落・押し目を探す）")

df_display = load_and_calculate()

if not df_display.empty:
    # 表の中にミニグラフを表示する設定を追加
    st.dataframe(
        df_display, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "7日間の推移": st.column_config.LineChartColumn(
                "7日間の推移",
                help="直近7日間の株価の動き"
            )
        }
    )

    # --- 3. 画面下部：AI深掘り分析 ---
    st.divider()
    st.subheader("💡 気になる銘柄をAIで深掘り（プロ視点）")
    
    company_options = df_display['企業名'].tolist()
    selected_company = st.selectbox("分析したい企業を選択してください", company_options)
    
    if st.button("AI分析を実行する"):
        target_row = df_display[df_display['企業名'] == selected_company].iloc[0]
        
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
                # エラーの原因を具体的に画面に出力させる
                st.error(f"AI分析中にエラーが発生しました。詳細: {e}")
