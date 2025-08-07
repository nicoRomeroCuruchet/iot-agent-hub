import os
import json
import time
import pyaudio
import torch
import requests
import loguru

import pvporcupine
import numpy as np
from pathlib import Path
import sounddevice as sd
from openai import OpenAI
from dotenv import load_dotenv
from utils import speak_with_openai
from faster_whisper import WhisperModel


tools = [
    {
        "type": "function", # This tool will be used to control the relay
        "function": {
            "name": "send_relay",
            "description": "Control the relay via POST to the Flask server",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "boolean",
                        "description": "true to turn relay on, false to turn off"
                    }
                },
                "required": ["state"]
            }
        }
    },
    {
        "type": "function", # This tool will be used to send error messages
        "function": {
            "name": "send_error",
            "description": "Send an error message to the Flask server",
            "parameters": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "string",
                        "description": "Error message explaining why action couldn't be determined"
                    }
                },
                "required": ["error"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Name of the city to get weather for"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": "Set an alarm to trigger at a specific time",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "string",
                        "description": "Alarm time in HH:MM 24-hour format"
                    },
                    "message": {
                        "type": "string",
                        "description": "Optional message to announce when the alarm goes off"
                    }
                },
                "required": ["time"]
            }
        }
    }
]


if __name__ == "__main__":

    # Load environment variables from .keys file    
    env_path = Path(__file__).parent / ".keys"
    load_dotenv(dotenv_path=env_path)

    flask_ip = "192.168.0.17"  # Replace with your Flask server IP
    flask_port = 5000

    openai_api_key = os.getenv("OPENAI_API_KEY")
    pv_access_key = os.getenv("PORCUPINE_ACCESS_KEY")
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY")

    if not openai_api_key or not pv_access_key:
        raise ValueError("Missing API keys in environment variables.")

    client = OpenAI(api_key=openai_api_key)
    
    # https://picovoice.ai/pricing/
    porcupine = pvporcupine.create(
        access_key=pv_access_key,
        keywords=["terminator", "hey google", "alexa", "computer", "jarvis"],
    )
   
    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )

    fs = 16000    # Sample rate
    duration = 5  # seconds
    loguru.logger.info("Loading Whisper model...")
    # Load the Whisper model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = WhisperModel("base.en", device=device, compute_type="float16")  # or "small", "medium", "large"
    loguru.logger.info("Whisper model loaded successfully.")
    loguru.logger.info("Models loaded, starting wake word detection...")
    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = np.frombuffer(pcm, dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                loguru.logger.info("Wake word detected, recording audio...")
                speak_with_openai(client, "Yes, tell me.", blocking=True)
                # Call your Whisper transcription or other logic here
                loguru.logger.info(f"Speak now for {duration} sec...")
                audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
                sd.wait()
                measure = time.time()
                loguru.logger.info("Recording complete, processing...")
                audio_float = audio.astype('float32').flatten() / 32768.0
                segments, info = model.transcribe(audio_float, beam_size=5, language="en", word_timestamps=True) 
                #Print each segment with timestamps
                input = ""
                for segment in segments:  # iterate generator
                    #loguru.logger.info(f"[{segment.start:.2f} - {segment.end:.2f}] {segment.text}")
                    input += segment.text
                    input = input.strip().lower()
                loguru.logger.info(f"Transcription complete: {input}")
                system_message = {
                    "role": "system",
                    "content":"You are an IoT voice assistant that controls a relay or sends errors."
                }

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        system_message,
                        {"role": "user", "content": f"Voice command: {input}"}
                    ],
                    tools=tools,
                )

                message = response.choices[0].message
                if not message.tool_calls:
                    loguru.logger.warning("No tool calls detected, using LLM response directly.")
                    speak_with_openai(client, message.content)
                
                if message.tool_calls:
                    tool_messages = []  # will collect all tool results here

                    for tool_call in message.tool_calls:
                        name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        loguru.logger.info(f"Calling tool: {name} with args: {args}")

                        # Execute the correct Flask endpoint
                        if name == "send_relay":
                            r = requests.post(f"http://{flask_ip}:{flask_port}/relay", json={"state": args["state"]})
                            tool_result = r.json()

                        elif name == "send_error":
                            r = requests.post(f"http://{flask_ip}:{flask_port}/error", json={"error": args["error"]})
                            tool_result = r.json()

                        elif name == "get_weather":
                            city = args["city"]
                            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={openweather_api_key}&units=metric"
                            r = requests.get(url)
                            tool_result = r.json()

                        elif name == "set_alarm":
                            time_str = args["time"]
                            message_alarm = args.get("message", "Alarm set!")
                            # Here you would implement the logic to set an alarm
                            # For now, we just return a confirmation
                            tool_result = {
                                "status": "success",
                                "message": f"Alarm set for {time_str} with message: {message}"
                            }
                        else:
                            tool_result = {"status": "error", "message": f"Unknown tool {name}"}

                        # Add this result as a tool message
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result)
                        })
                        
                    # Now call the model again with all tool messages
                    followup_messages = [
                        system_message,
                        {"role": "user", "content": f"Voice command: {input}"},
                        message,  # the original assistant tool call message
                        *tool_messages  # spread the list into the sequence
                    ]

                    followup = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=followup_messages
                    )

                    confirmation_text = followup.choices[0].message.content
                    speak_with_openai(client, confirmation_text)
                    loguru.logger.info("Assistant confirmation:", followup.choices[0].message.content)
                else:
                    loguru.logger.warning("No tool calls detected — nothing to execute.")

                loguru.logger.info(f"Processing time: {time.time() - measure:.2f} seconds")
                loguru.logger.info("Done processing input.")
                loguru.logger.info("Listening for wake word...")
    finally:
        audio_stream.close()
        pa.terminate()
        porcupine.delete()
