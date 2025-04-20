# **フェーズ5: デプロイフェーズ 詳細計画**

本ドキュメントは、MedFeeBot開発計画における「5. デプロイフェーズ」の具体的なタスクと手順を定義します。

**目標:**

*   ステージング環境および本番環境へのアプリケーションデプロイ
*   CI/CDパイプラインの構築によるデプロイ自動化

**前提条件:**

*   GCPプロジェクトがステージング用、本番用にそれぞれ準備されていること (または作成すること)
*   Slackワークスペースにテスト用、本番用のチャンネルが準備されていること (または作成すること)
*   GitHubリポジトリ (`31103/MedFeeBot`) へのアクセス権限があること

---

## **1. ステージング環境構築 (手動初回セットアップ)**

ステージング環境は、本番環境へのデプロイ前の最終検証を行うための環境です。

### 1.1. GCPプロジェクト設定

*   **アクション:** ステージング用として指定されたGCPプロジェクトを選択、または新規に作成します。
*   **アクション:** プロジェクト内で以下のAPIを有効化します:
    *   Cloud Functions API
    *   Cloud Storage API
    *   Secret Manager API
    *   Cloud Build API
    *   Cloud Scheduler API
    *   Cloud Logging API
    *   Cloud Monitoring API
*   **確認:** GCPコンソールの「APIとサービス」>「ライブラリ」で各APIが有効になっていることを確認します。

### 1.2. Secret Manager設定

*   **アクション:** ステージング用のSlack APIトークン（`xoxb-...`形式）をSecret Managerに登録します。
    *   **シークレット名:** `medfeebot-slack-api-token-staging` (推奨)
    *   **値:** ステージング用Slackボットトークン
*   **アクション (任意):** 管理者通知用のSlackトークンが必要な場合は、同様に登録します (`medfeebot-admin-slack-token-staging` など)。
*   **確認:** Secret Managerコンソールでシークレットが作成され、値が登録されていることを確認します。シークレットの**リソース名**（例: `projects/PROJECT_ID/secrets/SECRET_NAME/versions/latest`）を控えておきます。

### 1.3. GCSバケット作成

*   **アクション:** ステージング用のGCSバケットを作成します。
    *   **バケット名:** `medfeebot-staging-state` (推奨、グローバルで一意な名前)
    *   **ロケーションタイプ:** Region (例: `asia-northeast1`)
    *   **ストレージクラス:** Standard
    *   **アクセス制御:** Uniform (推奨)
*   **アクション:** Cloud Functionsが使用するサービスアカウント（デフォルトまたは指定のもの）に対して、このバケットへのアクセス権限を付与します。
    *   **ロール:** ストレージオブジェクト管理者 (`roles/storage.objectAdmin`)
*   **確認:** GCSコンソールでバケットが作成され、権限が設定されていることを確認します。

### 1.4. Cloud Functions 手動デプロイ (初回)

*   **アクション:** ローカルリポジトリのルートディレクトリで、以下の `gcloud` コマンドを実行してCloud Functionsをデプロイします。
    ```bash
    gcloud functions deploy medfeebot-staging \
      --gen2 \
      --region=asia-northeast1 \
      --runtime=python39 \
      --source=. \
      --entry-point=main_gcf \
      --trigger-http \
      --allow-unauthenticated \
      --set-env-vars=^:^GCP_PROJECT=[STAGING_PROJECT_ID]:GCS_BUCKET_NAME=medfeebot-staging-state:KNOWN_URLS_FILE=known_urls_staging.json:LATEST_IDS_FILE=latest_ids_staging.json:TARGET_URLS=[カンマ区切りの監視URL]:SLACK_SECRET_ID=projects/[STAGING_PROJECT_ID]/secrets/medfeebot-slack-api-token-staging/versions/latest:LOG_LEVEL=INFO \
      --service-account=[FUNCTIONS_SERVICE_ACCOUNT_EMAIL] # 必要に応じて指定
    ```
    *   `[STAGING_PROJECT_ID]`、`[カンマ区切りの監視URL]`、`[FUNCTIONS_SERVICE_ACCOUNT_EMAIL]` は実際の値に置き換えてください。
    *   環境変数名は `src/config.py` の実装に合わせてください。
    *   サービスアカウントを指定しない場合は、デフォルトのCompute Engineサービスアカウントが使用されます。このアカウントにSecret ManagerとGCSへのアクセス権限が必要です。
*   **アクション:** デプロイに使用するサービスアカウントに以下のIAMロールが付与されていることを確認します:
    *   Secret Manager のシークレット アクセサー (`roles/secretmanager.secretAccessor`)
    *   GCS バケットへのアクセス権限 (ステップ 1.3 で設定済み)
*   **確認:** デプロイが成功し、Cloud Functionsコンソールで関数がアクティブになっていること、およびHTTPSトリガーURLが発行されていることを確認します。

### 1.5. Cloud Scheduler設定

*   **アクション:** ステージング用のCloud Schedulerジョブを作成します。
    *   **名前:** `medfeebot-staging-trigger` (推奨)
    *   **リージョン:** `asia-northeast1` (推奨)
    *   **頻度:** `0 */1 * * *` (毎時0分)
    *   **タイムゾーン:** 日本 (Asia/Tokyo)
    *   **ターゲットタイプ:** HTTP
    *   **URL:** ステップ 1.4 で取得したCloud FunctionsのHTTPSトリガーURL
    *   **HTTPメソッド:** POST (またはGET、`main_gcf`の実装に合わせる)
    *   **本文:** 空 (または必要に応じてJSONペイロード)
    *   **認証ヘッダー:** OIDCトークンを追加 (推奨)
        *   **サービスアカウント:** Cloud SchedulerがFunctionsを呼び出すためのサービスアカウント（新規作成または既存）を指定。このサービスアカウントには `Cloud Functions起動元` (`roles/cloudfunctions.invoker`) ロールが必要です。
*   **確認:** Cloud Schedulerコンソールでジョブが作成され、「有効」になっていることを確認します。

### 1.6. テスト用Slackチャンネル設定

*   **アクション:** ステージング環境からの通知を受け取るためのSlackチャンネルを作成します (例: `#medfeebot-staging`)。
*   **アクション:** ステージング用に作成したSlackボットアプリを、このチャンネルに招待します (`/invite @YourStagingBotName`)。
*   **確認:** ボットがチャンネルに参加していることを確認します。

### 1.7. 動作検証

*   **アクション:** Cloud Schedulerジョブを手動で実行します (`今すぐ実行`)。
*   **確認:**
    *   Cloud Loggingで `medfeebot-staging` 関数のログを確認し、エラーが発生していないかチェックします。
    *   GCSバケット (`medfeebot-staging-state`) 内に状態ファイル (`known_urls_staging.json`, `latest_ids_staging.json`) が作成されていることを確認します。
    *   (初回実行では通知されないはず) 再度ジョブを手動実行するか、1時間待機します。監視対象サイトで変更があれば、テスト用Slackチャンネル (`#medfeebot-staging`) に通知が届くことを確認します。
    *   意図的に監視対象サイトのコンテンツを変更するか、GCSの状態ファイルを編集して、差分検知と通知が正しく行われるかテストします。

---

## **2. CI/CDパイプライン構築 (GitHub Actions)**

継続的インテグレーションと継続的デプロイメントにより、コード変更後のテストとデプロイを自動化します。

### 2.1. GCPサービスアカウントキー作成 (CI/CD用)

*   **アクション:** CI/CDパイプライン専用のGCPサービスアカウントを作成します (例: `github-actions-deployer@PROJECT_ID.iam.gserviceaccount.com`)。
*   **アクション:** このサービスアカウントに必要なIAMロールを付与します:
    *   Cloud Functions 開発者 (`roles/cloudfunctions.developer`)
    *   ストレージオブジェクト管理者 (`roles/storage.objectAdmin`) - ステージング/本番バケット両方に対して
    *   サービス アカウント ユーザー (`roles/iam.serviceAccountUser`) - Cloud Functions実行サービスアカウントに対して
    *   Secret Manager のシークレット アクセサー (`roles/secretmanager.secretAccessor`) - ステージング/本番シークレット両方に対して
    *   Cloud Build 編集者 (`roles/cloudbuild.builds.editor`) - Functionsデプロイに必要
*   **アクション:** このサービスアカウントのキー (JSON形式) を生成し、安全な場所にダウンロードします。**このキーファイルはGitリポジトリにコミットしないでください。**
*   **確認:** サービスアカウントとキーが作成され、必要なロールが付与されていることを確認します。

### 2.2. GitHub Secrets設定

*   **アクション:** GitHubリポジトリ (`31103/MedFeeBot`) の `Settings > Secrets and variables > Actions` で、以下のシークレットを登録します。
    *   `GCP_SA_KEY_STAGING`: ステップ 2.1 でダウンロードしたサービスアカウントキーJSONファイルの内容全体をコピー＆ペースト。
    *   `GCP_PROJECT_ID_STAGING`: ステージング用GCPプロジェクトID。
    *   `GCS_BUCKET_STAGING`: ステージング用GCSバケット名 (`medfeebot-staging-state`)。
    *   `SLACK_SECRET_ID_STAGING`: ステージング用SlackトークンのSecret Managerリソース名 (ステップ 1.2 で控えたもの)。
    *   `TARGET_URLS_STAGING`: ステージング用の監視対象URL (カンマ区切り)。
    *   (必要に応じて他の環境変数も `_STAGING` 接尾辞付きで登録)
    *   ---
    *   `GCP_SA_KEY_PRODUCTION`: **本番環境構築後**に、本番デプロイ用のサービスアカウントキーを登録 (ステージングと同じキーでも可、ただし権限分離推奨)。
    *   `GCP_PROJECT_ID_PRODUCTION`: **本番環境構築後**に、本番用GCPプロジェクトIDを登録。
    *   `GCS_BUCKET_PRODUCTION`: **本番環境構築後**に、本番用GCSバケット名を登録。
    *   `SLACK_SECRET_ID_PRODUCTION`: **本番環境構築後**に、本番用SlackトークンのSecret Managerリソース名を登録。
    *   `TARGET_URLS_PRODUCTION`: **本番環境構築後**に、本番用の監視対象URLを登録。
    *   (必要に応じて他の環境変数も `_PRODUCTION` 接尾辞付きで登録)
*   **確認:** 各シークレットが正しく登録されていることを確認します。

### 2.3. GitHub Actions ワークフローファイル作成

*   **アクション:** リポジトリのルートに `.github/workflows/deploy.yml` ファイルを作成し、以下の内容を記述します (内容は要調整)。

    ```yaml
    name: Deploy MedFeeBot

    on:
      push:
        branches:
          - main # mainブランチへのpush時にトリガー
      workflow_dispatch: # 手動実行も可能にする

    jobs:
      test:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - name: Set up Python
            uses: actions/setup-python@v5
            with:
              python-version: '3.9' # プロジェクトで使用するバージョンに合わせる
          - name: Install dependencies
            run: |
              python -m pip install --upgrade pip
              pip install -r requirements.txt
              pip install -r requirements-dev.txt
          - name: Run tests with pytest
            run: pytest
          - name: Check types with mypy
            run: mypy src tests

      deploy_staging:
        needs: test # testジョブの成功が必要
        runs-on: ubuntu-latest
        environment: staging # オプション: 環境保護ルールを設定する場合
        steps:
          - uses: actions/checkout@v4

          - id: 'auth'
            uses: 'google-github-actions/auth@v2'
            with:
              credentials_json: '${{ secrets.GCP_SA_KEY_STAGING }}'

          - name: 'Set up Cloud SDK'
            uses: 'google-github-actions/setup-gcloud@v2'

          - name: 'Deploy to Cloud Functions (Staging)'
            run: |
              gcloud functions deploy medfeebot-staging \
                --gen2 \
                --region=asia-northeast1 \
                --runtime=python39 \
                --source=. \
                --entry-point=main_gcf \
                --trigger-http \
                --allow-unauthenticated \
                --set-env-vars=^:^GCP_PROJECT=${{ secrets.GCP_PROJECT_ID_STAGING }}:GCS_BUCKET_NAME=${{ secrets.GCS_BUCKET_STAGING }}:KNOWN_URLS_FILE=known_urls_staging.json:LATEST_IDS_FILE=latest_ids_staging.json:TARGET_URLS=${{ secrets.TARGET_URLS_STAGING }}:SLACK_SECRET_ID=${{ secrets.SLACK_SECRET_ID_STAGING }}:LOG_LEVEL=INFO \
                --service-account=[FUNCTIONS_SERVICE_ACCOUNT_EMAIL] # 必要に応じて指定

      deploy_production:
        needs: deploy_staging # deploy_stagingジョブの成功が必要
        runs-on: ubuntu-latest
        environment: production # 本番環境用の保護ルールを設定
        if: github.ref == 'refs/heads/main' # mainブランチへのpush時のみ実行 (タグ契機などに変更可)
        steps:
          - uses: actions/checkout@v4

          - id: 'auth'
            uses: 'google-github-actions/auth@v2'
            with:
              credentials_json: '${{ secrets.GCP_SA_KEY_PRODUCTION }}' # 本番用キーを使用

          - name: 'Set up Cloud SDK'
            uses: 'google-github-actions/setup-gcloud@v2'

          - name: 'Deploy to Cloud Functions (Production)'
            run: |
              gcloud functions deploy medfeebot-production \
                --gen2 \
                --region=asia-northeast1 \
                --runtime=python39 \
                --source=. \
                --entry-point=main_gcf \
                --trigger-http \
                --allow-unauthenticated \
                --set-env-vars=^:^GCP_PROJECT=${{ secrets.GCP_PROJECT_ID_PRODUCTION }}:GCS_BUCKET_NAME=${{ secrets.GCS_BUCKET_PRODUCTION }}:KNOWN_URLS_FILE=known_urls_production.json:LATEST_IDS_FILE=latest_ids_production.json:TARGET_URLS=${{ secrets.TARGET_URLS_PRODUCTION }}:SLACK_SECRET_ID=${{ secrets.SLACK_SECRET_ID_PRODUCTION }}:LOG_LEVEL=INFO \
                --service-account=[FUNCTIONS_SERVICE_ACCOUNT_EMAIL] # 必要に応じて指定
    ```
    *   `[FUNCTIONS_SERVICE_ACCOUNT_EMAIL]` は実際のサービスアカウントに置き換えてください。
    *   環境変数や関数名 (`medfeebot-production`) は本番用に調整してください。
    *   本番デプロイのトリガー (`if: ...`) は、必要に応じてタグpush (`startsWith(github.ref, 'refs/tags/v')`) や手動承認 (`environment` の設定) に変更してください。
*   **確認:** `.github/workflows/deploy.yml` をコミットし、`main` ブランチにプッシュします。GitHub Actionsタブでワークフローが実行され、`test` と `deploy_staging` ジョブが成功することを確認します。

*   **Mermaid図 (CI/CDパイプライン イメージ):**
    ```mermaid
    graph TD
        A[Push to main / Manual Trigger] --> B(Run Tests);
        B -- Success --> C{Deploy to Staging};
        C -- Success --> D{Trigger for Production};
        D -- Triggered --> E{Deploy to Production};
        B -- Failure --> F[Report Failure];
        C -- Failure --> F;
        E -- Failure --> F;
    ```
    *(Production Trigger: Can be automatic on main push, manual approval, or tag push)*

---

## **3. 本番環境構築**

ステージング環境構築と同様の手順で、本番環境を構築します。**設定値は本番用のものを使用してください。**

*   **3.1. GCPプロジェクト設定:** 本番用プロジェクトを選択または作成し、APIを有効化。
*   **3.2. Secret Manager設定:** 本番用Slack APIトークンを登録 (`medfeebot-slack-api-token-production` など)。リソース名を控える。
*   **3.3. GCSバケット作成:** 本番用GCSバケットを作成 (`medfeebot-production-state` など)。権限付与。
*   **3.4. Cloud Functions 手動デプロイ (初回):**
    *   `gcloud functions deploy medfeebot-production ...` を実行。
    *   環境変数には本番用のプロジェクトID, バケット名, 状態ファイル名 (`known_urls_production.json` など), 監視URL, Secret Managerリソース名を設定。
    *   サービスアカウントに必要な権限を付与。
*   **3.5. Cloud Scheduler設定:** 本番用ジョブを作成 (`medfeebot-production-trigger` など)。ターゲットURLは本番Functionsのもの。
*   **3.6. 本番Slackチャンネル設定:** 本番通知用チャンネルを作成し、本番ボットアプリを招待。
*   **3.7. 動作検証:** ステージングと同様に、手動実行やログ確認、通知確認を実施。
*   **3.8. GitHub Secrets更新:** ステップ 2.2 でプレースホルダーになっていた本番環境用のシークレット (`GCP_SA_KEY_PRODUCTION`, `GCP_PROJECT_ID_PRODUCTION`, etc.) に実際の値を設定。

---

## **4. CI/CDパイプライン 本番デプロイ有効化**

*   **アクション:** GitHub Actions ワークフロー (`.github/workflows/deploy.yml`) の `deploy_production` ジョブのトリガー条件が意図通りか確認します (例: `main` ブランチへの push で自動デプロイ、またはタグ push 契機か)。
*   **アクション (任意):** 必要であれば、GitHubの `Environments` 設定で `production` 環境に対する保護ルール（承認者の設定など）を構成します。
*   **アクション (任意):** 最初の本番デプロイをCI/CD経由でトリガーし（例: `main` にマージ、またはタグを作成してプッシュ）、Actionsタブでデプロイが成功することを確認します。

---

## **成果物:**

*   デプロイ済みステージング環境 (Cloud Functions, GCS, Scheduler)
*   デプロイ済み本番環境 (Cloud Functions, GCS, Scheduler)
*   CI/CD設定ファイル (`.github/workflows/deploy.yml`)
*   更新されたデプロイ手順書 (本ドキュメント)
*   設定済み環境変数一覧 (別途ドキュメント化推奨)