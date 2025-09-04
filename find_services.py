#!/usr/bin/env python3
# 実際のページに含まれるサービス名を検索

import requests
from bs4 import BeautifulSoup
import os
import re

# Windows文字化け対策
if os.name == 'nt':
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

def find_actual_services():
    url = 'https://help.sakura.ad.jp/status/'
    print(f"実際のサービス名を検索: {url}")
    print("=" * 60)
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ページ全体のテキストを取得
        page_text = soup.get_text()
        
        print("1. ページ内でさくら関連のサービス名を検索:")
        print("-" * 40)
        
        # さくら関連のパターンを検索
        sakura_patterns = [
            r'さくら[のん][^\s]*',  # さくらのXXX or さくらんXXX
            r'ドメイン[^s]*',       # ドメインXXX
            r'レンタル[^s]*',       # レンタルXXX
            r'クラウド[^s]*',       # クラウドXXX
            r'IoT[^s]*',           # IoTXXX
            r'VPS[^s]*',           # VPSXXX
            r'SSL[^s]*',           # SSLXXX
        ]
        
        found_services = set()
        for pattern in sakura_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                cleaned = match.strip()[:30]  # 30文字に制限
                if len(cleaned) > 2:  # 2文字以上のもの
                    found_services.add(cleaned)
        
        if found_services:
            print("発見されたサービス名:")
            for i, service in enumerate(sorted(found_services), 1):
                print(f"  {i:2d}. '{service}'")
        else:
            print("さくら関連のサービス名が見つかりませんでした")
        
        print(f"\n2. 'メンテナンス' や '障害' を含むテキストを検索:")
        print("-" * 40)
        
        # メンテナンス・障害関連テキストを検索
        maintenance_patterns = [
            r'.{0,50}メンテナンス.{0,50}',
            r'.{0,50}障害.{0,50}',
            r'.{0,30}予定.{0,30}',
        ]
        
        maintenance_found = set()
        for pattern in maintenance_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip().replace('\n', ' ').replace('\t', ' ')
                if len(cleaned) > 5:  # 5文字以上
                    maintenance_found.add(cleaned[:100])  # 100文字制限
        
        if maintenance_found:
            print("メンテナンス・障害関連テキスト:")
            for i, text in enumerate(sorted(maintenance_found)[:10], 1):  # 最初の10件
                print(f"  {i:2d}. '{text}'")
        else:
            print("メンテナンス・障害関連のテキストが見つかりませんでした")
            
        print(f"\n3. ページタイトルの確認:")
        print("-" * 40)
        title = soup.find('title')
        if title:
            print(f"タイトル: '{title.get_text().strip()}'")
        else:
            print("タイトルが見つかりませんでした")
        
        print(f"\n4. ページ内の全テキスト（最初の500文字）:")
        print("-" * 40)
        print(f"'{page_text[:500]}...'")
        
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    find_actual_services()