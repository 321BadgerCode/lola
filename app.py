from flask import Flask, render_template, jsonify
import threading
from assistant import assistant_loop
import var

app = Flask(__name__)

@app.route('/')
def index():
	return render_template("index.html", listening=var.is_listening, prompt=var.last_prompt, response=var.last_resp)

@app.route("/toggle_listen", methods=["POST"])
def toggle_listen():
	var.is_listening = not var.is_listening
	return jsonify({"listening": var.is_listening})

@app.route("/update", methods=["GET"])
def update():
	return jsonify({
		"listening": var.is_listening,
		"prompt": var.last_prompt,
		"response": var.last_resp
	})

if __name__ == "__main__":
	t = threading.Thread(target=assistant_loop, daemon=True)
	t.start()
	app.run(debug=True, use_reloader=False)