# さくらインターネット API監視システム

## 概要

さくらインターネットの公式APIを使用して、メンテナンス・障害情報を監視し、Slackに通知するシステムです。

## 機能

### 🔍 監視機能
- **APIベースの監視**: 公式API (`https://help.sakura.ad.jp/maint/api/v1/feeds/`) を使用
- **リアルタイム検出**: 今日以降のイベントを正確に検出
- **終了時間考慮**: 障害は継続中または未来のもののみ通知

### 📢 通知ルール
- **メンテナンス通知**: 毎日初回のみ送信、同日内の重複は送信しない
- **障害通知**: 継続中または未来の障害のみ通知
- **URL情報付き**: 各イベントの詳細ページへのリンクを含む

### 🎯 監視対象サービス
- **さくらのレンタルサーバー** (`rs`)
- **さくらのクラウド** (`cloud`)
- **さくらのIoT** (`iot`)
- **ドメイン・SSL** (`domainssl`)

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
├── sakura_checker.py              # メインスクリプト（API版）
├── find_services.py               # サービス名検索ユーティリティ
├── requirements.txt               # Python依存関係
├── notification_sent.json         # 通知履歴（自動生成・7日間保持）
└── README.md                      # このファイル
```

## 通知詳細

### 🎨 Slack通知形式

**メンテナンス通知例:**
```
[さくらのクラウド] メンテナンス情報があります（10件）

📋 詳細情報:
1. [メンテナンス] さくらのクラウド 石狩第2ゾーン ネットワークメンテナンス
2. [メンテナンス] さくらのクラウド(ウェブアクセラレータ)
... 他8件
```

**障害通知例:**
```
🔴 @here [さくらのクラウド] 障害情報があります

📋 詳細情報:
1. [障害] さくらのクラウド 石狩第2ゾーン SSDプランストレージ
```

### 📅 重複制御仕様

- **毎日リセット**: 午前0時（JST）に重複チェックがリセット
- **初回通知**: その日の最初の検出時に全情報を通知
- **重複スキップ**: 同日内の同一サービス・タイプは通知をスキップ
- **自動クリーンアップ**: 7日前より古い履歴を自動削除

## 環境変数

- `SLACK_WEBHOOK_URL`: Slack Webhook URL
- `AUTO_MODE`: 自動実行モードフラグ（'1'で有効）

## ログ

GitHub Actionsの実行ログは以下で確認できます：
- リポジトリ → Actions → Sakura Internet Status Monitor

## API仕様

### 🔌 エンドポイント
- **ベースURL**: `https://help.sakura.ad.jp/maint/api/v1/feeds/`
- **パラメータ**:
  - `service`: サービス識別子 (`rs`, `cloud`, `iot`, `domainssl`)
  - `type`: イベントタイプ (`maint`, `trouble`)
  - `ordering`: ソート順 (`event_start`)
  - `limit`: 取得件数 (最大100)

### 🕐 時刻処理
- **入力形式**: UNIXタイムスタンプ（秒）
- **表示形式**: JST（日本標準時）
- **フィルタ基準**: 今日（JST）の0:00以降

## バージョン履歴

### v2.0.0（最新）- API版
- **重要**: HTML解析からAPI利用に完全移行
- 終了時間を考慮した障害フィルタリング
- URL情報付きSlack通知
- 毎日単位での重複制御
- 自動履歴クリーンアップ（7日間）

### v1.x - HTML解析版（廃止）
- ステータスページのHTML解析
- メンテナンスモード検出

## トラブルシューティング

### よくある問題

1. **Slack通知が送信されない**
   - `SLACK_WEBHOOK_URL`が正しく設定されているか確認
   - GitHub Secretsの設定を確認
   - Webhook URLの有効期限を確認

2. **通知の重複/スキップ**
   - 毎日0:00（JST）にリセットされる仕様
   - `notification_sent.json`の内容を確認
   - 手動リセットが必要な場合はファイルを削除

3. **API接続エラー**
   - さくらインターネットAPI (`help.sakura.ad.jp`) への接続を確認
   - GitHub ActionsのネットワークからAPIにアクセス可能か確認

4. **GitHub Actions実行エラー**
   - Actionsタブでエラーログを確認
   - Python 3.11環境での動作を確認
   - 依存パッケージ (`requests`, `beautifulsoup4`) のインストール状況を確認

### デバッグ方法

```bash
# ローカルでテスト実行（通知なし）
export SLACK_WEBHOOK_URL=dummy
echo "2" | python sakura_checker.py

# 通知履歴の確認
cat notification_sent.json

# 通知履歴のリセット（必要に応じて）
echo '{}' > notification_sent.json
```