from flask import Flask, jsonify
import json
import os
from common import ROOT

app = Flask(__name__)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/config")
def config():
    with open(ROOT / "config" / "mock_app_config.json", "r", encoding="utf-8") as f:
        return jsonify(json.load(f))

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5001"))
    app.run(host=host, port=port, debug=False)
