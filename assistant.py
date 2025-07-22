import os
import time
import requests
import threading
import json
import tempfile
import sounddevice as sd
import scipy.io.wavfile as wav
import pyttsx3
import whisper
import var

class TTSManager:
	def __init__(self):
		self.engine = pyttsx3.init()
		self._lock = threading.Lock()
		self._stop_flag = False
		self._current_thread = None
		# TODO: Add more voices or allow user to select
		# voices = self.engine.getProperty("voices")
		# for voice in voices:
		# 	if "English" in voice.name:
		# 		print(f"Voice: {voice.name}, ID: {voice.id}, Languages: {voice.languages}")

	def speak(self, text):
		def _speak():
			with self._lock:
				self.engine.say(text)
				self.engine.runAndWait()

		self.stop()
		self._stop_flag = False
		self._current_thread = threading.Thread(target=_speak, daemon=True)
		self._current_thread.start()

	def stop(self):
		if self._current_thread and self._current_thread.is_alive():
			self.engine.stop()
			self._stop_flag = True

tts = TTSManager()
model = whisper.load_model("base")
conf = json.load(open("config.json"))

def transcribe_whisper(audio_path):
	result = model.transcribe(audio_path)
	return result["text"]

def record_audio(seconds=7.5, samplerate=16000):
	audio = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1)
	sd.wait()
	with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
		wav.write(f.name, samplerate, audio)
		return f.name

def call_ollama(prompt):
	try:
		res = requests.post("http://localhost:11434/api/generate", json={
			"model": conf["llm"].get("model", "mistral:7b-instruct-q4_K_M"),
			"prompt": prompt,
			"stream": False,
			"temperature": conf["llm"].get("temperature", 0.7),
			"top_p": conf["llm"].get("top_p", 0.9),
			"max_tokens": conf["llm"].get("max_tokens", 512)
		})

		data = res.json()

		if "response" in data:
			return data["response"]
		elif "error" in data:
			return f"Ollama Error: {data["error"]}"
		else:
			return "Unexpected response from Ollama."

	except Exception as e:
		return f"Ollama call failed: {e}"

def call_mcp_if_needed(text):
	for mcp in conf["mcp"]:
		if mcp.lower() in text.lower():
			try:
				r = requests.get(conf["mcp"][mcp]["api"])
				if r.status_code == 200:
					return f"{conf["mcp"][mcp]["resp_pre"]} {r.text.strip()}"
				else:
					return f"Error fetching data from MCP: {r.status_code}"
			except Exception as e:
				return f"MCP call failed: {e}"
	return None

def assistant_loop():
	while True:
		if not var.is_listening:
			time.sleep(1)
			continue

		# Always listening
		audio_path = record_audio(seconds=5)
		transcription = transcribe_whisper(audio_path)
		os.remove(audio_path)

		if not transcription.strip():
			continue

		var.last_prompt = transcription

		# User interrupted – stop any ongoing speech
		tts.stop()

		if "stop" in transcription.lower():
			var.is_listening = False
			tts.speak("Okay, I stopped listening.")
			continue

		# Check if needs MCP (API)
		mcp_response = call_mcp_if_needed(transcription)
		if mcp_response:
			var.last_resp = mcp_response
			tts.speak(mcp_response)
			continue

		# Else, call LLM
		reply = call_ollama(transcription)
		var.last_resp = reply
		tts.speak(reply)