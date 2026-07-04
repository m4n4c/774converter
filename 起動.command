#!/bin/bash
# ダブルクリックで匿名化アプリを起動してブラウザを開く
cd "$(dirname "$0")"

# すでに起動している場合はブラウザを開くだけ(二重起動エラーを防ぐ)
if lsof -ti :8756 >/dev/null 2>&1; then
  echo "アプリはすでに起動しています。ブラウザを開きます。"
  open http://localhost:8756
  exit 0
fi

(sleep 3 && open http://localhost:8756) &
exec .venv/bin/uvicorn app:app --port 8756
