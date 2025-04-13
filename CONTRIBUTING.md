# コントリビューションガイドライン

このプロジェクトへの貢献に関心をお寄せいただきありがとうございます。

## コミットメッセージ規約

本プロジェクトでは、コミットメッセージの規約として
[Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/)
を採用しています。これにより、変更履歴の可読性が向上し、CHANGELOG
の自動生成などが可能になります。

**フォーマット:**

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**主な `<type>`:**

- `feat`: 新機能の追加
- `fix`: バグ修正
- `docs`: ドキュメントのみの変更
- `style`:
  コードの意味に影響しない変更（空白、フォーマット、セミコロン欠落など）
- `refactor`: バグ修正でも機能追加でもないコード変更
- `perf`: パフォーマンスを向上させるコード変更
- `test`: 不足しているテストの追加や既存テストの修正
- `build`: ビルドシステムや外部依存関係に影響する変更（例: pip, npm）
- `ci`: CI設定ファイルやスクリプトの変更（例: GitHub Actions）
- `chore`: 上記以外の変更（例: .gitignore の更新）

**例:**

```
feat: PDFリンク抽出機能を追加

厚生労働省のHTMLからPDFファイルへのリンクを抽出するパーサーを実装しました。
クエリパラメータ付きのリンクにも対応しています。

Refs #12
```

```
fix: GCS書き込みエラー時の処理を修正

GCSへの書き込みに失敗した場合でも、関数が異常終了しないように修正しました。
エラーはログに記録され、管理者に通知されます。

Close #25
```

## バージョニング

本プロジェクトでは、[セマンティックバージョニング (SemVer)](https://semver.org/lang/ja/)
2.0.0 を採用しています。

**フォーマット:** `MAJOR.MINOR.PATCH`

- **MAJOR:** 互換性のないAPI変更があった場合
- **MINOR:** 後方互換性のある機能追加があった場合
- **PATCH:** 後方互換性のあるバグ修正があった場合

リリース時には、GitHub Releases
を使用して適切なバージョンタグを付与し、`CHANGELOG.md` を更新します。

## ブランチ戦略

本プロジェクトでは
[GitHub Flow](https://docs.github.com/ja/get-started/quickstart/github-flow)
を採用しています。

1. `main` ブランチから作業用のフィーチャーブランチを作成します
   (`feat/add-parser`, `fix/handle-network-error` など)。
2. フィーチャーブランチで開発を行い、Conventional Commits
   に従ってコミットします。
3. 作業が完了したら、`main` ブランチへの Pull Request を作成します。
4. コードレビューと自動テスト (CI) を経て、Pull Request をマージします。
5. `main` ブランチへのマージ後、必要に応じてリリースが行われます。
