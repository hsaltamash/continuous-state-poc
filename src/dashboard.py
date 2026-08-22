from flask import Flask, render_template
from state_engine import current_state, recent_events

app = Flask(__name__, template_folder="../templates")

@app.get("/")
def index():
    rows = current_state()
    counts = {"MATCH": 0, "DRIFT": 0, "UNKNOWN": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return render_template("dashboard.html", rows=rows, events=recent_events(20), counts=counts)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
