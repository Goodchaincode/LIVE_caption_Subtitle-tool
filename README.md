# LIVE_caption_Subtitle-tool
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Speech Recognition](https://img.shields.io/badge/AI-Speech--to--Text-orange)
![UI](https://img.shields.io/badge/Interface-PyQt%20%2F%20Tkinter-green)
![OBS](https://img.shields.io/badge/Streaming-OBS%20Compatible-purple)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

This application can solve problem of giving you live caption it automatically syncs , just follow the GUI order 



YOU need tesseract Engine installed for this ,
u need to insert .srt, .ass , .vtt file for working of this TOOL 

Draw the OCR box and it should work on syncing your subtitle automatically .
U just need too connect a sync line with the proper timestamp in GUI rest of the syncing during of your show will be done by the program itself .

## 📌 Project Overview
The **LIVE Caption & Subtitle Tool** is a lightweight, real-time speech-to-text desktop application. Designed for content creators, educators, and accessibility purposes, this tool listens to system or microphone audio and generates highly accurate live subtitles on your screen.

Whether you are presenting a live webinar, streaming on Twitch/YouTube, or need immediate transcription for a meeting, this tool provides a seamless, transparent overlay that integrates perfectly with your existing workflow.

## 🚀 Key Features
* **⚡ Real-Time Transcription:** Utilizes advanced Speech-to-Text (STT) models to generate subtitles with minimal latency.
* **🌍 Multi-Language Support:** Automatically detects and transcribes speech in multiple languages.
* **🎛️ Transparent Overlay:** Features a borderless, transparent window that can sit on top of any application or be captured as a window source in **OBS Studio**.
* **💾 Export Options:** Save your live transcripts as `.txt`, `.srt`, or `.vtt` files for post-production editing.
* **🎨 Customizable UI:** Adjust font sizes, text colors, and background opacity to match your brand or viewing preferences.

## 🧠 Core Implementation: The Audio Pipeline
The efficiency of this tool relies on a continuous audio buffering and transcription pipeline. Below is a conceptual snippet of how the background worker handles real-time audio chunking without freezing the UI:

```python
import speech_recognition as sr
import threading

def process_audio_stream():
    """
    Background thread that continuously listens to the microphone
    and yields transcribed text to the UI overlay.
    """
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("🎙️ Listening for live audio...")
        
        while True:
            try:
                # Listen in short chunks for real-time feel
                audio = recognizer.listen(source, phrase_time_limit=3)
                text = recognizer.recognize_google(audio)
                
                # Update the UI via thread-safe signals
                update_subtitle_ui(text)
                
            except sr.UnknownValueError:
                pass # Ignore silence or unintelligible noise
            except sr.RequestError as e:
                print(f"⚠️ API Error: {e}")

