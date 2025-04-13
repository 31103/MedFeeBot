# **技術コンテキスト: MedFeeBot**

## **1. 開発言語とランタイム**

- **言語:** Python
- **バージョン:** 3.9 以降を推奨
- **実行環境:** Google Cloud Functions (第2世代) Python ランタイム

## **2. 主要ライブラリと依存関係**

- **HTTP通信:** `requests` - 厚生労働省サイトへのアクセス、Slack API
  呼び出しに使用。
- **HTML解析:** `beautifulsoup4` (または `lxml`) -
  取得したHTMLからPDFリンクを抽出するために使用。
- **Slack連携:** `slack_sdk` - Slack
  APIとのインタラクション（メッセージ投稿）に使用。
- **GCP連携:**
  - `google-cloud-storage`: 既知のPDF URLリストをGCSに永続化するために使用。
  - (Cloud Functions 環境では、`google-cloud-logging`, `google-cloud-monitoring`
    は通常、標準ライブラリやGCP提供の機能を通じて利用される)
- **設定管理 (ローカル開発):** `python-dotenv` - `.env`
  ファイルから環境変数を読み込むためにローカル開発時に使用。
- **型アノテーション:** `typing` (標準ライブラリ) -
  コード全体で型ヒントを付与し、可読性と保守性を向上させるために使用。静的解析ツール
  `mypy` と組み合わせて利用。

_依存関係管理:_ `requirements.txt` ファイルで管理します。

## **3. 開発環境**

- **仮想環境:** `venv` または `pipenv`
  を使用してプロジェクト固有の依存関係を管理。
- **IDE:** VSCode (推奨) または他のPython対応IDE。
- **バージョン管理:** Git を使用し、GitHub 上のリポジトリ (`MedFeeBot`) で管理。
- **ローカル実行:** ローカルでのテスト・デバッグ用に、Cloud Functions
  のエミュレータや、環境変数を `.env` ファイルで管理する仕組みを用意します。

## **4. テスト**

- **テストフレームワーク:** `pytest` - 単体テストおよび結合テストの実装に使用。
- **モックライブラリ:** `unittest.mock` (標準ライブラリ) または `pytest-mock` -
  外部依存（HTTPリクエスト、GCS、Slack
  API）をテストダブルに置き換えるために使用。
- **型チェック:** `mypy` - 型アノテーションの静的解析に使用。
- **カバレッジ:** `pytest-cov` (pytestプラグイン) または `coverage.py` -
  テストカバレッジの計測に使用（目標80%以上）。

## **5. CI/CD (継続的インテグレーション/継続的デプロイ)**

- **プラットフォーム:** GitHub Actions (推奨) または Google Cloud Build。
- **パイプライン:**
  - Pull Request 作成時: 自動テスト (単体・結合)、型チェック (`mypy`)、リンター
    (`flake8` など、任意) を実行。
  - `main` ブランチへのマージ時: 上記テストに加え、Cloud Functions
    への自動デプロイを実行。

## **6. バージョン管理とブランチ戦略**

- **バージョン管理システム:** Git
- **リポジトリホスティング:** GitHub
- **バージョニング:** セマンティックバージョニング (SemVer) - `vX.Y.Z` 形式。
- **ブランチ戦略:** GitHub Flow - `main` ブランチとフィーチャーブランチを使用。
- **コミットメッセージ:** Conventional Commits 規約に従う。
- **リリース管理:** GitHub Releases を使用し、タグ付けと `CHANGELOG.md`
  の更新を行う。

## **7. セキュリティ**

- **機密情報:** Slack API トークン等は Google Cloud Secret Manager
  で管理し、Cloud Functions 実行時に環境変数として安全に読み込む。
- **通信:** 外部へのHTTPリクエスト (MHLWサイト、Slack API) は HTTPS を使用する。
- **依存関係:** 定期的に依存ライブラリの脆弱性情報を確認し、必要に応じて更新する
  (`pip-audit` などのツール利用を検討)。

## **8. クラウドプラットフォーム (GCP)**

- **Cloud Functions (Gen 2):** ボットの実行基盤。
- **Cloud Scheduler:** 定期実行トリガー。
- **Cloud Storage (GCS):** 既知URLリストの永続化。
- **Secret Manager:** 機密情報管理。
- **Cloud Logging:** ログ収集・分析。
- **Cloud Monitoring:** パフォーマンス監視、アラート設定。
