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
    except Exception as e:
        st.error(f"スプレッドシートの読み込みに失敗しました。詳細: {e}")
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
    st.subheader("💡 AI深掘り分析（事業の強み・財務・マクロ環境）")
    
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
            except Exception as e:
                st.warning(f"チャートデータの取得に失敗しました: {e}")

            try:
                info = yf.Ticker(ticker_symbol).info
                per = info.get('trailingPE', info.get('forwardPE', 'データなし'))
                pbr = info.get('priceToBook', 'データなし')
                div_yield = info.get('dividendYield', 'データなし')
                
                per_str = f"{round(per, 1)}倍" if isinstance(per, (int, float)) else "データなし"
                pbr_str = f"{round(pbr, 2)}倍" if isinstance(pbr, (int, float)) else "データなし"
                
                # --- [修正箇所] 配当利回りの計算バグを修正 ---
                if isinstance(div_yield, (int, float)):
                    # yfinanceが0.025(小数)で返す場合と、2.5(%)で返す場合の両方に対応
                    dy = div_yield * 100 if div_yield < 1 else div_yield
                    div_yield_str = f"{round(dy, 2)}%"
                else:
                    div_yield_str = "データなし"
                # ---------------------------------------------
            except Exception as e:
                st.warning(f"Yahoo Financeからの指標取得エラー: {e}")
                per_str, pbr_str, div_yield_str = "データなし", "データなし", "データなし"

        cols = st.columns(3)
        cols[0].metric("PER", per_str)
        cols[1].metric("PBR", pbr_str)
        cols[2].metric("配当利回り", div_yield_str)
        
        prompt = f"""
        あなたは機関投資家や事業会社（特に光通信のような長期・安定志向のバリュー投資家）の動向を分析するプロの株式アナリストです。
        以下の企業について、プロが大量保有（買い増し）した意図と、現在の株価下落が「買い場」かどうかを多角的に分析してください。

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

        プロの投資家が「安定した視点」でこの銘柄を選んでいるという前提のもと、以下の5点を深掘りして解説してください。
        
        1. 【企業の競争優位性と将来性】この企業が展開するビジネスや商品・サービスの中で、他社を凌駕する強み（経済的な堀/モート）は何か。また、どの事業に勢いや先見性（将来の成長ドライバー）があるか。
        2. 【財務・事業の安定性】PER、PBR、配当利回りに加え、プロが必ず評価するであろう「事業の底堅さ」「財務の健全性」「キャッシュ創出力」の観点から、この企業がどれほど手堅いと推測されるか。
        3. 【マクロ・ミクロ比較】市場全体のトレンドと比較して、この銘柄の直近の株価推移は「市場全体の連れ安」か、それとも「個別要因による独自の動き」か。
        4. 【プロの投資意図】企業の強み、財務の安定性、過去の売買タイムラインを総合し、なぜ光通信のようなプロはこの銘柄を「長期視点で買い集めている」と考えられるか。
        5. 【総合投資判断】トレンドとRSI(過熱感)を踏まえ、個人投資家にとっても今が「絶好の押し目買いのチャンス（買い場）」と言えそうか。
        """
        
        with st.spinner(f"{selected_company} の事業内容と相場環境をAIが徹底分析中..."):
            try:
                model = genai.GenerativeModel("gemini-3.8-flash")
                response = model.generate_content(prompt)
                st.success("分析完了")
                st.write(response.text)
            except Exception as e:
                st.error(f"🔴 AIエラー詳細: {str(e)}")
