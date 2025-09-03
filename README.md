# さくらインターネット ステータス監視システム

## 概要

さくらインターネットのステータスページを監視し、障害やメンテナンス情報をSlackに通知するシステムです。

## 機能

### 通知ルール
- **障害通知**: 全て送信（正常復旧含む）
- **メンテナンス通知**: 初回のみ送信、同一内容の重複は送信しない
- **正常時通知**: 送信しない

### 監視対象サービス
- クラウド
- VPS
- ドメイン
- SSL
- 専用サーバ

## セットアップ

### GitHub Actionsでの自動実行

1. **GitHub Secretsの設定**
   - リポジトリの Settings → Secrets and variables → Actions
   - `SLACK_WEBHOOK_URL` に実際のSlack Webhook URLを設定

2. **実行頻度**
   - 毎時0分に自動実行（1時間間隔）
   - 手動実行も可能

### ローカル実行

#### 必要な環境
```bash
python >= 3.9
pip install -r requirements.txt
```

#### 実行方法
```bash
# 対話モード
python sakura_checker.py

# 自動実行モード
python sakura_checker.py auto

# 環境変数での制御
export AUTO_MODE=1
python sakura_checker.py
```

## ファイル構成

```
SAKURA_info/
├── .github/
│   └── workflows/
│       └── sakura-monitor.yml     # GitHub Actionsワークフロー
├── sakura_checker.py              # メインスクリプト
├── requirements.txt               # Python依存関係
├── maintenance_sent.json          # メンテナンス通知履歴（自動生成）
└── README.md                      # このファイル
```

## 環境変数

- `SLACK_WEBHOOK_URL`: Slack Webhook URL
- `AUTO_MODE`: 自動実行モードフラグ（'1'で有効）

## ログ

GitHub Actionsの実行ログは以下で確認できます：
- リポジトリ → Actions → Sakura Internet Status Monitor

## トラブルシューティング

### よくある問題

1. **Slack通知が送信されない**
   - `SLACK_WEBHOOK_URL`が正しく設定されているか確認
   - Webhookの権限を確認

2. **メンテナンス通知の重複**
   - `maintenance_sent.json`が正しく保存されているか確認
   - ファイル権限を確認

3. **GitHub Actions実行エラー**
   - Secretsが正しく設定されているか確認
   - ワークフローの構文を確認