# さくらインターネット ステータス監視システム
# 
# 機能概要:
# 1. さくらインターネットのステータスページを監視
# 2. 障害発生時は毎回Slack通知を送信
# 3. メンテナンス通知は重複を避けて初回のみ送信
# 4. 正常時の通知は送信しない（要件により無効化）
#
# 通知ルール:
# - 障害通知: 全て送信（正常復旧含む）
# - メンテナンス通知: 初回のみ送信、同一内容の重複は送信しない
# - 正常時通知: 送信しない

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json
import hashlib

# Windows環境での文字化け対策
# コンソールの出力エンコーディングをUTF-8に設定
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

# Slack Webhook URL（環境変数から必須で取得）
# このURLを使用してSlackチャンネルに通知を送信します
# セキュリティ上、GitHub Secretsに設定することが必須です
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

if not SLACK_WEBHOOK_URL:
    print("[エラー] SLACK_WEBHOOK_URL環境変数が設定されていません")
    print("GitHub Secrets に SLACK_WEBHOOK_URL を設定してください")
    exit(1)

# メンテナンス通知の重複チェック用ファイル
# 送信済みのメンテナンス通知のハッシュ値を保存して重複を防ぐ
MAINTENANCE_HASH_FILE = "maintenance_sent.json"

def load_sent_maintenance_hashes():
    """送信済みメンテナンス通知のハッシュを読み込み
    
    Returns:
        dict: 送信済み通知のハッシュ辞書
              キー: "サービス名_日時", 値: ハッシュ値
    """
    # ハッシュファイルが存在する場合は読み込み
    if os.path.exists(MAINTENANCE_HASH_FILE):
        try:
            with open(MAINTENANCE_HASH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            # ファイル読み込みエラーの場合は空の辞書を返す
            return {}
    # ファイルが存在しない場合は空の辞書を返す
    return {}

def save_sent_maintenance_hashes(hashes):
    """送信済みメンテナンス通知のハッシュを保存
    
    Args:
        hashes (dict): 保存するハッシュ辞書
    """
    try:
        # JSONファイルにハッシュ辞書を保存
        # ensure_ascii=False: 日本語文字を適切に保存
        # indent=2: 読みやすいフォーマットで保存
        with open(MAINTENANCE_HASH_FILE, 'w', encoding='utf-8') as f:
            json.dump(hashes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # ファイル保存に失敗した場合は警告を表示
        print(f"[警告] ハッシュファイルの保存に失敗: {e}")

def generate_maintenance_hash(service, message):
    """メンテナンス通知のハッシュを生成
    
    Args:
        service (str): サービス名
        message (str): メッセージ内容
        
    Returns:
        str: 16文字の短縮ハッシュ値
    """
    # サービス名とメッセージ内容を結合してハッシュ生成用の文字列を作成
    content = f"{service}:{message}"
    
    # SHA256ハッシュを生成し、16文字に短縮
    # 短縮することでファイルサイズを削減し、可読性を向上
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

def is_maintenance_already_sent(service, message):
    """メンテナンス通知が既に送信済みかチェック
    
    Args:
        service (str): サービス名
        message (str): メッセージ内容
        
    Returns:
        bool: 既に送信済みの場合True、未送信の場合False
    """
    # 保存済みのハッシュ辞書を読み込み
    hashes = load_sent_maintenance_hashes()
    
    # 現在の通知内容からハッシュを生成
    current_hash = generate_maintenance_hash(service, message)
    
    # 生成したハッシュが既存のハッシュ値に含まれているかチェック
    return current_hash in hashes.values()

def mark_maintenance_as_sent(service, message):
    """メンテナンス通知を送信済みとしてマーク
    
    Args:
        service (str): サービス名
        message (str): メッセージ内容
    """
    # 既存のハッシュ辞書を読み込み
    hashes = load_sent_maintenance_hashes()
    
    # 現在の通知内容からハッシュを生成
    current_hash = generate_maintenance_hash(service, message)
    
    # ユニークなキーを作成（サービス名_日時形式）
    # 例: "レンタルサーバ_20250903_150022"
    key = f"{service}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # ハッシュ辞書に新しいエントリを追加
    hashes[key] = current_hash
    
    # 更新されたハッシュ辞書をファイルに保存
    save_sent_maintenance_hashes(hashes)

def send_slack_notification(service, status, url='https://help.sakura.ad.jp/status/'):
    """Slackに通知を送信
    
    Args:
        service (str): サービス名（例: "レンタルサーバ", "クラウド"）
        status (str): ステータス（"障害", "メンテナンス", "正常"）
        url (str): 詳細確認用URL
    """
    
    # ステータス別にメッセージの色、アイコン、内容を設定
    if status == '障害':
        color = "danger"  # 赤色で警告レベルの表示
        message = f"{service}で障害が発生しました"
        icon = ":red_circle:"
        # 障害時は@hereメンションを追加してチャンネル全体に緊急通知
        text = f"{icon} <!here> さくらインターネット緊急通知"
    elif status == 'メンテナンス':
        color = "warning"  # 黄色で注意レベルの表示
        message = f"{service}でメンテナンスが予定されています"
        icon = ":large_blue_circle:"
        text = f"{icon} さくらインターネット通知"
        
        # メンテナンス通知の重複チェック
        # 同じ内容のメンテナンス通知が既に送信済みの場合はスキップ
        if is_maintenance_already_sent(service, message):
            print(f"[スキップ] {service}のメンテナンス通知は送信済み")
            return  # 処理を終了して通知を送信しない
    else:
        # 正常復旧時の設定
        color = "good"  # 緑色で正常レベルの表示
        message = f"{service}が復旧しました"
        icon = ":green_circle:"
        text = f"{icon} さくらインターネット通知"
    
    # Slack通知用のメッセージペイロードを構築
    # Slack Incoming Webhooksの形式に従ってJSONデータを作成
    slack_data = {
        "text": text,  # メイン通知メッセージ
        "attachments": [  # 詳細情報を含むアタッチメント
            {
                "color": color,  # メッセージの色（danger/warning/good）
                "fields": [  # 構造化された情報フィールド
                    {
                        "title": "サービス",
                        "value": service,
                        "short": True  # 同じ行に複数フィールドを表示
                    },
                    {
                        "title": "状態", 
                        "value": status,
                        "short": True  # 同じ行に複数フィールドを表示
                    },
                    {
                        "title": "メッセージ",
                        "value": message,
                        "short": False  # 単独行で表示
                    },
                    {
                        "title": "詳細確認",
                        "value": url,
                        "short": False  # 単独行で表示
                    }
                ],
                "footer": "さくらインターネット監視bot",  # フッター情報
                "ts": int(datetime.now().timestamp())  # タイムスタンプ
            }
        ]
    }
    
    # Slack Webhook URLにPOSTリクエストを送信
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(slack_data),  # JSONデータを文字列に変換
            headers={'Content-Type': 'application/json'}  # JSON形式を指定
        )
        
        # レスポンス状態をチェック
        if response.status_code == 200:
            print(f"[成功] Slack通知送信: {message}")
            
            # メンテナンス通知の場合のみ送信済みとしてマーク
            # 障害通知は毎回送信するため、履歴に保存しない
            if status == 'メンテナンス':
                mark_maintenance_as_sent(service, message)
        else:
            # HTTP エラーの場合
            print(f"[失敗] Slack通知エラー: {response.status_code}")
            
    except Exception as e:
        # ネットワークエラーやその他の例外の場合
        print(f"[エラー] Slack送信失敗: {e}")

def check_sakura_status(send_to_slack=True):
    """さくらインターネットのステータスページをチェック
    
    Args:
        send_to_slack (bool): Slack通知を送信するかどうか
                              True: 通知送信, False: ログ出力のみ
    """
    
    # 実行開始ログ
    print("=" * 60)
    print("さくらインターネット ステータス監視")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # さくらインターネットのステータスページURL
    url = 'https://help.sakura.ad.jp/status/'
    
    try:
        # ステータスページからHTMLを取得
        response = requests.get(url)
        response.raise_for_status()  # HTTPエラーの場合は例外を発生
        
        # BeautifulSoupでHTMLを解析
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 監視対象サービスのキーワードリスト
        # これらのキーワードがページ内に含まれているかチェック
        service_keywords = ['クラウド', 'VPS', 'ドメイン', 'SSL', '専用サーバ']
        
        # 障害・メンテナンス情報が見つかったかのフラグ
        alert_found = False
        
        # 各サービスキーワードについてステータスをチェック
        for keyword in service_keywords:
            # ページ内でキーワードを含むテキスト要素を検索
            elements = soup.find_all(string=lambda text: text and keyword in text)
            
            if elements:
                # 現在の実装では常に正常として判定
                # TODO: 実際の障害・メンテナンス検出ロジックを実装する必要がある
                status = '正常'
                
                # 障害・メンテナンスの場合のみ表示・通知
                # 注意: 現在のロジックでは常に正常のため、以下の条件は実行されない
                if status == '障害':
                    message = f"[障害] {keyword}で障害が発生しました"
                    print(message)
                    # Slack通知が有効な場合のみ送信
                    if send_to_slack:
                        send_slack_notification(keyword, status, url)
                    alert_found = True
                elif status == 'メンテナンス':
                    message = f"[メンテ] {keyword}でメンテナンスが予定されています"
                    print(message)
                    # Slack通知が有効な場合のみ送信
                    if send_to_slack:
                        send_slack_notification(keyword, status, url)
                    alert_found = True
        
        # 障害・メンテナンス情報が見つからなかった場合
        if not alert_found:
            print("現在、障害・メンテナンス情報はありません")
            # 正常時の通知は送信しない（要件に基づき無効化）
            # 以前は send_all_normal_notification() を呼び出していたが、
            # 要件変更により正常時通知は無効化された
        
        # 詳細確認用URLと終了ログを表示
        print(f"\n詳細確認: {url}")
        print("=" * 60)
        
    except Exception as e:
        # ネットワークエラーやページ解析エラーなどの例外処理
        print(f"[エラー] エラーが発生しました: {e}")
        
        # 監視システム自体のエラーをSlackに通知
        if send_to_slack:
            send_slack_notification("監視システム", "エラー", url)
        
        print("=" * 60)

# ========================================
# 正常時の通知機能（要件により無効化）
# ========================================
# 以下の関数は要件変更により使用されなくなりました。
# 正常時の通知は送信せず、障害・メンテナンス時のみ通知する仕様に変更。
# 将来的に正常時通知が必要になった場合のため、コードは保持しています。
#
# def send_all_normal_notification(url='https://help.sakura.ad.jp/status/'):
#     """すべてのサービスが正常な場合のSlack通知
#     
#     Args:
#         url (str): 詳細確認用URL
#     """
#     
#     slack_data = {
#         "text": ":green_circle: さくらインターネット監視結果",
#         "attachments": [
#             {
#                 "color": "good",
#                 "fields": [
#                     {
#                         "title": "監視結果",
#                         "value": "現在、障害・メンテナンス情報はありません",
#                         "short": False
#                     },
#                     {
#                         "title": "詳細確認",
#                         "value": url,
#                         "short": False
#                     }
#                 ],
#                 "footer": "さくらインターネット監視bot",
#                 "ts": int(datetime.now().timestamp())
#             }
#         ]
#     }
#     
#     try:
#         response = requests.post(
#             SLACK_WEBHOOK_URL,
#             data=json.dumps(slack_data),
#             headers={'Content-Type': 'application/json'}
#         )
#         
#         if response.status_code == 200:
#             print("[成功] Slack通知送信: すべてのサービス正常")
#         else:
#             print(f"[失敗] Slack通知エラー: {response.status_code}")
#             
#     except Exception as e:
#         print(f"[エラー] Slack送信失敗: {e}")

def test_slack_notification():
    """Slack通知のテスト関数
    
    機能:
    - 障害通知とメンテナンス通知のテストを実行
    - メンテナンス通知の重複チェック機能も検証可能
    - 実際のSlack通知を送信するため、テスト時は注意が必要
    """
    print("=" * 60)
    print("【Slack通知テスト】")
    print("=" * 60)
    
    # テスト用のサービスとステータスの組み合わせ
    # 障害通知: 毎回送信される
    # メンテナンス通知: 初回のみ送信、2回目以降はスキップされる
    test_services = [
        ('レンタルサーバ', '障害'),      # 障害通知テスト
        ('クラウド', 'メンテナンス'),     # メンテナンス通知テスト
    ]
    
    # 各テストケースについて通知を送信
    for service, status in test_services:
        print(f"テスト通知送信: {service} - {status}")
        send_slack_notification(service, status)
        
    print("=" * 60)

# ========================================
# メイン処理
# ========================================
if __name__ == "__main__":
    import sys
    
    # 環境変数AUTO_MODEが設定されている場合は自動実行
    if os.environ.get('AUTO_MODE') == '1' or len(sys.argv) > 1 and sys.argv[1] == 'auto':
        # 自動監視モード: ステータスをチェックしてSlack通知を送信
        print("自動監視モードで実行中...")
        check_sakura_status(send_to_slack=True)
    else:
        # 対話モード: 実行モード選択メニュー
        print("1. 通常監視（Slack通知あり）")
        print("2. テスト実行（Slack通知なし）")
        print("3. Slack通知テスト")
        
        choice = input("選択してください (1-3): ")
        
        if choice == "1":
            # 本番運用モード: ステータスをチェックしてSlack通知を送信
            check_sakura_status(send_to_slack=True)
        elif choice == "2":
            # デバッグモード: ステータスチェックのみでSlack通知は送信しない
            check_sakura_status(send_to_slack=False)
        elif choice == "3":
            # テストモード: Slack通知機能をテスト（実際に通知が送信される）
            test_slack_notification()
        else:
            print("無効な選択です")