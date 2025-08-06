import os
import json
import time
import pyaudio
import whisper
import requests
import loguru

import pvporcupine
import numpy as np
from pathlib import Path
import sounddevice as sd
from openai import OpenAI
from dotenv import load_dotenv
from utils import speak_with_openai


tools = [
    {
        "type": "function",
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
        "type": "function",
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
    }
]


if __name__ == "__main__":

    # Load environment variables from .keys file    
    env_path = Path(__file__).parent / ".keys"
    load_dotenv(dotenv_path=env_path)

    flask_ip = "localhost"
    flask_port = 5000

    openai_api_key = os.getenv("OPENAI_API_KEY")
    pv_access_key = os.getenv("PORCUPINE_ACCESS_KEY")

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
    duration =2  # seconds
    model = whisper.load_model("base", device="cpu")  # or "small", "medium", "large"
    loguru.logger.info("Models loaded, starting wake word detection...")
    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = np.frombuffer(pcm, dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                loguru.logger.info("Wake word detected, recording audio...")
                # Give a small pause before recording to avoid cutting off the start
                time.sleep(0.1)
                # Call your Whisper transcription or other logic here
                loguru.logger.info(f"Speak now for {duration} sec...")
                audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
                sd.wait()
                measure = time.time()
                loguru.logger.info("Recording complete, processing...")
                audio_float = audio.astype('float32').flatten() / 32768.0
                result = model.transcribe(audio_float, language="en", fp16=False)   
                #Print each segment with timestamps
                input = ""
                for segment in result.get("segments", []):
                    loguru.logger.info(f"[{segment['start']:.2f} - {segment['end']:.2f}] {segment['text']}")
                    input += segment['text']


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
