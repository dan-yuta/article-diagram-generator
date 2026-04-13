# 記事図解ジェネレーター

長文記事を直感的でわかりやすいHTML図解に自動変換するツール。

## 特徴

- **URLから自動取得** — 記事URLを貼り付けるだけで本文を自動取得
- **テキスト直接入力** — URLがない場合はテキスト貼り付けも可能
- **Tailwind CSS + Lucide Icons** — 統一されたデザインシステムで美しい図解を生成
- **一言結論・用語解説・かみ砕き解説** — 難しい記事も直感的に理解できる構成
- **PDF出力対応** — 生成された図解はブラウザからPDF印刷可能

## 使い方

```cmd
python app.py
```

または `run.bat` をダブルクリック。

初回起動時にAPIキーを入力すれば、次回からは自動読み込み。

## ファイル構成

```
├── app.py              # メインアプリケーション
├── run.bat             # 簡単起動バッチ
├── README.md
├── references/
│   └── base.html       # 図解HTMLテンプレート（Tailwind CSS + Lucide Icons + ADS配色）
├── ui/
│   ├── index.html      # Web UI
│   ├── config.txt      # APIキー保存（.gitignore対象）
│   ├── requirements.txt
│   └── QUICKSTART.md
├── output/             # 生成された図解HTML（.gitignore対象）
└── _archive/           # 旧バージョン（.gitignore対象）
```

## 技術仕様

- **フロントエンド**: Tailwind CSS CDN, Lucide Icons, Noto Sans JP
- **バックエンド**: Python 3.7+
- **AI**: Claude API (Sonnet 4.5)
- **ライブラリ**: anthropic, requests, beautifulsoup4

## 生成される図解の特徴

- 冒頭に記事の一言結論
- 難しい用語には解説ボックス
- 複雑な流れにはかみ砕き解説
- フローチャート、タイムライン、比較表、カードグリッド等
- レスポンシブデザイン（モバイル対応）
- PDF印刷対応

## 注意事項

- APIキーは公開しないでください
- Claude APIの使用には料金がかかります（従量課金）
- 著作権に配慮して使用してください
