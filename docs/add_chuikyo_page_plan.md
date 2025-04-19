# 修正計画 v3: 複数URL監視対応 (PDF検知 + 会議開催検知)

## 概要

既存の監視対象URL（PDF検知）に加え、厚生労働省の「中央社会保険医療協議会総会」ページ
(`https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html`)
を新たな監視対象として追加します。この新しいページでは、**新規会議の開催を検知してその内容を通知する**ことを目的とします。

この計画では、異なる目的（PDF検知、会議開催検知）を持つ複数のURLを並行して監視できるようにシステムを拡張します。中医協ページの解析ロジックは、当該ページの構造に特化した**アドホックな実装**となります。

## ステップ

1. **パーサーの修正・追加:**
   - **ファイル:** `src/parser.py`
   - **内容:**
     - **新規追加 (アドホック):**
       `extract_latest_chuikyo_meeting(html_content: str) -> dict | None`
       関数を追加。
       - 入力されたHTMLコンテンツを `BeautifulSoup` で解析します。
       - `<table class="m-tableFlex">` 内の最初の `<tr>` (最新会議の行)
         を特定します。見つからない場合は `None` を返します。
       - 以下の情報をセレクタ等で抽出します。必須情報（会議回数、開催日、議題）が取得できない場合はエラーログを出力し
         `None` を返します。
         - **会議回数 (識別子):** `td.m-table__highlight` (最初のtd)
           のテキスト。取得後、前後の空白を除去します (例: `第606回`)。
         - **開催日:** `td.m-table__highlight.m-table__nowrap` (2番目のtd)
           のテキスト。取得後、前後の空白を除去します。
         - **議題リスト:** 3番目の `td` 内の `ol.m-listMarker > li`
           をすべて取得し、各 `li`
           要素のテキストをリストとして抽出します。各議題テキストの前後の空白を除去します。
         - **議事録/要旨リンク (オプション):** 4番目の `td` 内の `a.m-link`
           が存在すれば、その `href` 属性値 (絶対URLに変換)
           とテキストを取得します。存在しない場合は `None`
           または空文字列とします。
         - **資料リンク (オプション):** 5番目の `td` 内の `a.m-link`
           が存在すれば、その `href` 属性値 (絶対URLに変換)
           とテキストを取得します。存在しない場合は `None`
           または空文字列とします。 (`urljoin` を使用して絶対URLに変換)
       - 抽出した情報を辞書形式で返却します。キー名は一貫性を持たせます。
         ```python
         # 返却値の例
         {
             'id': '第606回',
             'date': '2025年4月9日（令和7年4月9日）',
             'topics': [
                 '1 部会・小委員会に属する委員の指名等について',
                 '2 医療機器の保険適用について',
                 # ... 他の議題
             ],
             'minutes_url': 'https://www.mhlw.go.jp/stf/newpage_56730.html', # 例 (存在する場合)
             'minutes_text': '議事録', # 例 (存在する場合)
             'materials_url': 'https://www.mhlw.go.jp/stf/newpage_56712.html', # 例 (存在する場合)
             'materials_text': '資料' # 例 (存在する場合)
         }
         ```
     - **既存維持:** 既存のPDF検知用パーサー (`extract_hospital_document_info`
       や `extract_pdf_links`) は変更せずに維持します。

2. **差分検知ロジックの拡張:**
   - **ファイル:** `src/storage.py`
   - **内容:**
     - **状態管理ファイルの明確化:**
       - `known_urls.json`: 既存のPDF検知対象URLについて、検知済みのPDF
         URLリストを保存します。(`{url: [pdf_url1, pdf_url2, ...]}`)
       - `latest_ids.json`:
         会議開催検知対象URLについて、最後に検知した会議の識別子（会議回数）を保存します。(`{url: meeting_id}`)
     - **新規追加:** 会議開催検知用のストレージ操作関数を追加。
       - `save_latest_meeting_ids(meeting_ids: dict[str, str])`:
         最新会議IDの辞書をGCS上の `latest_ids.json` にJSON形式で保存する。
       - `load_latest_meeting_ids() -> dict[str, str]`: GCS上の
         `latest_ids.json`
         から会議IDの辞書を読み込む。ファイルが存在しない、または不正な形式の場合は空の辞書を返し、エラーログを出力する。
     - **既存維持:** 既存のPDF検知用ストレージ操作関数 (`save_known_urls`,
       `load_known_urls`) は変更せずに維持します。

3. **設定の更新と拡張:**
   - **ファイル:** `.env` (ローカル), Cloud Functions 環境変数 (クラウド),
     `src/config.py`
   - **内容:**
     - **環境変数:**
       - `TARGET_URLS`:
         カンマ区切りで監視対象URLを複数指定します。URLの順序は保持されます。
         - 例:
           `TARGET_URLS=https://www.hospital.or.jp/site/ministry/,https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html`
     - **`src/config.py`:**
       - `TARGET_URLS` 環境変数を読み込み、URLのリスト (`List[str]`)
         として保持します。空の要素は除外します。
       - **URL設定辞書 (`URL_CONFIGS`)**:
         各URLに対する監視タイプとパーサー関数をマッピングします。キーはURL文字列、値は設定辞書です。
         ```python
         # 例: src/config.py 内
         import os
         from typing import List, Dict, Callable, Any
         from src import parser # parser.py をインポート
         from urllib.parse import urlparse

         # 環境変数からURLリストを取得
         target_urls_str = os.getenv('TARGET_URLS', '')
         TARGET_URLS: List[str] = [url.strip() for url in target_urls_str.split(',') if url.strip()]

         # URLごとの設定を定義
         # キー: URL文字列
         # 値: { "type": "pdf" | "meeting", "parser": Callable[[str], Any] }
         URL_CONFIGS: Dict[str, Dict[str, Any]] = {
             "https://www.hospital.or.jp/site/ministry/": {
                 "type": "pdf",
                 "parser": parser.extract_hospital_document_info # PDF情報リストを返す関数
             },
             "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html": {
                 "type": "meeting",
                 "parser": parser.extract_latest_chuikyo_meeting # 会議情報辞書 or None を返す関数
             }
             # 他のURL設定も必要に応じて追加
         }

         # 設定されていないURLに対する警告
         CONFIGURED_URLS = list(URL_CONFIGS.keys())
         for url in TARGET_URLS:
             if url not in CONFIGURED_URLS:
                 # logger などで警告を出す
                 print(f"Warning: URL '{url}' is in TARGET_URLS but not configured in URL_CONFIGS.")

         # GCS設定などもここに記述 (既存)
         GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
         KNOWN_URLS_FILE = 'known_urls.json'
         LATEST_IDS_FILE = 'latest_ids.json' # 新しい状態ファイル名
         # ... 他の設定 ...
         ```
       - `load_config`
         関数などでこれらの設定を読み込み、アプリケーション全体で利用できるようにします。

4. **メインロジックの修正:**
   - **ファイル:** `src/main.py` (主に `run_check` 関数、または新設する
     `process_url` 関数)
   - **内容:**
     - `run_check` 関数 (または `main_gcf` から呼び出されるメイン処理関数)
       内で、`config.TARGET_URLS` リストをループ処理します。
     - ループ内で、現在の `url` に対応する設定を `config.URL_CONFIGS`
       から取得します。設定が存在しない場合は警告ログを出力し、次のURLへ進みます。
     - **HTML取得:** `fetcher.fetch_html(url)`
       を呼び出してHTMLコンテンツを取得します。取得に失敗した場合はエラーログを出力し、次のURLへ進みます。
     - **パーサー実行:** 取得した設定の `parser`
       関数を呼び出し、HTMLコンテンツを渡して解析結果を取得します。パーサーが
       `None`
       を返した場合（解析失敗など）はエラーログを出力し、次のURLへ進みます。
     - **タイプ別処理分岐:** 設定の `type` に基づいて処理を分岐します。
       - **`type` が `pdf` の場合:**
         1. 解析結果 (ドキュメント情報リスト) を受け取ります。
         2. `storage.load_known_urls()` で既知URL辞書 (`{url: [pdf_url]}`)
            を取得します。
         3. 現在の `url` に対応する既知PDF URLリストを取得します。
         4. 解析結果のURLリストと既知PDF URLリストを比較し、新規PDF
            URLを特定します。
         5. 新規PDF
            URLがあれば、対応するドキュメント情報（タイトル等も含む）を整形し、`notifier.send_slack_notification`
            を呼び出して通知します。通知データには `type: 'pdf'`
            のような情報を含め、Notifier側で区別できるようにします。
         6. `storage.save_known_urls()` で、現在の `url` の既知PDF
            URLリストを更新した辞書全体を保存します。
       - **`type` が `meeting` の場合:**
         1. 解析結果 (最新会議情報辞書) を受け取ります。
         2. `storage.load_latest_meeting_ids()` で前回会議ID辞書
            (`{url: meeting_id}`) を取得します。
         3. 現在の `url` に対応する前回会議ID (`previous_meeting_id`)
            を取得します（存在しない場合は `None`）。
         4. 解析結果から最新会議ID (`latest_meeting_id = result['id']`)
            を取得します。
         5. `latest_meeting_id != previous_meeting_id`
            の場合、「新規会議開催」と判断します。
         6. 新規会議の場合、解析結果の会議情報全体を
            `notifier.send_slack_notification`
            に渡して通知します。通知データには `type: 'meeting'`
            のような情報を含めます。
         7. `storage.save_latest_meeting_ids()` で、現在の `url` の会議IDを
            `latest_meeting_id` に更新した辞書全体を保存します。

5. **通知機能の調整:**
   - **ファイル:** `src/notifier.py`
   - **内容:**
     - `send_slack_notification(data: Any)`
       関数の引数を汎用的にし、渡されたデータのタイプ (`pdf` または `meeting`)
       を判別して適切なメッセージを生成するようにします。`main.py`
       から渡されるデータに `type` キーを含めるか、データ構造で判別します。
     - **会議情報用メッセージ生成ロジック:**
       - 受け取った会議情報辞書 (`data`)
         から必要な情報（会議回数、開催日、議題リスト、リンク）を取り出します。
       - Block Kit JSONテンプレートに変数を埋め込みます。
       - 議題リストは改行区切りの文字列に整形します。
       - 資料・議事録リンクが存在する場合のみ、`actions`
         ブロックに対応するボタン要素を追加します。
     - **Slack通知例 (第606回中医協が新規検知された場合):**
       ````json
       // notifier.py が Slack API に送信するペイロードの例
       {
         "channel": "#your-channel-id", // 設定から取得
         "blocks": [
           {
             "type": "header",
             "text": {
               "type": "plain_text",
               "text": ":mega: 新しい中央社会保険医療協議会が開催されました",
               "emoji": true
             }
           },
           {
             "type": "section",
             "fields": [
               {
                 "type": "mrkdwn",
                 "text": "*会議名:*\n中央社会保険医療協議会"
               },
               { "type": "mrkdwn", "text": "*回数:*\n第606回" },
               {
                 "type": "mrkdwn",
                 "text": "*開催日:*\n2025年4月9日（令和7年4月9日）"
               }
             ]
           },
           {
             "type": "section",
             "text": {
               "type": "mrkdwn",
               "text": "*議題:*\n```\n1 部会・小委員会に属する委員の指名等について\n2 医療機器の保険適用について\n3 医薬品の新規薬価収載について\n4 DPC における高額な新規の医薬品等への対応について\n5 在宅自己注射について\n6 DPC 対象病院の退出に係る報告について\n7 令和８年度診療報酬改定、薬価改定の議論の進め方について\n8 選定療養に導入すべき事例等に関する提案・意見募集について\n```"
             }
           },
           {
             "type": "divider"
           },
           {
             "type": "actions",
             "elements": [
               { // 資料リンクが存在する場合
                 "type": "button",
                 "text": {
                   "type": "plain_text",
                   "text": "資料",
                   "emoji": true
                 },
                 "url": "https://www.mhlw.go.jp/stf/newpage_56712.html"
               }
               // 議事録リンクはまだないのでボタンは表示されない
             ]
           }
         ]
       }
       ````
     - 既存のPDF通知メッセージ生成ロジックは維持します。

6. **テストの追加・更新:**
   - **ファイル:** `tests/test_parser.py`, `tests/test_storage.py`,
     `tests/test_main.py` (必要なら作成), `tests/test_notifier.py`,
     `tests/test_integration.py`, etc.
   - **内容:** (変更なし、v2計画の詳細化を反映)
     - `test_parser.py`: `extract_latest_chuikyo_meeting`
       の単体テスト（正常系、異常系、HTML構造変化への耐性テスト含む）。
     - `test_storage.py`: `latest_ids.json` 関連関数の単体テスト。
     - `test_config.py`: `TARGET_URLS` と `URL_CONFIGS` の読み込みテスト。
     - `test_main.py` (または `test_integration.py`): `run_check` (または
       `process_url`)
       のテスト。URLタイプ別分岐、差分検知ロジック（新規/更新/変更なし）、エラーハンドリング（設定なしURL、fetch失敗、parse失敗）をテスト。
     - `test_notifier.py`: 会議情報用Block Kit生成テスト。PDF通知テストは維持。
     - `test_integration.py`:
       複数URL（pdf/meeting混在）シナリオでのE2E（モック使用）テスト。

7. **ドキュメント更新:**
   - **ファイル:** `README.md`, `memory-bank/activeContext.md`,
     `memory-bank/systemPatterns.md`
   - **内容:**
     - `README.md`:
       - 監視対象URLと目的（PDF検知/会議開催検知）を明確に記載。
       - 設定方法 (`TARGET_URLS`) を更新。
       - 開発者向けに `URL_CONFIGS` の構造と役割を説明。
     - `memory-bank/activeContext.md`:
       - 「現在のフォーカス」「次のステップ」「アクティブな決定事項」に今回の詳細化内容を反映。
     - `memory-bank/systemPatterns.md`:
       - 「設計パターンとプラクティス」に `URL_CONFIGS`
         による設定駆動型処理分岐を追加。
       - 「クリティカルな実装パス」に2種類の状態管理 (`known_urls.json`,
         `latest_ids.json`) とそれぞれの更新ロジックを明記。

## 修正計画 v3 のフロー図 (変更なし)

```mermaid
graph TD
    A[開始: 複数URL監視要求<br>(PDF検知 + 会議開催検知)] --> B(設定読み込み<br>TARGET_URLS, URL_CONFIGS);
    B --> C(URLリストをループ);
    C --> D{URL設定取得<br>(URL_CONFIGS)};
    D -- 設定あり --> E{HTML取得};
    D -- 設定なし --> C;
    E -- 成功 --> F{パーサー関数<br>取得 (設定から)};
    E -- 失敗 --> C;
    F --> G[パーサー実行];
    G -- 成功 --> H{監視タイプは?<br>(設定から)};
    G -- 失敗 --> C;
    H -- meeting --> I[会議情報取得<br>(ID, 日付, 議題...)];
    H -- pdf --> J[ドキュメント情報取得<br>(タイトル, URL...)];
    I --> K[前回会議ID<br>取得 (GCS: latest_ids.json)];
    J --> L[既知URLリスト<br>取得 (GCS: known_urls.json)];
    K --> M{ID比較<br>差分あり?};
    L --> N{URL比較<br>新規あり?};
    M -- Yes --> O[会議情報整形];
    N -- Yes --> P[新規PDF情報整形];
    O --> Q(Slack通知);
    P --> Q;
    M -- Yes --> R[会議ID更新<br>(GCS: latest_ids.json)];
    N -- Yes --> S[既知URL更新<br>(GCS: known_urls.json)];
    M -- No --> T(次のURLへ or 終了);
    N -- No --> T;
    Q -- 通知成功 --> R;
    Q -- 通知成功 --> S;
    Q -- 通知失敗 --> T; // 通知失敗してもID/URLは更新しない方が安全か？要検討
    R --> T;
    S --> T;
```
