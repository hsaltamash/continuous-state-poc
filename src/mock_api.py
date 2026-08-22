from flask import Flask, jsonify
import json
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
    app.run(host="127.0.0.1", port=5001, debug=False)
