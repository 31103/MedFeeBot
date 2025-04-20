# MedFeeBot

厚生労働省などの医療関連ウェブサイトを定期的に監視し、**新しい通知文書（PDF）の掲載**や**特定の会議（例:
中央社会保険医療協議会総会）の新規開催**を検知して、指定されたSlackチャンネルへ通知を行うボットです。

## 概要

このボットは、設定された複数のURLを監視し、それぞれのURLに対して定義された目的（PDF検知または会議開催検知）に基づいて変更を検出します。

- **PDF検知:**
  新しいPDF文書が掲載されると、その文書の日付、名称、URLを抽出して通知します。
- **会議開催検知:**
  新しい会議が開催されると、その会議の回数、開催日、議題、関連リンク（資料、議事録など）を抽出して通知します。

これにより、重要な情報を見逃すリスクを低減し、情報収集の効率化を図ります。
現在はローカル環境での実行とGoogle Cloud Functionsでの運用に対応しています。

## 機能

- **複数URL監視:** 設定ファイルで指定された複数のURLを並行して監視します。
- **タイプ別検知:**
  URLごとに「PDF検知」または「会議開催検知」のいずれかのモードで動作します。
- **HTMLコンテンツ取得:** 指定されたURLからHTMLコンテンツを取得します。
- **コンテンツ解析:**
  - PDF検知モード: HTML内から文書情報（日付、名称、PDFリンク）を抽出します。
  - 会議開催検知モード:
    HTML内から最新の会議情報（回数、日付、議題、関連リンク）を抽出します。
- **差分検知:**
  - PDF検知モード: 既知のPDF URLリストと比較し、新規PDFを検出します。
  - 会議開催検知モード: 前回検知した会議の識別子（例:
    会議回数）と比較し、新規会議開催を検出します。
- **状態管理:** 検知済みのPDF
  URLリストと最後に検知した会議IDを永続化します（ローカルファイルまたはGCS）。
- **Slack通知:**
  新規PDFまたは新規会議が検出された場合、整形された情報を指定されたSlackチャンネルに通知します。
- **エラーハンドリングと通知:**
  処理中にエラーが発生した場合、ログに記録し、管理者向けSlackチャンネルに通知します。
- **設定駆動:** `src/config.py` 内の `URL_CONFIGS`
  辞書により、URLごとの監視タイプと使用するパーサー関数を定義します（開発者向け）。
- **処理ログの出力:** 詳細な処理ログを出力します。

## スクリプトとしてのローカル実行

この方法は、Cloud Functions 環境をエミュレートせず、Python
スクリプトとして直接実行する場合の手順です。主に開発初期段階や特定のモジュールのテストに利用します。

### 1. 前提条件

- Python 3.9 以降
- Git

### 2. セットアップ

1. **リポジトリをクローン:**
   ```bash
   git clone https://github.com/31103/MedFeeBot.git
   cd MedFeeBot
   ```

2. **仮想環境の作成と有効化:**
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **依存関係のインストール:**
   ```bash
   pip install -r requirements.txt
   # 開発用ツールもインストールする場合
   # pip install -r requirements-dev.txt
   ```

4. **.env ファイルの作成:** プロジェクトルートに `.env`
   という名前のファイルを作成し、以下の内容を記述して、実際の値に置き換えてください。

   ```dotenv
   # .envファイルの内容例
   # 監視したいURLをカンマ区切りで指定
   TARGET_URLS="https://www.hospital.or.jp/site/ministry/,https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html"

   # Slack設定 (必須)
   SLACK_API_TOKEN="xoxb-から始まるSlackボットトークン" # GCF環境ではSecret Manager経由推奨
   SLACK_CHANNEL_ID="通知を送りたいSlackチャンネルのID"

   # --- オプション ---
   # エラー通知用チャンネル
   # SLACK_ADMIN_CHANNEL_ID="エラー通知を送りたい管理者用チャンネルID"

   # ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   # LOG_LEVEL="DEBUG" # デフォルトはINFO

   # 状態保存ファイル名 (ローカル実行時 / GCSオブジェクト名)
   # KNOWN_URLS_FILE="known_urls_prod.json" # デフォルトは known_urls.json (PDF検知用)
   # LATEST_IDS_FILE="latest_ids_prod.json" # デフォルトは latest_ids.json (会議検知用)

   # GCS設定 (GCF環境では必須)
   # GCS_BUCKET_NAME="your-gcs-bucket-name"
   ```
   - `TARGET_URLS`: **必須。**
     監視対象のURLをカンマ区切りで指定します。ここに指定されたURLのうち、`src/config.py`
     の `URL_CONFIGS` で設定されているものだけが処理されます。
   - `SLACK_API_TOKEN`: **必須。** Slackアプリのボットユーザートークン
     (`Bot User OAuth Token`)。`chat:write` スコープが必要です。Cloud Functions
     環境では、後述の `SLACK_SECRET_ID` を使用することを強く推奨します。
   - `SLACK_CHANNEL_ID`: **必須。**
     通知を送信するSlackチャンネルのID。ボットがこのチャンネルに参加している必要があります。
   - `SLACK_ADMIN_CHANNEL_ID` (オプション):
     エラー発生時に通知を受け取るチャンネルID。設定しない場合、エラー通知は送信されません。
   - `LOG_LEVEL` (オプション): ログの詳細度。デフォルトは `INFO`。
   - `KNOWN_URLS_FILE` (オプション):
     PDF検知モードで使用する既知URLリストを保存するファイル名。ローカル実行時はこの名前のファイルが作成/更新され、GCS利用時はこの名前がオブジェクト名として使用されます。デフォルトは
     `known_urls.json`。
   - `LATEST_IDS_FILE` (オプション):
     会議開催検知モードで使用する最後に検知した会議IDを保存するファイル名。ローカル実行時はこの名前のファイルが作成/更新され、GCS利用時はこの名前がオブジェクト名として使用されます。デフォルトは
     `latest_ids.json`。
   - `GCS_BUCKET_NAME` (オプション/GCFでは必須):
     状態ファイルを保存するGCSバケット名。ローカル実行でもGCSを利用したい場合に設定します。Cloud
     Functions環境では必須です。

### 3. 実行

以下のコマンドでスクリプトを実行します。

```bash
python -m src.main
```

スクリプトは `.env`
ファイルから設定を読み込み、指定されたURLをチェックし、新規文書が見つかればSlackに通知します。
初回実行時（または状態ファイルが存在しない場合）は、各URLで検出された現在の状態（PDFリストまたは最新会議ID）が保存され、通知は行われません。2回目以降の実行で、前回保存された状態と比較して差分（新規PDFまたは新規会議）が検出された場合に通知されます。

## Google Cloud Functions での実行

### 1. デプロイに必要な環境変数

Cloud Functions にデプロイする際には、以下の環境変数を設定する必要があります。

- **必須:**
  - `TARGET_URLS`: **必須。** 監視対象のURLをカンマ区切りで指定します。
  - `SLACK_CHANNEL_ID`: **必須。** 通知を送信するSlackチャンネルのID。
  - `SLACK_SECRET_ID`: **必須。** Slack API トークンが保存されている Secret
    Manager のシークレットID (例:
    `projects/your-project-id/secrets/your-slack-token-secret/versions/latest`)。
  - `GCS_BUCKET_NAME`: **必須。** 状態ファイル (`known_urls.json`,
    `latest_ids.json` など) を保存する GCS バケット名。
- **オプション:**
  - `ADMIN_SLACK_CHANNEL_ID`: エラー発生時に通知を受け取るチャンネルID。
  - `LOG_LEVEL`: ログレベル。デフォルトは `INFO`。
  - `KNOWN_URLS_FILE`: PDF検知用の状態ファイル名
    (GCSオブジェクト名)。デフォルトは `known_urls.json`。
  - `LATEST_IDS_FILE`: 会議検知用の状態ファイル名
    (GCSオブジェクト名)。デフォルトは `latest_ids.json`。

### 2. ローカルでのエミュレーション (Functions Framework)

Cloud Functions へのデプロイ前に、ローカル環境で関数の動作を確認できます。

1. **開発用依存関係のインストール:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **環境変数の設定:**
   上記「デプロイに必要な環境変数」で説明した変数を、ローカル環境の環境変数として設定するか、`.env`
   ファイルに記述します。(ローカルエミュレーションでは `SLACK_API_TOKEN` を
   `.env` に記述し、`SLACK_SECRET_ID` を設定しない方法も可能です。) GCS
   へのアクセスには、ローカル環境で GCP への認証が必要です
   (`gcloud auth application-default login`)。

3. **Functions Framework の実行:**
   プロジェクトのルートディレクトリで以下のコマンドを実行します。

   ```bash
   functions-framework --target=main_gcf --source=src/main.py --port=8080
   ```
   - `--target`: 実行する関数の名前 (`main_gcf`)。
   - `--source`: エントリーポイントが含まれるファイル (`src/main.py`)。
   - `--port`: ローカルサーバーがリッスンするポート (デフォルトは 8080)。

4. **関数のトリガー:** 別のターミナルまたは `curl`
   などを使用して、ローカルサーバーに HTTP リクエストを送信します。

   ```bash
   curl http://localhost:8080/
   ```
   これにより `main_gcf` 関数が実行され、コンソールにログが出力されます。

## 開発者向け情報

### URLごとの設定 (`src/config.py`)

`src/config.py` 内の `URL_CONFIGS` 辞書で、`TARGET_URLS`
環境変数で指定された各URLに対する処理方法を定義します。

```python
# src/config.py 内の例
URL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "https://www.hospital.or.jp/site/ministry/": {
        "type": "pdf", # 監視タイプ: PDF文書の新規追加を検知
        "parser": parser.extract_hospital_document_info # 使用するパーサー関数
    },
    "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html": {
        "type": "meeting", # 監視タイプ: 最新会議の更新を検知
        "parser": parser.extract_latest_chuikyo_meeting # 使用するパーサー関数
    }
    # 他の監視対象URLと設定を追加可能
}
```

- **キー:** 監視対象のURL文字列。
- **値 (辞書):**
  - `"type"`: 監視タイプ (`"pdf"` または `"meeting"`)。`main.py`
    はこのタイプに基づいて差分検知と通知処理を分岐します。
  - `"parser"`: そのURLのHTMLコンテンツを解析するための関数オブジェクト
    (`src/parser.py` 内で定義)。
    - `pdf` タイプの場合、通常は文書情報 (日付、タイトル、URLなど)
      を含む辞書のリスト (`List[Dict[str, str]]`) を返す関数を指定します。
    - `meeting` タイプの場合、通常は最新の会議情報 (ID、日付、議題、リンクなど)
      を含む辞書 (`Dict[str, Any]`) または情報が見つからない場合に `None`
      を返す関数を指定します。

新しい監視対象URLを追加する場合は、`TARGET_URLS`
環境変数に追加し、対応する設定を `URL_CONFIGS` に追加する必要があります。

## 開発計画

詳細な開発計画は [docs/development_plan.md](docs/development_plan.md)
を参照してください。

## 貢献

貢献方法については [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
