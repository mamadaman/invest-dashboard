import streamlit as st
import pandas as pd
import yfinance as yf
import google.generativeai as genai

# ページ設定
st.set_page_config(page_title="プロの投資意図ダッシュボード", layout="wide")
st.title("🎯 プロの投資意図ダッシュボード")

# APIキーの設定
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
# 最も賢くて安定している最新モデルを指定
model = genai.GenerativeModel("gemini-1.5-flash")

# --- 1. エクセルデータの読み込みと株価の自動計算 ---
@st.cache_data(ttl=3600)
def load_and_calculate():
    try:
        df = pd.read_excel("target_list.xlsx")
    except Exception as e:
        st.error("エクセルファイルが見つかりません。")
        return pd.DataFrame()

    tickers = [f"{str(code).strip()}.T" for code in df['銘柄コード']]
    
    with st.spinner("最新の株価データを取得中..."):
        data = yf.download(tickers, period="7d", group_by='ticker', progress=False)

    current_prices, diff_amounts, diff_percents, history_strings = [], [], [], []

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
                hist_prices = [str(round(p, 1)) for p in hist.tolist()]
                hist_str = ", ".join(hist_prices)
            else:
                current, diff, pct, hist_str = 0.0, 0.0, 0.0, "データなし"
        except:
            current, diff, pct, hist_str = 0.0, 0.0, 0.0, "データなし"
            
        current_prices.append(round(current, 1))
        diff_amounts.append(round(diff, 1))
        diff_percents.append(round(pct, 2))
        history_strings.append(hist_str)

    # ズレを防ぐため、新しく綺麗な表を作り直す
    display_df = pd.DataFrame({
        '銘柄コード': df['銘柄コード'],
        '企業名': df['企業名'],
        '取得日': pd.to_datetime(df['取得日']).dt.strftime('%Y-%m-%d'),
        '取得時の状況': df['取得時の状況'],
        '現在値(円)': current_prices,
        '7日増減額': diff_amounts,
        '7日増減率(%)': diff_percents,
        '直近の株価推移': history_strings
    })
    
    # 銘柄コードを見出し（インデックス）に設定して列ズレを完全に防ぐ
    display_df = display_df.set_index('銘柄コード')
    return display_df

# --- 2. 画面上部：一覧表の表示 ---
st.subheader("📊 プロの投資動向一覧")
st.write("IR BANKの取得履歴と直近1週間の株価変動（一時的な下落・押し目を探す）")

df_display = load_and_calculate()

if not df_display.empty:
    # 修正した綺麗な表を表示
    st.dataframe(df_display, use_container_width=True)

    # --- 3. 画面下部：AI深掘り分析 ---
    st.divider()
    st.subheader("💡 気になる銘柄をAIで深掘り（プロ視点）")
    
    company_options = df_display['企業名'].tolist()
    selected_company = st.selectbox("分析したい企業を選択してください", company_options)
    
    if st.button("AI分析を実行する"):
        target_row = df_display[df_display['企業名'] == selected_company].iloc[0]
        ticker_code = target_row.name # インデックスの銘柄コードを取得
        ticker_symbol = f"{str(ticker_code).strip()}.T"
        
        # --- 1年間のチャートとプロの指標を取得 ---
        with st.spinner(f"{selected_company} の1年間チャートとプロの指標を取得中..."):
            # チャート表示
            try:
                hist_1y = yf.Ticker(ticker_symbol).history(period="1y")
                if not hist_1y.empty:
                    st.write("📈 **過去1年間の株価推移**")
                    st.line_chart(hist_1y['Close'])
            except:
                st.warning("1年間のチャートデータが取得できませんでした。")

            # プロの指標（PER, PBR, 配当利回り）
            try:
                info = yf.Ticker(ticker_symbol).info
                per = info.get('trailingPE', info.get('forwardPE', 'データなし'))
                pbr = info.get('priceToBook', 'データなし')
                div_yield = info.get('dividendYield', 'データなし')
                
                per_str = f"{round(per, 1)}倍" if isinstance(per, (int, float)) else "データなし"
                pbr_str = f"{round(pbr, 2)}倍" if isinstance(pbr, (int, float)) else "データなし"
                div_yield_str = f"{round(div_yield * 100, 2)}%" if isinstance(div_yield, (int, float)) else "データなし"
            except:
                per_str, pbr_str, div_yield_str = "データなし", "データなし", "データなし"

        # 指標を画面に美しく並べて表示
        cols = st.columns(3)
        cols[0].metric("PER (株価収益率)", per_str, help="15倍以下で割安の目安")
        cols[1].metric("PBR (株価純資産倍率)", pbr_str, help="1倍以下で割安の目安")
        cols[2].metric("配当利回り", div_yield_str, help="3%以上で高配当の目安")
        
        # --- AIへのプロンプト（指示書） ---
        prompt = f"""
        あなたは機関投資家や事業会社の動向を分析するプロの株式アナリストです。
        以下の企業について、プロが大量保有（買い増し）した意図と、現在の株価下落が「買い場」かどうかを分析してください。

        【対象銘柄】
        企業名: {target_row['企業名']} (コード: {ticker_code})
        プロの取得状況: {target_row['取得時の状況']}
        直近7日の株価増減率: {target_row['7日増減率(%)']}%

        【ファンダメンタル指標】
        PER: {per_str}
        PBR: {pbr_str}
        配当利回り: {div_yield_str}

        以下の4点を簡潔に解説してください。
        1. 【プロの投資意図】なぜ事業会社やプロはこの銘柄を買ったと推測されるか（純投資か、シナジー狙いか等）
        2. 【指標評価】PER、PBR、配当利回りの観点から、現在の株価は「割安（買い）」か「割高（据え置き）」か、プロの視点で明確に評価してください。
        3. 【下落の要因】もし直近で株価が下落している場合、それは企業特有の致命的な悪材料か、市場全体のノイズか
        4. 【投資判断】ファンダメンタルズが崩れていない一時的な下落（押し目）として、個人投資家も追随して買うべきか
        """
        
        with st.spinner(f"{selected_company} の投資意図をAIが分析中..."):
            try:
                response = model.generate_content(prompt)
                st.success("分析完了")
                st.write(response.text)
            except Exception as e:
                st.error(f"AI分析中にエラーが発生しました。詳細: {e}")
