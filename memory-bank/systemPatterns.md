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
  監視URL、SlackチャンネルID、GCSバケット/ファイルパスなどの設定値は環境変数で管理し、デプロイ環境ごとに変更可能にします。機密情報はSecret
  Manager経由で環境変数に注入します。
- **エラーハンドリング:**
  `try-except`ブロックを用いて、ネットワークエラー、HTTPエラー、解析エラーなどを捕捉し、処理の継続または安全な終了を保証します。エラー発生時は詳細をLoggingに記録し、管理者Slackチャンネルへ通知します（Slack通知失敗時はLoggingのみ）。
- **GCSアクセスエラーの分離:**
  GCSからの**読み込み**失敗は致命的エラーとして関数を異常終了させます。**書き込み**失敗はログと管理者通知に留め、関数実行は継続します（次回再通知の可能性あり）。
- **型アノテーション:**
  `typing`モジュールを活用し、コードの可読性と保守性を高めます。静的解析ツール(mypy)による検証も行います。
- **モジュール分割:** 機能ごとにモジュールを分割し（例: `fetcher.py`,
  `parser.py`, `notifier.py`, `storage.py`, `config.py`）、関心事を分離します。
- **Conventional Commits:**
  コミットメッセージの規約を統一し、変更履歴の自動生成や意図の明確化を図ります。
- **GitHub Flow:**
  シンプルなブランチ戦略を採用し、迅速な開発とデプロイを目指します。
- **セマンティックバージョニング (SemVer):**
  バージョン番号付けのルールを明確にし、リリース管理を容易にします。

## **4. クリティカルな実装パス**

- **PDFリンク検知ロジック:**
  - `<a>`タグの`href`属性を抽出。
  - 正規表現 (`\.pdf(\?.*)?$`)
    を使用し、`.pdf`で終わるリンクおよびクエリパラメータが付与されたPDFリンク
    (`.pdf?version=1`など) の両方を確実に捕捉する。
  - 相対パスを絶対URLに正しく変換する（`urllib.parse.urljoin`などを利用）。
- **新規PDF判定ロジック:**
  - GCSから既存URLリスト（JSON）を読み込む。
  - 今回取得したURLリストと比較し、差分（新規URL）を特定する。
  - 新規URLがあれば、GCS上のリストを更新（アトミックな操作ではない点に注意）。
  - **初回実行時の特別処理:**
    ページ上の全PDFリンクを検知し、通知せずにGCSに保存する。
- **エラー通知フロー:**
  - 一般的なエラー: Logging記録 + 管理者Slack通知。
  - GCS読み込みエラー: Logging記録 + 管理者Slack通知 + **関数異常終了**。
  - GCS書き込みエラー: Logging記録 + 管理者Slack通知（関数は継続）。
  - Slack通知自体のエラー: Logging記録のみ。
