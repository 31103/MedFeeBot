# **システムパターン: MedFeeBot**

## **1. システムアーキテクチャ概要**

MedFeeBotは、サーバーレスアーキテクチャを採用し、Google Cloud Platform (GCP)
上で動作します。主要コンポーネントとその連携は以下の通りです。

```mermaid
graph LR
    subgraph Google Cloud
        Scheduler[Cloud Scheduler] -- triggers --> GCF[Cloud Functions (Python)]
        GCF -- reads/writes --> GCS[Cloud Storage Bucket/File]
        GCF -- reads secret --> SecretManager[Secret Manager]
        GCF -- sends logs --> Logging[Cloud Logging]
        GCF -- sends metrics --> Monitoring[Cloud Monitoring]
    end
    GCF -- fetches HTML --> MHLW[MHLW Website]
    GCF -- sends notification --> Slack[Slack Target Channel]
    GCF -- sends error alert --> SlackAdmin[Slack Admin Channel]
```

- **Cloud Scheduler:** 定期実行トリガー（デフォルトは1時間ごと）を提供し、Cloud
  Functionsを起動します。
- **Cloud Functions (第2世代, Python):**
  ボットの中核ロジックを実行します。厚生労働省サイトからHTMLを取得し、PDFリンクを解析、新規PDFを検知し、Slackへ通知します。
- **Cloud Storage (GCS):**
  検知済みのPDFファイルのURLリストを永続化するためのストレージとして利用します（JSON形式ファイルを想定）。
- **Secret Manager:** Slack APIトークンなどの機密情報を安全に保管します。
- **Cloud Logging:** 関数の実行ログやエラー情報を記録します。
- **Cloud Monitoring:** 関数のパフォーマンス監視やアラート設定に利用します。
- **外部サービス:**
  - **厚生労働省ウェブサイト (MHLW):** 監視対象のHTMLコンテンツを取得します。
  - **Slack:**
    検知結果の通知先およびエラー発生時の管理者への通知先として利用します。

## **2. 主要な技術的決定**

- **実行環境:** Google Cloud Functions (第2世代)
  - 理由:
    サーバーレスで運用負荷が低く、従量課金でコスト効率が良い。Pythonランタイムが利用可能。
- **開発言語:** Python (3.9以降)
  - 理由:
    豊富なライブラリ（Webスクレイピング、API連携）、GCPとの親和性、型アノテーションによる保守性向上。
- **永続化ストレージ:** Google Cloud Storage (GCS)
  - 理由: シンプルなファイルベースのデータ保存に適しており、Cloud
    Functionsからのアクセスが容易。低コスト。
- **機密情報管理:** Google Cloud Secret Manager
  - 理由: APIキーなどの機密情報を安全に管理するためのGCP標準サービス。Cloud
    Functionsから環境変数経由で安全に参照可能。
- **HTML解析:** Beautiful Soup 4 (または lxml)
  - 理由: Pythonで広く使われているHTML/XMLパーサーであり、柔軟な要素選択が可能。
- **HTTP通信:** requests ライブラリ
  - 理由: PythonにおけるHTTP通信のデファクトスタンダード。シンプルで使いやすい。
- **Slack連携:** slack\_sdk ライブラリ
  - 理由: Slack公式のPython SDKであり、API連携を容易にする。

## **3. 設計パターンとプラクティス**

- **環境変数による設定:**
  - 監視対象URLリスト
    (`TARGET_URLS`)、SlackチャンネルID、GCSバケット名、状態ファイル名
    (`KNOWN_URLS_FILE`, `LATEST_IDS_FILE`)
    などの主要な設定値は環境変数で管理します。
  - 機密情報 (Slack APIトークン) は Secret Manager 経由で環境変数に注入します
    (`SLACK_SECRET_ID`)。
- **設定駆動型処理分岐:**
  - `src/config.py` 内の `URL_CONFIGS` 辞書で、各監視対象URLに対する監視タイプ
    (`pdf` or `meeting`) と使用するパーサー関数をマッピングします。
  - `main.py`
    はこの設定を読み込み、URLごとに適切な処理フロー（パーサー実行、差分検知、通知）を実行します。これにより、新しいURLや監視タイプの追加が容易になります。
- **エラーハンドリング:**
  - `try-except`ブロックを用いて、ネットワークエラー、HTTPエラー、解析エラー、GCSアクセスエラーなどを捕捉します。
  - URLごとの処理でエラーが発生しても、他のURLの処理は継続します。
  - エラー発生時は詳細をLoggingに記録し、設定されていれば管理者Slackチャンネルへ通知します（Slack通知自体のエラーは除く）。
- **GCSアクセスエラーの分離:**
  - GCSからの状態**読み込み**失敗は、処理タイプに応じて致命的エラーとするか、空の状態として処理を継続するかを判断します（例:
    `load_known_urls` は致命的、`load_latest_meeting_ids` は空を返す）。
  - GCSへの状態**書き込み**失敗はログと管理者通知に留め、関数実行は継続します（次回の実行で状態が古くなる可能性がある）。
- **型アノテーション:**
  `typing`モジュールを活用し、コードの可読性と保守性を高めます。静的解析ツール(mypy)による検証も行います。
- **モジュール分割:** 機能ごとにモジュールを分割し（例: `fetcher.py`,
  `parser.py`, `notifier.py`, `storage.py`, `config.py`）、関心事を分離します。
- **Conventional Commits:** コミットメッセージの規約を統一します。
- **GitHub Flow:** シンプルなブランチ戦略を採用します。
- **セマンティックバージョニング (SemVer):**
  バージョン番号付けのルールを明確にします。

## **4. クリティカルな実装パス**

- **PDFリンク検知ロジック (`parser.py`):**
  - `<a>`タグの`href`属性を抽出。
  - 正規表現 (`\.pdf(\?.*)?$`)
    を使用し、`.pdf`で終わるリンクおよびクエリパラメータが付与されたPDFリンクを捕捉。
  - 相対パスを絶対URLに正しく変換 (`urllib.parse.urljoin`)。
  - 特定サイト向けパーサー (`extract_hospital_document_info`)
    では、日付やタイトルも同時に抽出。
- **会議情報抽出ロジック (`parser.py`):**
  - 特定のHTML構造（例: `table.m-tableFlex`）に依存したアドホックな実装
    (`extract_latest_chuikyo_meeting`)。
  - 会議回数、開催日、議題リスト、関連リンク（オプション）を抽出。
  - 必須情報が取得できない場合は `None` を返す。
- **状態管理と差分検知 (`storage.py`, `main.py`):**
  - **PDF検知:**
    - `load_known_urls`: GCS等から `{url: [pdf_url]}` 形式の辞書を読み込む。
    - `find_new_pdf_urls`: 特定の `target_url` について、現在のPDF
      URLセットと読み込んだ既知URLリストを比較し、新規PDF URLセットを返す。
    - `save_known_urls`: 更新された `{url: [pdf_url]}`
      形式の辞書全体をGCS等に保存する。
    - 初回実行時（対象URLのキーが存在しない場合）は、現在のPDFリストを保存し、通知は行わない。
  - **会議開催検知:**
    - `load_latest_meeting_ids`: GCS等から `{url: meeting_id}`
      形式の辞書を読み込む。
    - `main.py` 内: 特定の `target_url` について、今回解析した最新会議ID
      (`parsed_result['id']`) と読み込んだ前回ID (`previous_meeting_id`)
      を比較する。
    - `save_latest_meeting_ids`: IDが更新された場合、更新後の
      `{url: meeting_id}` 形式の辞書全体をGCS等に保存する。
    - 初回実行時（対象URLのキーが存在しない場合）は、現在の会議IDを保存し、通知を行う（初回から通知対象）。
- **通知処理 (`notifier.py`):**
  - `send_slack_notification` はペイロード
    (`{'type': ..., 'data': ..., 'source_url': ...}`) を受け取る。
  - `type` (`pdf` or `meeting`) に応じて、`data` の内容を解釈し、適切なBlock Kit
    JSONを生成するヘルパー関数 (`_build_pdf_notification_blocks`,
    `_build_meeting_notification_blocks`) を呼び出す。
- **エラー通知フロー:**
  - 一般的なエラー: Logging記録 + 管理者Slack通知。
  - GCS読み込みエラー (致命的な場合): Logging記録 + 管理者Slack通知 +
    **関数異常終了** (または該当URLの処理スキップ)。
  - GCS書き込みエラー: Logging記録 + 管理者Slack通知（関数は継続）。
  - Slack通知自体のエラー: Logging記録のみ。
