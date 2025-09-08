#!/usr/bin/env python3
# さくらインターネット API監視システム
# 
# 機能概要:
# 1. さくらインターネットのメンテナンス・障害情報APIを利用
# 2. 各サービス（レンタルサーバー、クラウド、IoT、ドメイン・SSL）を監視
# 3. 今日以降のイベントのみを通知対象とする
# 4. 重複通知を防ぐハッシュベースシステム
#
# API仕様:
# - ベースURL: https://help.sakura.ad.jp/maint/api/v1/feeds/
# - パラメータ: service, type, ordering, limit
# - サービス: rs, cloud, iot, domainssl
# - タイプ: maint, trouble

import requests
from datetime import datetime, timezone, timedelta
import os
import json
import hashlib

# Windows環境での文字化け対策
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

# Slack Webhook URL（環境変数から取得）
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

if not SLACK_WEBHOOK_URL:
    print("[エラー] SLACK_WEBHOOK_URL環境変数が設定されていません")
    print("GitHub Secrets に SLACK_WEBHOOK_URL を設定してください")
    exit(1)

# 通知履歴保存ファイル
NOTIFICATION_HASH_FILE = "notification_sent.json"

# サービス定義
SERVICES = {
    'iot': 'さくらのIoT',
    'cloud': 'さくらのクラウド'
}

# イベントタイプ定義
EVENT_TYPES = {
    'maint': 'メンテナンス',
    'trouble': '障害'
}

def load_sent_notification_hashes():
    """送信済み通知のハッシュを読み込み
    
    Returns:
        dict: 送信済み通知のハッシュ辞書
    """
    if os.path.exists(NOTIFICATION_HASH_FILE):
        try:
            with open(NOTIFICATION_HASH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] ハッシュファイル読み込みエラー: {e}")
            return {}
    return {}

def save_sent_notification_hashes(hashes):
    """送信済み通知のハッシュを保存
    
    Args:
        hashes (dict): 保存するハッシュ辞書
    """
    try:
        with open(NOTIFICATION_HASH_FILE, 'w', encoding='utf-8') as f:
            json.dump(hashes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[警告] ハッシュファイル保存エラー: {e}")

def cleanup_old_notification_hashes():
    """古い通知履歴をクリーンアップ（7日前より古いものを削除）"""
    try:
        hashes = load_sent_notification_hashes()
        if not hashes:
            return
            
        jst = timezone(timedelta(hours=9))
        cutoff_date = datetime.now(jst) - timedelta(days=7)
        cutoff_str = cutoff_date.strftime('%Y%m%d')
        
        # 7日前より古いキーを削除
        keys_to_remove = []
        for key in hashes.keys():
            # キー形式: service_type_YYYYMMDD_HHMMSS
            parts = key.split('_')
            if len(parts) >= 4:
                date_str = parts[2]  # YYYYMMDD部分
                if date_str < cutoff_str:
                    keys_to_remove.append(key)
        
        if keys_to_remove:
            for key in keys_to_remove:
                del hashes[key]
            save_sent_notification_hashes(hashes)
            print(f"[クリーンアップ] {len(keys_to_remove)}件の古い通知履歴を削除")
            
    except Exception as e:
        print(f"[警告] 通知履歴クリーンアップエラー: {e}")

def generate_notification_hash(service, event_type, event_data):
    """通知のユニークハッシュを生成
    
    Args:
        service (str): サービス名
        event_type (str): イベントタイプ
        event_data (dict): イベントデータ
        
    Returns:
        str: ハッシュ値
    """
    # イベントの一意性を保つための文字列を作成
    unique_string = f"{service}:{event_type}:{event_data.get('id', '')}:{event_data.get('event_start', '')}"
    return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()[:16]

def is_notification_already_sent_today(service, event_type):
    """通知の重複チェック（メンテナンス：日単位、障害：時間単位）
    
    Args:
        service (str): サービス名
        event_type (str): イベントタイプ
        
    Returns:
        bool: 既に送信済みの場合True
    """
    hashes = load_sent_notification_hashes()
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    
    if event_type == 'trouble':
        # 障害：1時間単位でチェック（毎時重複送信OK）
        current_hour_str = now.strftime('%Y%m%d_%H')
        hour_key_prefix = f"{service}_{event_type}_{current_hour_str}"
        
        for key in hashes.keys():
            if key.startswith(hour_key_prefix):
                return True
    else:
        # メンテナンス：日単位でチェック（毎日初回のみ）
        today_str = now.strftime('%Y%m%d')
        today_key_prefix = f"{service}_{event_type}_{today_str}"
        
        for key in hashes.keys():
            if key.startswith(today_key_prefix):
                return True
    
    return False

def mark_notification_as_sent(service, event_type, event_data):
    """通知を送信済みとしてマーク
    
    Args:
        service (str): サービス名
        event_type (str): イベントタイプ
        event_data (dict): イベントデータ
    """
    hashes = load_sent_notification_hashes()
    current_hash = generate_notification_hash(service, event_type, event_data)
    
    # ユニークなキーを生成
    jst = timezone(timedelta(hours=9))
    key = f"{service}_{event_type}_{datetime.now(jst).strftime('%Y%m%d_%H%M%S')}"
    
    hashes[key] = current_hash
    save_sent_notification_hashes(hashes)

def send_slack_notification(service_name, event_type, event_count, events_data):
    """Slackに通知を送信
    
    Args:
        service_name (str): サービス名
        event_type (str): イベントタイプ（メンテナンス/障害）
        event_count (int): イベント数
        events_data (list): イベントデータのリスト
    """
    # メッセージ内容を作成
    if event_type == 'メンテナンス':
        color = "warning"  # 黄色
        icon = ":large_blue_circle:"
        if event_count == 1:
            message = f"[{service_name}] メンテナンス情報があります"
        else:
            message = f"[{service_name}] メンテナンス情報があります（{event_count}件）"
    else:  # 障害
        color = "danger"  # 赤色
        icon = ":red_circle:"
        if event_count == 1:
            message = f"[{service_name}] 障害情報があります"
        else:
            message = f"[{service_name}] 障害情報があります（{event_count}件）"
        # 障害時は@hereメンションを追加
        message = f"{icon} <!here> {message}"

    # JST時刻を取得
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)

    # イベントのURL情報を収集
    urls_text = ""
    if events_data:
        urls = []
        for i, event in enumerate(events_data[:5], 1):  # 最大5件まで表示
            title = event.get('title', 'タイトルなし')
            url = event.get('url', '')
            if url:
                # URLが長い場合は短縮表示
                if len(title) > 40:
                    title = title[:37] + "..."
                urls.append(f"{i}. <{url}|{title}>")
            else:
                urls.append(f"{i}. {title}")
        
        if urls:
            urls_text = "\n\n📋 *詳細情報:*\n" + "\n".join(urls)
            if len(events_data) > 5:
                urls_text += f"\n... 他{len(events_data) - 5}件"

    # Slack通知用のペイロードを作成
    slack_data = {
        "text": message + urls_text,
        "attachments": [
            {
                "color": color,
                "fields": [
                    {
                        "title": "サービス",
                        "value": service_name,
                        "short": True
                    },
                    {
                        "title": "種別",
                        "value": event_type,
                        "short": True
                    },
                    {
                        "title": "件数",
                        "value": str(event_count),
                        "short": True
                    },
                    {
                        "title": "確認時刻",
                        "value": now_jst.strftime('%Y-%m-%d %H:%M:%S JST'),
                        "short": True
                    }
                ],
                "footer": "さくらインターネット監視bot（API版）",
                "ts": int(now_jst.timestamp())
            }
        ]
    }

    # Slack Webhookに送信
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(slack_data),
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[成功] Slack通知送信: {message}")
        else:
            print(f"[失敗] Slack通知エラー: {response.status_code}")
            
    except Exception as e:
        print(f"[エラー] Slack送信失敗: {e}")

def fetch_api_data(service, event_type):
    """さくらインターネットAPIからデータを取得
    
    Args:
        service (str): サービス識別子（rs, cloud, iot, domainssl）
        event_type (str): イベントタイプ（maint, trouble）
        
    Returns:
        dict: APIレスポンス、エラー時はNone
    """
    api_url = f"https://help.sakura.ad.jp/maint/api/v1/feeds/"
    params = {
        'service': service,
        'type': event_type,
        'ordering': 'event_start',
        'limit': 100
    }
    
    try:
        print(f"[デバッグ] API呼び出し: {service} - {event_type}")
        response = requests.get(api_url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        print(f"[デバッグ] API結果: {len(data.get('results', []))}件取得")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"[エラー] API呼び出し失敗 ({service}-{event_type}): {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[エラー] JSONデコードエラー ({service}-{event_type}): {e}")
        return None
    except Exception as e:
        print(f"[エラー] 予期しないエラー ({service}-{event_type}): {e}")
        return None

def is_event_relevant(event_data, event_type):
    """イベントが通知対象かチェック
    
    Args:
        event_data (dict): イベントデータ
        event_type (str): イベントタイプ（maint, trouble）
        
    Returns:
        bool: 通知対象の場合True
    """
    try:
        event_start_str = event_data.get('event_start')
        event_end_str = event_data.get('event_end')
        
        if not event_start_str:
            return False
            
        # 石狩第2ゾーンのみのメンテナンス情報を除外（第1ゾーンも含む場合は通知）
        title = event_data.get('title', '')
        desc = event_data.get('desc', '')
        if ('石狩第2ゾーン' in title or '石狩第2ゾーン' in desc) and ('石狩第1ゾーン' not in title and '石狩第1ゾーン' not in desc):
            print(f"    [フィルタ] 石狩第2ゾーンのみのため除外: {title[:50]}...")
            return False
            
        # UNIXタイムスタンプの場合（文字列が数字のみ）
        if event_start_str.isdigit():
            event_start = datetime.fromtimestamp(int(event_start_str), tz=timezone.utc)
        else:
            # ISO形式の場合
            event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
        
        # 終了時刻も解析
        event_end = None
        if event_end_str:
            if event_end_str.isdigit():
                event_end = datetime.fromtimestamp(int(event_end_str), tz=timezone.utc)
            else:
                event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
        
        # JSTで現在時刻と今日の開始時刻を取得
        jst = timezone(timedelta(hours=9))
        now_jst = datetime.now(jst)
        today_start = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # イベント開始時刻をJSTに変換
        event_start_jst = event_start.astimezone(jst)
        
        # イベントタイプに応じた判定
        if event_type == 'trouble':  # 障害
            # 障害の場合：終了時刻が現在時刻より後（継続中または未来）
            if event_end:
                event_end_jst = event_end.astimezone(jst)
                is_relevant = event_end_jst > now_jst
                print(f"    [日時チェック] 障害 {event_start_str}〜{event_end_str} → 終了:{event_end_jst.strftime('%Y-%m-%d %H:%M:%S JST')} → 継続中/未来: {is_relevant}")
            else:
                # 終了時刻がない場合は開始時刻で判定
                is_relevant = event_start_jst >= today_start
                print(f"    [日時チェック] 障害 {event_start_str} → {event_start_jst.strftime('%Y-%m-%d %H:%M:%S JST')} → 今日以降: {is_relevant}")
        else:  # メンテナンス
            # メンテナンスの場合：開始時刻が今日以降（予告のため）
            is_relevant = event_start_jst >= today_start
            print(f"    [日時チェック] メンテナンス {event_start_str} → {event_start_jst.strftime('%Y-%m-%d %H:%M:%S JST')} → 今日以降: {is_relevant}")
        
        return is_relevant
        
    except Exception as e:
        print(f"[警告] 日時解析エラー: {event_data} - {e}")
        return False

def check_sakura_api_status(send_to_slack=True):
    """さくらインターネットAPIを使用してステータスをチェック
    
    Args:
        send_to_slack (bool): Slack通知を送信するかどうか
    """
    # 古い通知履歴をクリーンアップ
    cleanup_old_notification_hashes()
    
    # 実行開始ログ
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    
    print("=" * 60)
    print("さくらインターネット API監視システム")
    print(f"実行時刻: {now_jst.strftime('%Y-%m-%d %H:%M:%S')} JST")
    print("=" * 60)
    
    # 通知が発生したかのフラグ
    alert_found = False
    
    # 各サービス・イベントタイプについてチェック
    for service_id, service_name in SERVICES.items():
        print(f"\n[チェック] {service_name} ({service_id})")
        print("-" * 40)
        
        for event_type_id, event_type_name in EVENT_TYPES.items():
            print(f"  {event_type_name}情報を取得中...")
            
            # APIからデータを取得
            api_data = fetch_api_data(service_id, event_type_id)
            
            if api_data is None:
                print(f"    [警告] {event_type_name}情報の取得に失敗")
                continue
                
            # resultsから今日以降のイベントをフィルタ
            results = api_data.get('results', [])
            today_or_later_events = []
            
            for event in results:
                if is_event_relevant(event, event_type_id):
                    today_or_later_events.append(event)
                    event_start = event.get('event_start')
                    print(f"    [検出] ID:{event.get('id', 'N/A')} 開始:{event_start}")
            
            event_count = len(today_or_later_events)
            
            if event_count > 0:
                print(f"    [結果] {event_type_name}: {event_count}件の今日以降イベント")
                
                # 毎日単位での重複チェック
                if not is_notification_already_sent_today(service_id, event_type_id):
                    if send_to_slack:
                        send_slack_notification(service_name, event_type_name, event_count, today_or_later_events)
                        # 代表イベントでマーク（従来の仕様を維持）
                        representative_event = today_or_later_events[0]
                        mark_notification_as_sent(service_id, event_type_id, representative_event)
                    alert_found = True
                else:
                    if event_type_id == 'trouble':
                        print(f"    [スキップ] {event_type_name}通知はこの時間帯に送信済み")
                    else:
                        print(f"    [スキップ] {event_type_name}通知は今日既に送信済み")
            else:
                print(f"    [結果] {event_type_name}: 今日以降のイベントなし")
    
    # 総合結果
    if not alert_found:
        print(f"\n[結果] 現在、今日以降のメンテナンス・障害情報はありません")
    else:
        print(f"\n[結果] {alert_found}件の通知を送信しました")
    
    print("=" * 60)

def test_slack_notification():
    """Slack通知のテスト関数"""
    print("=" * 60)
    print("【Slack通知テスト】")
    print("=" * 60)
    
    # テスト用の通知
    test_cases = [
        ('さくらのレンタルサーバー', 'メンテナンス', 1),
        ('さくらのクラウド', '障害', 2),
    ]
    
    for service_name, event_type, count in test_cases:
        print(f"テスト通知送信: {service_name} - {event_type} ({count}件)")
        # テスト用のダミーイベントデータ
        test_events = [
            {
                'title': f'テスト{event_type}情報',
                'url': 'https://support.sakura.ad.jp/test/12345',
            }
        ]
        send_slack_notification(service_name, event_type, count, test_events)
        
    print("=" * 60)

def main():
    """メイン処理"""
    import sys
    
    # 環境変数AUTO_MODEが設定されている場合は自動実行
    if os.environ.get('AUTO_MODE') == '1' or len(sys.argv) > 1 and sys.argv[1] == 'auto':
        print("自動監視モードで実行中...")
        check_sakura_api_status(send_to_slack=True)
    else:
        # 対話モード
        print("1. 通常監視（Slack通知あり）")
        print("2. テスト実行（Slack通知なし）") 
        print("3. Slack通知テスト")
        
        choice = input("選択してください (1-3): ")
        
        if choice == "1":
            check_sakura_api_status(send_to_slack=True)
        elif choice == "2":
            check_sakura_api_status(send_to_slack=False)
        elif choice == "3":
            test_slack_notification()
        else:
            print("無効な選択です")

if __name__ == "__main__":
    main()