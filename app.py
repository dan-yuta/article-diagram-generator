#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
記事図解ジェネレーター - オールインワンアプリ
このスクリプト1つでサーバーとブラウザを起動します
"""

import os
import sys
import subprocess

# 依存パッケージを最初にインストール
def install_dependencies():
    """依存パッケージのインストール"""
    required = {
        'anthropic': 'anthropic',
        'requests': 'requests',
        'bs4': 'beautifulsoup4'
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print("\n必要なパッケージをインストールしています...")
        print(f"パッケージ: {', '.join(missing)}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
        print("✓ インストール完了\n")

# 依存パッケージをインストール
install_dependencies()

# インストール後に必要なモジュールをインポート
import re
import json
import webbrowser
import time
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import anthropic
import requests
from bs4 import BeautifulSoup

# グローバル変数
ANTHROPIC_API_KEY = None
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"

# 出力ディレクトリを作成
OUTPUT_DIR.mkdir(exist_ok=True)


class DiagramHandler(SimpleHTTPRequestHandler):
    """リクエストハンドラー"""

    def do_GET(self):
        """GETリクエストの処理"""
        print(f"\n[GET] リクエスト: {self.path}")

        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()

            # index.htmlを読み込んで送信
            index_path = BASE_DIR / 'ui' / 'index.html'
            with open(index_path, 'r', encoding='utf-8') as f:
                self.wfile.write(f.read().encode('utf-8'))
        elif self.path.startswith('/open_file/'):
            # ファイルを開くリクエスト
            from urllib.parse import unquote
            encoded_name = self.path.replace('/open_file/', '')
            file_name = unquote(encoded_name)
            file_path = (OUTPUT_DIR / file_name).resolve()

            # パストラバーサル防止
            if not str(file_path).startswith(str(OUTPUT_DIR.resolve())):
                self.send_response(403)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Access denied'}).encode('utf-8'))
                return

            print(f"\n========== ファイルを開く処理 ==========")
            print(f"1. エンコード済みパス: {encoded_name}")
            print(f"2. デコード後のファイル名: {file_name}")
            print(f"3. フルパス: {file_path}")
            print(f"4. OUTPUT_DIR: {OUTPUT_DIR}")
            print(f"5. ファイル存在チェック: {file_path.exists()}")

            # デバッグ: フォルダ内のファイル一覧
            if not file_path.exists():
                print(f"\n⚠️ ファイルが見つかりません！")
                print(f"フォルダ内のファイル一覧:")
                import os
                for f in os.listdir(OUTPUT_DIR):
                    print(f"  - {f}")
                    if file_name in f or f in file_name:
                        print(f"    ↑ 部分一致")
            print(f"==========================================\n")

            if file_path.exists():
                # ファイルをデフォルトブラウザで開く
                print(f"✓ ファイルが見つかりました。ブラウザで開きます...")
                webbrowser.open(f'file:///{file_path}')

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'opened', 'file': str(file_path)}).encode('utf-8'))
            else:
                print(f"✗ ファイルが見つかりません: {file_path}")
                self.send_response(404)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'File not found', 'path': str(file_path)}).encode('utf-8'))
        else:
            # 静的ファイルはデフォルトの処理
            super().do_GET()

    def do_POST(self):
        """POSTリクエストの処理"""
        if self.path == '/shutdown':
            # サーバー停止リクエスト
            print("\n\n⚠️  シャットダウン要求を受信しました...")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'shutting down'}).encode('utf-8'))

            # サーバーを停止
            print("✓ サーバーを停止します...\n")
            threading.Thread(target=lambda: os._exit(0)).start()

        elif self.path == '/generate':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
            except (ValueError, TypeError):
                self.send_error_response('不正なリクエストです')
                return
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            url = data.get('url', '')
            text = data.get('text', '')

            try:
                # URLが指定されている場合は記事を取得
                if url:
                    print(f"\n記事を取得中: {url}")
                    text = fetch_article(url)
                    if not text:
                        self.send_error_response('記事の取得に失敗しました')
                        return
                    print(f"✓ 記事を取得しました ({len(text)}文字)")

                if not text:
                    self.send_error_response('テキストが空です')
                    return

                # Claude APIで図解HTMLを生成
                print("\nClaude APIで図解を生成中...")
                diagram_html = generate_diagram(text)
                print("✓ 図解の生成が完了しました")

                # ファイル名を生成
                file_name = generate_filename(text)

                # ファイルパスを生成
                file_path = OUTPUT_DIR / file_name

                print(f"\n保存先情報:")
                print(f"  OUTPUT_DIR: {OUTPUT_DIR}")
                print(f"  file_name: {file_name}")
                print(f"  file_path: {file_path}")

                # HTMLファイルを保存
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(diagram_html)

                print(f"✓ ファイルを保存しました: {file_path}\n")

                # 成功レスポンスを返す
                self.send_success_response({
                    'file_path': str(file_path),
                    'file_name': file_name
                })

            except Exception as e:
                print(f"\n✗ エラーが発生しました: {e}\n")
                self.send_error_response(str(e))
        else:
            self.send_error(404)

    def send_success_response(self, data):
        """成功レスポンスを送信"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_error_response(self, error_message):
        """エラーレスポンスを送信"""
        self.send_response(400)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'error': error_message}, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """ログを簡潔に出力"""
        return  # ログを無効化


def fetch_article(url):
    """URLから記事を取得"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # 不要なタグを削除
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        # 記事本文を取得
        article_tags = ['article', 'main', '[role="main"]']
        article_text = ''

        for tag in article_tags:
            if tag.startswith('['):
                elements = soup.select(tag)
            else:
                elements = soup.find_all(tag)

            if elements:
                article_text = elements[0].get_text(separator='\n', strip=True)
                break

        # articleタグが見つからない場合はbodyから取得
        if not article_text:
            body = soup.find('body')
            if body:
                article_text = body.get_text(separator='\n', strip=True)

        # 連続する空白行を削除
        article_text = re.sub(r'\n\s*\n', '\n\n', article_text)

        return article_text.strip()
    except Exception as e:
        print(f"記事の取得エラー: {e}")
        return None


TEMPLATE_DIR = BASE_DIR / "references"


def get_html_template():
    """references/base.htmlからHTMLテンプレートを読み込む"""
    template_path = TEMPLATE_DIR / "base.html"
    if not template_path.exists():
        raise FileNotFoundError(f"テンプレートファイルが見つかりません: {template_path}")
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_diagram(text):
    """Claude APIを使用して図解HTMLを生成"""
    if not ANTHROPIC_API_KEY:
        raise Exception('ANTHROPIC_API_KEY が設定されていません')

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""以下の記事を分析し、図解コンテンツ（HTMLの本文のみ）を生成してください。

## 出力形式
- <main>の中身だけを出力。<main>タグ自体も書かない。<div>から始めること
- <!DOCTYPE html>,<html>,<head>,<body>,<style>,<script>,<main>タグは一切書かない
- Tailwind CSSクラスでスタイリング（CDN読み込み済み）
- Lucide Icons使用可: <i data-lucide="icon-name" class="w-5 h-5 text-blue-600"></i>
- 絵文字も積極的に使う 🎯📌💡🔥⚠️✅❌🔰 など、見出し・カード・リスト・ボックスに入れて視覚的に

## カスタムカラー "ads"（定義済み）
bg-ads-surface(薄グレー), text-ads-text(#1E293B), text-ads-muted(#64748B), text-ads-dim(#94A3B8), text-ads-accent(#3B82F6), text-ads-accent-light(#2563EB), border-ads-border(#E2E8F0), text-ads-positive(緑), text-ads-negative(赤), text-ads-warning(黄)

## テキスト色ルール（絶対）
- bodyはtext-slate-600設定済み。見出しはtext-slate-900。強調は<strong class="text-slate-900">
- ⚠️ text-white は絶対に使用禁止。どんな背景でも使わない
- ⚠️ 濃い背景（bg-slate-900, bg-slate-800, bg-gradient-to-br from-slate-900 等）は使用禁止
- 背景は必ず薄い色（bg-xxx-500/5, bg-xxx-500/10, bg-xxx-50, bg-ads-surface等）を使う
- テキストは常に濃い色（text-slate-900, text-slate-700, text-xxx-800, text-xxx-900等）

## ★★★ 以下の3つは必ず含めること（省略厳禁）★★★

### 必須1: 📌 一言結論ボックス（ヒーロー直後に必ず配置）
記事全体の結論を1〜2文にまとめ、以下のHTMLで表示:
<div class="bg-ads-accent/5 border-2 border-ads-accent/30 rounded-2xl p-6 md:p-8 mb-12 text-center">
  <p class="text-xs text-ads-accent font-bold tracking-widest uppercase mb-3">📌 一言でいうと</p>
  <p class="text-xl md:text-2xl font-black text-slate-900 leading-relaxed">ここに結論を書く</p>
</div>

### 必須2: 📖 用語解説（難しい単語が出るたびに）
専門用語・地名・人名などが初出するとき、すぐ後ろに解説を入れる。方法は2つから選ぶ:
- インライン: 「ホルムズ海峡<span class="text-ads-muted text-sm">（中東の石油輸送の要所。封鎖されると世界の石油供給が止まる）</span>」
- 解説ボックス:
<div class="bg-amber-50 border border-amber-200 rounded-xl p-4 my-4">
  <p class="font-bold text-amber-800 mb-1">📖 用語解説</p>
  <p class="text-sm text-amber-700"><strong>ホルムズ海峡</strong> — 中東の石油輸送の要所。世界の石油の約20%がここを通る。封鎖されると石油価格が急騰し世界経済に大打撃を与える</p>
</div>

### 必須3: 🔰 かみ砕き解説（複雑な流れや因果関係のあとに）
難しい話のあとに、中学生でもわかる言葉で言い換えたボックスを入れる:
<div class="bg-blue-50 border border-blue-200 rounded-xl p-4 my-4">
  <p class="font-bold text-blue-800 mb-1">🔰 かみ砕くと...</p>
  <p class="text-sm text-blue-700">つまり「○○が△△したから、□□になった」ということ。例えるなら...</p>
</div>

## 使えるパターン（Tailwindクラスで自由に組む）
ヒーロー / セクション見出し / フロー図 / 比較カード / テーブル / 数字カード / ポイントボックス / カードグリッド / タイムライン

## 重要な制約
- セクション数は最大5〜6個に絞り、必ず最後まで書き切る
- HTMLコードはコンパクトに。同じ情報を繰り返さない
- 冗長なクラス指定やネストを避け、出力トークンを節約する

## 記事内容:
{text}

上記を分析し、<div>から始まるコンテンツHTMLのみを出力:"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=16000,
        extra_headers={"anthropic-beta": "output-128k-2025-02-19"},
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # トークン上限で途切れたかチェック
    stop_reason = message.stop_reason
    if stop_reason == 'max_tokens':
        print("⚠️  max_tokensに到達 — 生成が途中で切れた可能性があります")

    # レスポンスからコンテンツHTMLを抽出
    response_text = message.content[0].text

    # ```htmlタグで囲まれている場合は抽出
    html_match = re.search(r'```html\s*(.*?)\s*```', response_text, re.DOTALL)
    if html_match:
        content_html = html_match.group(1).strip()
    else:
        content_html = response_text.strip()

    # もし完全なHTML文書が返された場合、<main>の中身を抽出
    if '<!DOCTYPE html>' in content_html or '<html' in content_html:
        main_match = re.search(r'<main[^>]*>(.*?)</main>', content_html, re.DOTALL)
        if main_match:
            content_html = main_match.group(1).strip()

    # 生成HTMLのサニタイズ（テンプレートとの重複・禁止パターンを除去）
    content_html = sanitize_generated_html(content_html)

    # 途中で切れたHTMLの修復: 開いたままのタグを閉じる
    if stop_reason == 'max_tokens':
        content_html = repair_truncated_html(content_html)

    # タイトルを抽出（h1タグから）
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', content_html, re.DOTALL)
    if title_match:
        # HTMLタグを除去してプレーンテキストのタイトルを取得
        title_text = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    else:
        # h1がない場合は記事の最初の行をタイトルにする
        first_line = text.split('\n')[0] if text else '図解'
        title_text = first_line[:80]

    # テンプレートにコンテンツを埋め込む
    template = get_html_template()

    if '<!-- CONTENT_START -->' not in template or '<!-- CONTENT_END -->' not in template:
        raise Exception('テンプレートにCONTENT_START/CONTENT_ENDマーカーが見つかりません。references/base.htmlを確認してください')

    full_html = template.replace('<!-- TITLE -->', title_text)
    full_html = re.sub(
        r'<!-- CONTENT_START -->.*?<!-- CONTENT_END -->',
        f'<!-- CONTENT_START -->\n{content_html}\n<!-- CONTENT_END -->',
        full_html,
        flags=re.DOTALL
    )

    return full_html


def sanitize_generated_html(html):
    """生成されたHTMLからテンプレートと重複する要素や禁止パターンを除去する"""
    # <main>タグを除去（テンプレート側に<main>があるため二重ネスト防止）
    html = re.sub(r'<main[^>]*>', '', html)
    html = re.sub(r'</main>', '', html)

    # <script>タグを除去（テンプレート側で読み込み済み）
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)

    # 濃い背景クラスを薄い背景に置換
    dark_bg_replacements = [
        (r'bg-slate-900', 'bg-slate-100'),
        (r'bg-slate-800', 'bg-slate-100'),
        (r'bg-gradient-to-br\s+from-slate-900\s+via-slate-800\s+to-slate-900', 'bg-gradient-to-br from-slate-50 via-blue-50 to-slate-50'),
        (r'bg-gradient-to-br\s+from-slate-800\s+to-slate-900', 'bg-gradient-to-br from-slate-50 to-blue-50'),
        (r'bg-red-600\b', 'bg-red-500/10'),
    ]
    for pattern, replacement in dark_bg_replacements:
        html = re.sub(pattern, replacement, html)

    # text-white を text-slate-900 に置換
    html = re.sub(r'\btext-white\b', 'text-slate-900', html)

    # text-slate-50 を text-slate-900 に置換（ほぼ白色）
    html = re.sub(r'\btext-slate-50\b', 'text-slate-900', html)
    html = re.sub(r'\btext-slate-100\b', 'text-slate-800', html)
    html = re.sub(r'\btext-slate-200\b', 'text-slate-700', html)
    html = re.sub(r'\btext-slate-300\b', 'text-slate-600', html)

    # bg-white/10, bg-white/5 などの半透明白背景をしっかり見える色に
    html = re.sub(r'\bbg-white/10\b', 'bg-ads-surface', html)
    html = re.sub(r'\bbg-white/5\b', 'bg-ads-surface', html)

    # backdrop-blur は薄い背景では不要なので除去（-sm, -md等の派生も含む）
    html = re.sub(r'\bbackdrop-blur(?:-[a-z]+)?\b', '', html)

    return html


def repair_truncated_html(html):
    """max_tokensで途切れたHTMLの開きっぱなしのタグを閉じる"""
    # 自己閉じタグ（閉じる必要がないもの）
    void_tags = {'br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr'}

    # 開いたタグと閉じたタグをスタックで追跡
    open_tags = []
    tag_pattern = re.compile(r'<(/?)(\w+)(?:\s[^>]*)?\s*/?>')

    for match in tag_pattern.finditer(html):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()

        if tag_name in void_tags:
            continue

        if is_closing:
            # 対応する開きタグを探して除去
            for idx in range(len(open_tags) - 1, -1, -1):
                if open_tags[idx] == tag_name:
                    open_tags.pop(idx)
                    break
        else:
            open_tags.append(tag_name)

    # 開きっぱなしのタグを逆順に閉じる
    closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
    if closing_tags:
        print(f"  修復: {len(open_tags)}個の未閉じタグを補完しました")

    return html + closing_tags


def generate_filename(text):
    """テキストからファイル名を生成"""
    # タイトルっぽい部分を抽出
    lines = text.split('\n')
    title = lines[0] if lines else text[:100]

    # ファイル名に使えない文字を削除
    title = re.sub(r'[\\/:*?"<>|]', '', title)
    title = title.strip()[:50]

    # タイムスタンプを追加
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ファイル名を生成
    if title:
        filename = f"{title}_{timestamp}.html"
    else:
        filename = f"diagram_{timestamp}.html"

    return filename


def setup_api_key():
    """APIキーをセットアップ"""
    global ANTHROPIC_API_KEY

    # 環境変数から取得
    api_key = os.environ.get('ANTHROPIC_API_KEY')

    # config.txtから取得
    config_file = BASE_DIR / 'ui' / 'config.txt'
    if not api_key and config_file.exists():
        print("config.txtからAPIキーを読み込み中...")
        with open(config_file, 'r', encoding='utf-8') as f:
            api_key = f.read().strip()

    # APIキーがない場合は入力を促す
    if not api_key:
        print("\n" + "=" * 60)
        print("APIキーが設定されていません")
        print("=" * 60)
        print("\nAnthropic APIキーを取得してください:")
        print("https://console.anthropic.com/settings/keys")
        print()

        response = input("APIキーを入力しますか? (y/n): ")
        if response.lower() == 'y':
            api_key = input("APIキーを入力してください (sk-ant-...): ").strip()
            if api_key:
                # config.txtに保存
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write(api_key)
                print(f"\n✓ APIキーを {config_file} に保存しました")
            else:
                print("\n✗ APIキーが入力されませんでした")
                sys.exit(1)
        else:
            print("\nAPIキーを設定してから再度実行してください")
            sys.exit(1)

    ANTHROPIC_API_KEY = api_key
    return True


def main():
    """メイン関数"""
    print("\n" + "=" * 60)
    print("📊 記事図解ジェネレーター")
    print("=" * 60)

    # APIキーのセットアップ
    setup_api_key()

    print("\n✓ セットアップ完了")

    # デバッグ情報
    print(f"\nデバッグ情報:")
    print(f"  BASE_DIR: {BASE_DIR}")
    print(f"  OUTPUT_DIR: {OUTPUT_DIR}")
    print(f"  OUTPUT_DIR exists: {OUTPUT_DIR.exists()}")

    # サーバーを起動
    port = 8000
    server = HTTPServer(('localhost', port), DiagramHandler)

    print(f"\n🚀 サーバーを起動しました")
    print(f"   http://localhost:{port}")
    print(f"\n📂 図解の保存先:")
    print(f"   {OUTPUT_DIR}")
    print(f"\n💡 使い方:")
    print(f"   1. ブラウザで記事URLまたはテキストを入力")
    print(f"   2. 「図解を生成」ボタンをクリック")
    print(f"   3. 生成完了後、「図解を開く」ボタンをクリック")
    print(f"\n⚠️  終了するには Ctrl+C を押してください")
    print("=" * 60 + "\n")

    # ブラウザを別スレッドで開く
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://localhost:{port}/')

    threading.Thread(target=open_browser, daemon=True).start()

    # サーバーを起動
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n⚠️  サーバーを停止しています...")
        server.shutdown()
        print("✓ サーバーを停止しました\n")


if __name__ == '__main__':
    main()
