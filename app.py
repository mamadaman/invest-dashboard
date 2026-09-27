import streamlit as st
import pandas as pd
import yfinance as yf
import google.generativeai as genai
import numpy as np

# ページ設定
st.set_page_config(page_title="プロの投資意図ダッシュボード弐号機", layout="wide")
st.title("🎯 プロの投資意図ダッシュボード 【弐号機】")

# APIキーの設定
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# テクニカル指標の計算関数
def calc_indicators(hist_series):
    if len(hist_series) < 25:
        return 0.0, 0.0, 0.0, "-", "-", "-"
    
    current = float(hist_series.iloc[-1])
    past_1d = float(hist_series.iloc[-2])
    past_7d = float(hist_series.iloc[-7]) if len(hist_series) >= 7 else float(hist_series.iloc[0])
    
    # 変化率
    daily_pct = ((current - past_1d) / past_1d) * 100
    weekly_pct = ((current - past_7d) / past_7d) * 100
    
    # 移動平均 (5日, 25日)
    ma5 = hist_series.rolling(5).mean().iloc[-1]
    ma25 = hist_series.rolling(25).mean().iloc[-1]
    
    if ma5 > ma25 and current > ma5:
        trend = "↗️ 上昇中"
    elif ma5 < ma25 and current < ma5:
        trend = "↘️ 下落途中"
    else:
        trend = "➡️ 横ばい"
        
    # RSI (14日)
    delta = hist_series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    if rsi <= 30:
        rsi_flag = "🧊 売られすぎ"
    elif rsi >= 70:
        rsi_flag = "🔥 買われすぎ"
    else:
        rsi_flag = "➖ 中立"
        
    # 急変動アラート
    if daily_pct <= -5.0:
        alert = "⚠️ 急落"
    elif daily_pct >= 5.0:
        alert = "🚀 暴騰"
    else:
        alert = ""
        
    return current, daily_pct, weekly_pct, trend, rsi_flag, alert

# データ読み込みと計算
@st.cache_data(ttl=3600)
def load_and_calculate():
    sheet_id = "1jGnNSeI-zUnArj8A7-Sivx5i9WTA9-As0Qe8QLWRljA"
    gid = "1224433232"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    try:
        df = pd.read_csv(csv_url).fillna("")
    except Exception:
        st.error("スプレッドシートの読み込みに失敗しました。")
        return pd.DataFrame()

    # スプレッドシートの銘柄に、日経平均とTOPIX連動ETFを追加
    tickers_list = ["^N225", "1306.T"] + [f"{str(code).strip()}.T" for code in df['銘柄コード']]
    
    with st.spinner("過去3ヶ月の株価データ（テクニカル計算用）を取得中..."):
        data = yf.download(tickers_list, period="3mo", group_by='ticker', progress=False)

    results = []
    
    # 1. 日経平均とTOPIXの処理（1・2行目用）
    macro_symbols = {"^N225": "日経平均株価", "1306.T": "TOPIX(連動ETF)"}
    for sym, name in macro_symbols.items():
        try:
            hist = data[sym]['Close'].dropna()
            current, d_pct, w_pct, trend, rsi_flag, alert = calc_indicators(hist)
            hist_str = ", ".join([str(round(p, 1)) for p in hist.tail(7).tolist()])
        except:
            current, d_pct, w_pct, trend, rsi_flag, alert, hist_str = 0, 0, 0, "-", "-", "-", "データなし"
            
        results.append({
            '★ 気になる': False,
            '銘柄コード': sym.replace(".T", ""),
            '企業名': name,
            'トレンド': trend,
            '過熱感(RSI)': rsi_flag,
            '急変動': alert,
            '現在値(円)': round(current, 1),
            '前日比(%)': round(d_pct, 1),
            '7日増減率(%)': round(w_pct, 1),
            '取得日': "-",
            '取得時の状況': "市場平均（ベンチマーク）",
            '直近7日推移': hist_str,
            '過去の履歴': "-"
        })

    # 2. 個別株の処理
    for _, row in df.iterrows():
        code = str(row['銘柄コード']).strip()
        sym = f"{code}.T"
        try:
            hist = data[sym]['Close'].dropna()
            current, d_pct, w_pct, trend, rsi_flag, alert = calc_indicators(hist)
            hist_str = ", ".join([str(round(p, 1)) for p in hist.tail(7).tolist()])
        except:
            current, d_pct, w_pct, trend, rsi_flag, alert, hist_str = 0, 0, 0, "-", "-", "-", "データなし"
            
        results.append({
            '★ 気になる': False,
            '銘柄コード': code,
            '企業名': row['企業名'],
            'トレンド': trend,
            '過熱感(RSI)': rsi_flag,
            '急変動': alert,
            '現在値(円)': round(current, 1),
            '前日比(%)': round(d_pct, 1),
            '7日増減率(%)': round(w_pct, 1),
            '取得日': row['取得日'],
            '取得時の状況': row['取得時の状況'],
            '直近7日推移': hist_str,
            '過去の履歴': row['履歴']
        })

    return pd.DataFrame(results)

# --- 画面上部：一覧表 ---
st.subheader("📊 プロの投資動向＆マクロ環境 一覧")
st.write("1・2行目の「市場平均」と個別株のトレンドを比較し、特有の下落（押し目）を探します。左端の「★」にチェックを入れて分析候補を絞り込めます。")

df_display = load_and_calculate()

if not df_display.empty:
    # 履歴列を非表示にして、編集可能なデータフレームとして表示（★列のみ編集可能）
    col_config = {col: st.column_config.Column(disabled=True) for col in df_display.columns if col != '★ 気になる'}
    
    edited_df = st.data_editor(
        df_display.drop(columns=['過去の履歴']), 
        hide_index=True, 
        column_config=col_config,
        use_container_width=True,
        height=500
    )

    # --- 画面下部：AI深掘り分析 ---
    st.divider()
    st.subheader("💡 AI深掘り分析（マクロ環境との連動性チェック）")
    
    # チェックを入れた銘柄があればそれを優先表示、なければマクロ以外の全銘柄
    selected_stars = edited_df[edited_df['★ 気になる'] == True]['企業名'].tolist()
    all_companies = edited_df[~edited_df['企業名'].isin(["日経平均株価", "TOPIX(連動ETF)"])]['企業名'].tolist()
    
    dropdown_options = selected_stars if len(selected_stars) > 0 else all_companies
    
    if len(selected_stars) > 0:
        st.info(f"★チェックした銘柄（{len(selected_stars)}件）のみをリストに表示しています。")
        
    selected_company = st.selectbox("分析したい企業を選択してください", dropdown_options)
    
    # 対象企業のデータ抽出
    target_row = df_display[df_display['企業名'] == selected_company].iloc[0]
    ticker_code = target_row['銘柄コード']
    ticker_symbol = f"{str(ticker_code).strip()}.T"
    
    # マクロ環境のデータ抽出（プロンプト用）
    nikkei_row = df_display[df_display['企業名'] == "日経平均株価"].iloc[0]
    topix_row = df_display[df_display['企業名'] == "TOPIX(連動ETF)"].iloc[0]
    
    # 履歴のアコーディオン表示
    with st.expander(f"📜 【{selected_company}】の過去の取得・売却履歴を見る"):
        history_text = str(target_row['過去の履歴'])
        if history_text and history_text != "-" and history_text != "nan":
            for line in history_text.split(" | "):
                st.write(f"・ {line}")
        else:
            st.write("過去の履歴データがありません。")

    if st.button("AI分析を実行する"):
        with st.spinner(f"{selected_company} の各種データを取得中..."):
            try:
                hist_1y = yf.Ticker(ticker_symbol).history(period="1y")
                if not hist_1y.empty:
                    st.write("📈 **過去1年間の株価推移**")
                    st.line_chart(hist_1y['Close'])
            except:
                st.warning("チャートデータが取得できませんでした。")

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

        cols = st.columns(3)
        cols[0].metric("PER", per_str)
        cols[1].metric("PBR", pbr_str)
        cols[2].metric("配当利回り", div_yield_str)
        
        prompt = f"""
        あなたは機関投資家や事業会社の動向を分析するプロの株式アナリストです。
        以下の企業について、プロが大量保有（買い増し）した意図と、現在の株価下落が「買い場」かどうかを分析してください。

        【市場全体（マクロ）の環境】
        日経平均株価: トレンド[{nikkei_row['トレンド']}] / 過熱感[{nikkei_row['過熱感(RSI)']}] / 7日増減[{nikkei_row['7日増減率(%)']}%]
        TOPIX: トレンド[{topix_row['トレンド']}] / 過熱感[{topix_row['過熱感(RSI)']}] / 7日増減[{topix_row['7日増減率(%)']}%]

        【対象銘柄（ミクロ）の状況】
        企業名: {target_row['企業名']} (コード: {ticker_code})
        取得時の状況: {target_row['取得時の状況']}
        現在のトレンド: [{target_row['トレンド']}]
        現在の過熱感: [{target_row['過熱感(RSI)']}]
        直近7日の増減率: {target_row['7日増減率(%)']}%
        
        【プロの過去の売買タイムライン】
        {target_row['過去の履歴']}

        【ファンダメンタル指標】
        PER: {per_str} / PBR: {pbr_str} / 配当利回り: {div_yield_str}

        以下の4点を簡潔に解説してください。
        1. 【マクロ・ミクロ比較】市場全体のトレンドと比較して、この銘柄の直近の動きは「連れ安」か、それとも「個別要因による独自の動き」か推測してください。
        2. 【プロの投資意図】過去のタイムラインも踏まえ、なぜプロはこの銘柄を取引しているか。
        3. 【指標評価】PER、PBR、配当利回りの観点から、現在の株価は「割安」か。
        4. 【総合投資判断】トレンドとRSI(過熱感)を踏まえ、今が押し目買いのチャンス（買い場）と言えそうか。
        """
        
        with st.spinner(f"{selected_company} の投資意図と相場環境をAIが分析中..."):
            try:
                # ユーザー指定モデル
                model = genai.GenerativeModel("gemini-3.8-flash")
                response = model.generate_content(prompt)
                st.success("分析完了")
                st.write(response.text)
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Quota" in error_msg:
                    st.warning("⚠️ APIの無料枠制限（1分間に5回まで）に達しました。約1分ほど待ってから、再度「AI分析を実行する」ボタンを押してください。")
                else:
                    st.error(f"AI分析中にエラーが発生しました。詳細: {e}")
