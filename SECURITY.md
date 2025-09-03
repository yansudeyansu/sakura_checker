# セキュリティガイドライン

## 重要な注意事項

⚠️ **Slack Webhook URLの取り扱い**

このリポジトリはパブリック（公開）のため、Slack Webhook URLを直接コードに含めることは**絶対に避けてください**。

## セットアップ手順

### 1. 新しいWebhook URLの取得

1. https://it-w0f2296.slack.com/services/B09D9FQ85V4 にアクセス
2. "Webhook URL" セクションまでスクロール
3. 新しいWebhook URLをコピー

### 2. GitHub Secretsの設定

1. **GitHubリポジトリ**で以下の手順を実行：
   - [Settings] → [Secrets and variables] → [Actions]
   - [New repository secret] をクリック
   - **Name**: `SLACK_WEBHOOK_URL`
   - **Value**: 新しいWebhook URL

### 3. ローカル実行用の環境変数設定

```bash
# Windows
set SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_NEW_URL

# macOS/Linux
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR_NEW_URL"
```

## セキュリティ対策

✅ **実装済み**:
- コードからWebhook URLを完全除去
- 環境変数での必須チェック
- GitHub Secretsでの安全な管理

❌ **してはいけないこと**:
- Webhook URLをコードに直接記述
- パブリックリポジトリでシークレット情報を公開
- Slackトークンをファイルに保存

## 緊急時の対応

もしWebhook URLが漏洩した場合：

1. **即座にSlackで該当Webhookを無効化**
2. **新しいWebhook URLを生成**
3. **GitHub Secretsを更新**
4. **Git履歴をクリーンアップ**（必要に応じて）