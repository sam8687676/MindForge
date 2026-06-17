# Filename: mindforge_offline_gui_pyttsx3.py
# Fully offline MindForge assistant for Python 3.13
# Features: GUI, Offline TTS, Offline STT, Local LLM reasoning, ESP MQTT, Memory logging

import sys, os, time, threading, json
from queue import Queue
from pathlib import Path

import tkinter as tk
from tkinter import scrolledtext

# ----------------------------
# OFFLINE STT (Whisper.cpp)
# ----------------------------
import subprocess

# ----------------------------
# OFFLINE TTS (pyttsx3)
# ----------------------------
import pyttsx3

engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)

def speak_text(text):
    engine.say(text)
    engine.runAndWait()

# ----------------------------
# LOCAL LLM REASONING
# ----------------------------
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

device = "cpu"  # Change to "cuda" if GPU is available

print("Loading local LLM model...")
tokenizer = AutoTokenizer.from_pretrained("TheBloke/Mistral-7B-OpenOrca-V2-GPTQ")
model = AutoModelForCausalLM.from_pretrained(
    "TheBloke/Mistral-7B-OpenOrca-V2-GPTQ",
    device_map="auto",
    torch_dtype=torch.float16
)
llm_pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=0)

def llm_reason(command):
    prompt = f"You are MindForge, an intelligent assistant. Respond in Jarvis/Friday style to: {command}"
    output = llm_pipe(prompt, max_new_tokens=150, do_sample=True, temperature=0.7)
    return output[0]['generated_text']

# ----------------------------
# ESP MQTT CONTROL
# ----------------------------
import paho.mqtt.client as mqtt

MQTT_BROKER = "192.168.1.50"  # Change to your ESP32 broker IP
MQTT_PORT = 1883
MQTT_TOPIC = "mindforge/commands"

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

def send_esp_command(command):
    mqtt_client.publish(MQTT_TOPIC, command)

# ----------------------------
# MEMORY LOGGER
# ----------------------------
MEMORY_FILE = "mindforge_memory.json"
PROFILE_FILE = "user_profile.json"

def load_profile():
    if Path(PROFILE_FILE).exists():
        try:
            with open(PROFILE_FILE, "r") as f:
                return json.load(f)
        except:
            pass

    return {
        "facts": [],
        "tasks": [],
        "projects": [],
        "preferences": {}
    }

def save_profile(profile):
    with open(PROFILE_FILE, "w") as f:
        json.dump(profile, f, indent=4)

def save_memory(command, response):
    data = {
        "timestamp": time.time(),
        "command": command,
        "response": response
    }

    try:
        with open(MEMORY_FILE, "r") as f:
            mem = json.load(f)
    except:
        mem = []

    mem.append(data)

    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=4)

# ----------------------------
# OFFLINE STT FUNCTION
# ----------------------------
def stt_from_microphone():
    """
    Records 5 seconds from mic and uses whisper.cpp for offline transcription.
    Make sure whisper.cpp binary and model exist in ./whisper.cpp
    """
    if sys.platform.startswith("win"):
        # On Windows, you can record audio with sounddevice or other tools
        # For simplicity, you can record via Audacity and feed the file manually
        pass
    else:
        os.system("arecord -d 5 -f S16_LE -r 16000 input.wav")  # Linux example

    try:
        result = subprocess.run(
            ["./whisper.cpp/main", "-f", "input.wav", "-m", "models/ggml-small.en.bin"],
            capture_output=True
        )
        transcript = result.stdout.decode("utf-8").strip()
        return transcript
    except Exception as e:
        print("STT error:", e)
        return ""

# ----------------------------
# GUI CLASS
# ----------------------------
class MindForgeGUI:
    def __init__(self, root, queue):
        self.root = root
        self.queue = queue

        self.root.title("MindForge Offline Assistant")
        self.root.geometry("700x500")

        self.log = scrolledtext.ScrolledText(root, state='disabled', wrap='word')
        self.log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(root, width=80)
        self.entry.pack(padx=10, pady=5)
        self.entry.bind("<Return>", self.manual_command)

        self.process_queue()

    def log_message(self, message):
        self.log.config(state='normal')
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.config(state='disabled')

    def manual_command(self, event=None):
        cmd = self.entry.get()
        self.entry.delete(0, tk.END)
        self.queue.put(cmd)

def process_queue(self):
    while not self.queue.empty():
        command = self.queue.get()
        if not command:
            continue
        command_lower = command.lower()

        # =====================
        # MEMORY COMMANDS
        # =====================

        if command_lower.startswith("remember that"):
            fact = command[13:].strip()
            profile = load_profile()
            profile["facts"].append(fact)
            save_profile(profile)
            response = "I'll remember that."

        elif "what do you know about me" in command_lower:
            profile = load_profile()
            if len(profile["facts"]) == 0:
                response = "I don't know anything about you yet."
            else:
                response = "Here's what I know:\n"
                for fact in profile["facts"]:
                    response += f"\n• {fact}"

        # =====================
        # ESP COMMANDS
        # =====================

        elif "light" in command_lower or "esp" in command_lower:
            if "on" in command_lower:
                send_esp_command("LIGHT_ON")
                response = "Turning on the light."
            else:
                send_esp_command("LIGHT_OFF")
                response = "Turning off the light."

        # =====================
        # AI REASONING
        # =====================

        else:
            try:
                response = llm_reason(command)
            except Exception as e:
                response = f"LLM error: {e}"

        self.log_message(f"You: {command}")
        self.log_message(f"MindForge: {response}")

        threading.Thread(
            target=speak_text,
            args=(response,),
            daemon=True
        ).start()

        save_memory(command, response)

    self.root.after(100, self.process_queue)

