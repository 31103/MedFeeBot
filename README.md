# MedFeeBot

医療関連のウェブサイトにおける通知文書（PDFファイル）を定期的に監視し、新たな文書が掲載された場合に、指定されたSlackチャンネルへ通知を行うボットです。

## 概要

このボットは、指定された医療関連ページを監視し、新しい文書（PDF）を検出するとSlackに通知します。これにより、重要な情報を見逃すリスクを低減し、情報収集の効率化を図ります。検出時には、文書の日付、名称、およびURLを抽出して通知します。

現在はローカル環境での実行に対応しています。将来的にはGoogle Cloud
Functionsでの運用を予定しています。

## 機能

- 指定されたURLのHTMLコンテンツを取得
- HTML内から文書情報（日付、名称、PDFファイルへのリンク）を抽出
- 既知のURLリストと比較し、新規文書を検出
- 新規文書が検出された場合、文書の日付、名称、URLを含む情報を指定されたSlackチャンネルに通知
- 処理ログの出力

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
   # .envファイルの内容例 (スクリプト実行用)
   TARGET_URL="監視したい医療関連ページのURL" # 例: https://www.hospital.or.jp/site/ministry/
   SLACK_API_TOKEN="xoxb-から始まるSlackボットトークン" # GCF環境ではSecret Manager経由
   SLACK_CHANNEL_ID="通知を送りたいSlackチャンネルのID"
   # --- オプション ---
   # SLACK_ADMIN_CHANNEL_ID="エラー通知を送りたい管理者用チャンネルID"
   # LOG_LEVEL="DEBUG" # デフォルトはINFO
   # KNOWN_URLS_FILE_PATH="custom_known_urls.json" # デフォルトは known_urls.json
   # GCS_BUCKET_NAME="your-gcs-bucket-name" # GCS利用テスト時
   # GCS_OBJECT_NAME="path/to/your/known_urls.json" # GCS利用テスト時
   ```
   - `TARGET_URL`: 監視対象の医療関連ウェブページのURL。
   - `SLACK_API_TOKEN`: Slackアプリのボットユーザートークン
     (`Bot User OAuth Token`)。`chat:write` スコープが必要です。**注意:** Cloud
     Functions 環境では `SLACK_SECRET_ID` を使用します。
   - `SLACK_CHANNEL_ID`:
     通知を送信するSlackチャンネルのID。ボットがこのチャンネルに参加している必要があります。
   - `SLACK_ADMIN_CHANNEL_ID` (オプション):
     エラー発生時に通知を受け取るチャンネルID。
   - `LOG_LEVEL` (オプション): ログの詳細度 (`DEBUG`, `INFO`, `WARNING`,
     `ERROR`, `CRITICAL`)。デフォルトは `INFO`。
   - `KNOWN_URLS_FILE_PATH` (オプション): ローカル実行時に既知 URL
     を保存するファイルパス。デフォルトは `known_urls.json`。**注意:** Cloud
     Functions 環境では GCS を使用します。
   - `GCS_BUCKET_NAME`, `GCS_OBJECT_NAME` (オプション): ローカルから GCS
     を利用してテストする場合に設定します。

### 3. 実行

以下のコマンドでスクリプトを実行します。

```bash
python -m src.main
```

スクリプトは `.env`
ファイルから設定を読み込み、指定されたURLをチェックし、新規文書が見つかればSlackに通知します。
初回実行時は、検出されたすべての文書のURLが既知のリストに保存され、通知は行われません。2回目以降の実行で、前回以降に新たに追加された文書が通知されます。通知メッセージには、文書の日付、名称、URLが含まれます。

## Google Cloud Functions での実行

### 1. デプロイに必要な環境変数

Cloud Functions にデプロイする際には、以下の環境変数を設定する必要があります。

- **必須:**
  - `TARGET_URL`: 監視対象の医療関連ウェブページのURL。
  - `SLACK_CHANNEL_ID`: 通知を送信するSlackチャンネルのID。
  - `SLACK_SECRET_ID`: Slack API トークンが保存されている Secret Manager
    のシークレットID (例:
    `projects/your-project-id/secrets/your-slack-token-secret/versions/latest`)。
  - `GCS_BUCKET_NAME`: 既知 URL リストを保存する GCS バケット名。
  - `GCS_OBJECT_NAME`: GCS バケット内の既知 URL リストのファイルパス (例:
    `medfeebot/known_urls.json`)。
- **オプション:**
  - `ADMIN_SLACK_CHANNEL_ID`: エラー発生時に通知を受け取るチャンネルID。
  - `LOG_LEVEL`: ログレベル (`DEBUG`, `INFO`, `WARNING`, `ERROR`,
    `CRITICAL`)。デフォルトは `INFO`。

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

## 開発計画

詳細な開発計画は [docs/development_plan.md](docs/development_plan.md)
を参照してください。

## 貢献

貢献方法については [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
