# 使用するPythonのバージョンを指定
# Nmbot.pyが動作するPython 3.11を指定します
FROM python:3.11

# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# プログラムの実行に必要なライブラリを記述したファイルをコピー
COPY app/requirements.txt .

# 依存関係にあるライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# app/Nmbot.pyをコンテナ内にコピー
COPY app/Nmbot.py .

# ポートを開ける（Koyeb用）
# あなたのBotのコードにWebサーバー機能が追加されているため、ポート8080を開放します
EXPOSE 8080

# Botの起動コマンド
# Nmbot.pyを実行するコマンドを指定します
CMD ["python", "Nmbot.py"]

# ヘルスチェックを追加
HEALTHCHECK CMD curl --fail http://localhost:8080 || exit 1
