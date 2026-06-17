import time
import json
import threading
from queue import Queue
from pathlib import Path

import tkinter as tk
from tkinter import scrolledtext
import pyttsx3


MEMORY_FILE = "mindforge_memory.json"
PROFILE_FILE = "user_profile.json"

def speak_text(text):
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        engine.setProperty("volume", 1.0)

        engine.say(text)
        engine.runAndWait()
        engine.stop()

    except Exception as e:
        print("TTS Error:", e)

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
    try:
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    except:
        memory = []

    memory.append({
        "timestamp": time.time(),
        "command": command,
        "response": response
    })

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def llm_reason(command):
    return f"I have received your command: {command}"


class MindForgeGUI:
    def __init__(self, root, queue):
        self.root = root
        self.queue = queue

        self.root.title("MindForge Offline Assistant")
        self.root.geometry("700x500")
        self.root.configure(bg="black")
        print("GUI initialized")

        self.log = scrolledtext.ScrolledText(root, state="disabled", wrap="word")
        self.log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(root, width=80)
        self.entry.pack(padx=10, pady=5)
        self.entry.bind("<Return>", self.manual_command)

        self.process_queue()

    def log_message(self, message):
        self.log.config(state="normal")
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def manual_command(self, event=None):
        command = self.entry.get().strip()
        self.entry.delete(0, tk.END)

        if command:
            self.queue.put(command)

    def process_queue(self):
        while not self.queue.empty():
            command = self.queue.get()
            command_lower = command.lower()

            if command_lower.startswith("remember that"):
                fact = command[len("remember that"):].strip()

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

            else:
                response = llm_reason(command)

            self.log_message(f"You: {command}")
            self.log_message(f"MindForge: {response}")

            save_memory(command, response)

            threading.Thread(
                target=speak_text,
                args=(response,),
                daemon=True
            ).start()

        self.root.after(100, self.process_queue)


if __name__ == "__main__":
    command_queue = Queue()
    root = tk.Tk()
    app = MindForgeGUI(root, command_queue)
    root.mainloop()