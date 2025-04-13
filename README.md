# MedFeeBot

厚生労働省のウェブサイトにおける診療報酬に関連するページを定期的に監視し、新たな通知文書（PDFファイル）が掲載された場合に、指定されたSlackチャンネルへ通知を行うボットです。

## 概要

このボットは、厚生労働省の特定ページを監視し、新しいPDFリンクを検出するとSlackに通知します。これにより、診療報酬改定などの重要な情報を見逃すリスクを低減し、情報収集の効率化を図ります。

現在はローカル環境での実行に対応しています。将来的にはGoogle Cloud
Functionsでの運用を予定しています。

## 機能

- 指定されたURLのHTMLコンテンツを取得
- HTML内からPDFファイルへのリンクを抽出
- 既知のURLリスト（`known_urls.json`）と比較し、新規URLを検出
- 新規URLが検出された場合、指定されたSlackチャンネルに通知
- 処理ログの出力

## ローカルでの実行方法

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
   TARGET_URL="監視したい厚生労働省のページのURL"
   SLACK_BOT_TOKEN="xoxb-から始まるSlackボットトークン"
   SLACK_CHANNEL_ID="通知を送りたいSlackチャンネルのID"
   # SLACK_ADMIN_CHANNEL_ID="エラー通知を送りたい管理者用チャンネルID (オプション)"
   # LOG_LEVEL="DEBUG" # オプション (デフォルトはINFO)
   ```
   - `TARGET_URL`: 監視対象のウェブページのURL。
   - `SLACK_BOT_TOKEN`: Slackアプリのボットユーザートークン
     (`Bot User OAuth Token`)。`chat:write` スコープが必要です。
   - `SLACK_CHANNEL_ID`:
     通知を送信するSlackチャンネルのID。ボットがこのチャンネルに参加している必要があります。
   - `SLACK_ADMIN_CHANNEL_ID` (オプション):
     エラー発生時に通知を受け取るチャンネルID。
   - `LOG_LEVEL` (オプション): ログの詳細度を指定します (`DEBUG`, `INFO`,
     `WARNING`, `ERROR`, `CRITICAL`)。デフォルトは `INFO` です。

### 3. 実行

以下のコマンドでスクリプトを実行します。

```bash
python -m src.main
```

スクリプトは `.env`
ファイルから設定を読み込み、指定されたURLをチェックし、新規PDFが見つかればSlackに通知します。
初回実行時は、検出されたすべてのPDFリンクが `known_urls.json`
に保存され、通知は行われません。2回目以降の実行で、前回以降に新たに追加されたPDFリンクが通知されます。

## 開発計画

詳細な開発計画は [docs/development_plan.md](docs/development_plan.md)
を参照してください。

## 貢献

貢献方法については [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
