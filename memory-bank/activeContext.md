# **アクティブコンテキスト: MedFeeBot (CI/CD ワークフロー修正完了)**

## **1. 現在のフォーカス**

- **CI/CDパイプラインの検証:**
  - GitHub Actions ワークフロー (`.github/workflows/deploy.yml`) が `main`
    ブランチへのプッシュ時に正しく動作するか確認する。
  - 必要な GitHub Secrets (GCPサービスアカウントキー、プロジェクトID等)
    を設定する。
- **本番環境構築:** `docs/deployment_plan_phase5.md`
  に基づき、本番環境のセットアップを進める。
- **パーサーバグ修正:** GitHub Issue #6
  で追跡されている中医協パーサーのバグ修正に取り組む (別タスク)。

## **2. 最近の変更**

- **設定管理の拡張 (`src/config.py`, `.env`):** (変更なし)
- **パーサーの追加 (`src/parser.py`):** (変更なし)
- **ストレージ機能の拡張 (`src/storage.py`):** (変更なし)
- **メインロジックの修正 (`src/main.py`):** (変更なし)
- **通知機能の調整 (`src/notifier.py`):** (変更なし)
- **テストコードの追加・更新:** (変更なし)
- **テスト実行:** (変更なし)
- **ドキュメント更新:**
  - `README.md`: CI/CD (GitHub Actions) に関するセクションを追加。
  - `docs/deployment_plan_phase5.md`:
    手動デプロイ手順の修正（PowerShell対応、`--env-vars-file`
    推奨、`--source=./src` 指定、`requirements.txt`
    の配置、ランタイムバージョン更新、必要IAMロール追記）、GitHub
    Actionsワークフロー例の更新。
- **中医協パーサーの修正 (`src/parser.py`):** (変更なし - バグ再発 Issue #6)
- **CI/CDパイプライン構築:**
  - GitHub Actions ワークフローファイル (`.github/workflows/deploy.yml`)
    を作成。テストジョブとステージング環境へのデプロイジョブを定義。
  - GitHub Actions ワークフローファイル (`.github/workflows/deploy.yml`)
    を修正。ステージングデプロイジョブで環境変数を `--env-vars-file` を使用して
    YAML ファイルから読み込むように変更。
- **ステージング環境手動デプロイ:**
  - `gcloud functions deploy` コマンドを使用してステージング環境
    (`medfeebot-staging`) への初回手動デプロイを実施。
  - **デバッグと修正:**
    - デプロイエラー (`requirements.txt` / `main.py` が見つからない)
      に対処するため、`requirements.txt` を `src`
      ディレクトリにコピーし、`--source=./src` を指定するように変更。
    - コンテナ起動エラー (`Container Healthcheck failed`)
      に対処するため、`src/requirements.txt` に `functions-framework` を追加。
    - コンテナ起動時の `ModuleNotFoundError: No module named 'src'`
      に対処するため、`src/config.py` の `from src import parser` を
      `import parser` に修正。
    - 実行時エラー (`PermissionDenied` for Secret Manager) に対処するため、Cloud
      Functions実行サービスアカウントに `roles/secretmanager.secretAccessor`
      ロールを付与。
  - **デプロイ成功:**
    上記修正により、ステージング環境への手動デプロイと基本的な動作（Secret
    Managerからのトークン取得含む）を確認。
- **パーサーバグの特定:**
  ステージング環境での実行テスト中に、中医協パーサーがヘッダー行 ("回数")
  を誤って解析するバグの再発を確認。GitHub Issue #6 を作成して追跡。

## **3. 次のステップ**

1. **CI/CDパイプライン検証:**
   - GitHub リポジトリに必要な Secrets (`GCP_SA_KEY_STAGING`,
     `GCP_PROJECT_ID_STAGING` など) を設定する。
   - `main` ブランチにコードをプッシュし、GitHub Actions
     ワークフローがトリガーされ、`test` ジョブと `deploy_staging`
     ジョブが成功することを確認する。
2. **本番環境構築:**
   - `docs/deployment_plan_phase5.md` の「3.
     本番環境構築」セクションに従い、GCPプロジェクト設定、Secret
     Manager設定、GCSバケット作成、Cloud Functions手動デプロイ、Cloud
     Scheduler設定、Slackチャンネル設定を行う。
3. **CI/CD 本番デプロイ有効化:**
   - 本番環境用の GitHub Secrets を設定する。
   - `.github/workflows/deploy.yml` の `deploy_production`
     ジョブのトリガー条件を確認・設定する。
   - 必要に応じて GitHub Environments で保護ルールを設定する。
   - CI/CD経由での本番デプロイをテストする。
4. **パーサーバグ修正:** Issue #6 に基づき、`src/parser.py` の
   `extract_latest_chuikyo_meeting` 関数を修正する (別タスク)。

## **4. アクティブな決定事項**

- (変更なし)
  準備フェーズ、基本実装フェーズ、テストフェーズ、クラウド実装フェーズのタスクは完了。
- (変更なし) デプロイフェーズを進行中。
- (変更なし) メモリバンクのコアファイル構造を採用。
- (変更なし) `docs/development_plan.md`
  に記載されたフェーズに従って開発を進める。
- (変更なし) `docs/specifications.md`
  に記載された技術スタック、アーキテクチャ、開発プラクティスを採用する。
- (変更なし) 永続化方法として GCS 上の JSON ファイルが最適。
- (変更なし) 複数URL監視、設定駆動型アーキテクチャ (`URL_CONFIGS`) を採用。
- (変更なし) 中医協パーサーはアドホック実装。
- (変更なし) 状態管理はファイル分離。
- (変更なし) Slack通知メッセージ形式。
- **Cloud Functions デプロイ構成:**
  - ソースディレクトリは `./src` を指定。
  - 依存関係ファイル `requirements.txt` は `src`
    ディレクトリ内に配置する必要がある。
  - HTTPトリガーの場合、`functions-framework` が `requirements.txt` に必要。
  - 環境変数は `--env-vars-file=env-staging.yaml` (ステージングの場合)
    で設定することを推奨（特にPowerShell環境）。
- **実行サービスアカウント権限:** Cloud
  Functions実行サービスアカウントには、GCSバケットへのアクセス権
  (`roles/storage.objectAdmin` 等) と Secret Managerへのアクセス権
  (`roles/secretmanager.secretAccessor`) が必要。

## **5. 重要なパターンと設定**

- **開発プロセス:** (変更なし)
- **コード品質:** (変更なし)
- **設定管理:** (変更なし)
- **状態管理:** (変更なし)
- **エラーハンドリング:** (変更なし)
- **モジュール構成:** (変更なし)
- **テスト戦略:** (変更なし)
- **Cloud Functions エントリーポイント:** (変更なし)
- **パーサーロジック:** (変更なし - バグあり Issue #6)
- **通知メッセージ形式:** (変更なし)
- **デプロイコマンド (PowerShell):** 行継続文字は `` ` ``、`--set-env-vars` より
  `--env-vars-file` を推奨。
- **Pythonインポート:** Cloud Functions環境 (`--source=./src` の場合)
  では、`src` ディレクトリ内のモジュールをインポートする際は相対インポート
  (`from . import module`) または直接インポート (`import module`) を使用する
  (`from src import module` は不可)。

## **6. 学びと洞察**

- (変更なし) Slack API トークンとスコープ。
- (変更なし) Slack ボットのチャンネル招待。
- (変更なし) PoCによる技術検証。
- (変更なし) 基本実装によるコンポーネント連携。
- (変更なし) ローカル状態管理。
- (変更なし) テストとリファクタリングの効果。
- (変更なし) TDD的アプローチの有効性。
- (変更なし) Cloud Functionsのロジック分離。
- (変更なし) GCS `NotFound` 例外。
- (変更なし) Secret Managerの利点。
- (変更なし) 仕様書と計画の重要性。
- (変更なし) メモリバンクの継続更新。
- (変更なし) 特定サイト向けパーサーの脆弱性。
- (変更なし) 引数渡しによるテスト容易性。
- (変更なし) 設定駆動型アーキテクチャの利点と管理コスト。
- (変更なし) 状態管理の分離。
- (変更なし) HTML構造の複雑さへの対応。
- **Cloud Functions デプロイの依存関係:** `--source`
  で指定したディレクトリ直下に `requirements.txt` が必要。HTTPトリガーには
  `functions-framework` が必須。
- **Cloud Functions Python インポートパス:** `--source=./src` の場合、`src`
  がルートとして扱われるため、`src` 内の他モジュールは `from src import ...`
  ではなく `import ...` や `from . import ...` でインポートする必要がある。
- **Cloud Functions 実行権限:** 関数が使用するGCPサービス (GCS, Secret
  Manager等)
  へのアクセス権限を実行サービスアカウントに適切に付与する必要がある。
- **`gcloud` コマンドのシェル依存性:**
  コマンドの行継続文字や特殊文字の扱いはシェル (Bash, PowerShell等)
  によって異なるため注意が必要。`--env-vars-file`
  はシェル依存を減らすのに有効であり、CI/CD ワークフローでも採用。
- **コンテナヘルスチェック:** Cloud Functions (Gen2) / Cloud Run
  のコンテナ起動時にコードの初期化（インポート時など）でエラーが発生すると、ヘルスチェックが失敗しデプロイがロールバックされる。ログの詳細な確認が不可欠。
