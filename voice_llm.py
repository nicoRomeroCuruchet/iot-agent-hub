import os
import re
import json
import requests

import time
import pyaudio
import whisper

import pvporcupine
import numpy as np
import sounddevice as sd
from openai import OpenAI

from dotenv import load_dotenv
from pathlib import Path



def send_payload(topic, payload):
    """ Sends a JSON payload to the specified HTTP endpoint.

    Parameters:
    - topic (str): The HTTP endpoint (URL) to which the payload will be sent.
    - payload (dict): The JSON-serializable payload to send.

    Returns:
    - None """
    try:
        response = requests.post(topic, json=payload)
        if response.status_code == 200:
            print("Payload sent successfully.")
        else:
            print(f"Failed to send payload. Status code: {response.status_code}")
    except Exception as e:
        print(f"Failed to send payload: {e}")

def generate_prompt(input, server_code_str):
    
    
    json_str_on = '''{
    "topic": "/relay",
    "payload": true
    }'''

    json_str_off = '''{
    "topic": "/relay",
    "payload": false
    }'''

    json_str_error = '''{
    "topic": "/error",
    "payload": "I cannot deduce the input"
    }'''

    function_str = """def send_payload(topic, payload):
    \"""
    Sends a JSON payload to the specified HTTP endpoint.

    Parameters:
    - topic (str): The HTTP endpoint (URL) to which the payload will be sent.
    - payload (dict): The JSON-serializable payload to send.

    Returns:
    - None
    \"""
    try:
        response = requests.post(topic, json=payload)
        if response.status_code == 200:
            print("Payload sent successfully.")
        else:
            print(f"Failed to send payload. Status code: {response.status_code}")
    except Exception as e:
        print(f"Failed to send payload: {e}")
"""

    prompt = f"Based on the input: '{input}'\n\
    You are an assistant in an IoT system. A voice input was captured by a listening system.\
    The input may have errors, be partial, or triggered by mistake.\
    You have access to a REST server that exposes endpoints this is the code:\
    \n\n'''{server_code_str.strip()}'''\n\n\
    Your task is:\n\
    - Based on the input text, determine which endpoint should be called.\n\
    - Then generate the appropriate parameters to call the `send_payload` function and brief comment one line how you arrived to the result.\n\
    - This is the code of this function:\n\
    \n '''{function_str}'''\n\
    ### Rules:\n\
    - If the input clearly means to turn on/off the relay, call `/relay` with the correct state.\n\
    - If you cannot deduce the input, call `/error` with a message saying 'I cannot deduce the input'.\n\
    - You DO NOT HAVE to generate python code just the parameters for the function and comment with no more than one line how you arrived to the result.\n\
    - The parameters should be a JSON string with the topic and payload.\n\
    - The topic should be the endpoint you want to call, e.g., `/relay` or `/error`.\n\
    - Please comment with no more than one line how you arrived at those parameters.\n\
    - I need a JSON string as output.\n\
    - The payload should be a boolean for `/relay` (true for on, false for off) or a string for `/error`.\n\
    - The input may be partial or contain errors, so think carefully about the input.\n\
    - You have 1 second to respond, so think fast!\n\
    - The parameters should be a JSON string with the topic and payload.\n\
    - Think carefully about the input, it may be partial or contain errors.\n\
    - Think fast, you have 1 seconds to respond!\n\
    ### Output (format strictly as JSON):\n\
    For example, if you can deduce the input is turn on the relay, output should be:\n\
    + {json_str_on}\n\
    For example, if you can deduce the input is turn off the relay, output should be:\n\
    + {json_str_off}\n\
    For example, if you cannot deduce the input, output should be:\n\
    + {json_str_error}\n"

    return prompt

def llm_query(client, prompt):

    """Queries the OpenAI API with a given prompt and returns the response."""

    response = client.chat.completions.create(
    model="gpt-3.5-turbo",  # or "gpt-4" if you need higher accuracy
    messages=[
        {"role": "system", "content": "You are an IoT assistant that outputs only a JSON string."},
        {"role": "user",   "content": prompt}
    ],
    temperature=0.2,  # Keep output deterministic
    max_tokens=100,   # Limit the response length
)
    return response.choices[0].message.content.strip()

def llm_query_local(prompt, model="llama3"):
    """ Queries a language model with the given prompt.
    Args:
        prompt (str): The input prompt for the language model.
        model (str): The model to use for the query. Default is "llama3"."""
    
    url = "http://localhost:11434/api/generate"
    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": False
    }
    
    response = requests.post(url, json=payload)
    return response.json()["response"]


if __name__ == "__main__":
    # Load environment variables from .keys file    
    env_path = Path(__file__).parent / ".keys"
    print("Loading environment from:", env_path)
    load_dotenv(dotenv_path=env_path)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    pv_access_key = os.getenv("PORCUPINE_ACCESS_KEY")

    if not openai_api_key or not pv_access_key:
        raise ValueError("Missing API keys in environment variables.")

    client = OpenAI(api_key=openai_api_key)
    access_key = pv_access_key

    fs = 16000    # Sample rate
    duration = 5  # seconds

    # https://picovoice.ai/pricing/
    model = whisper.load_model("base", device="cpu")  # or "small", "medium", "large"

    porcupine = pvporcupine.create(
        access_key=access_key,
        keywords=["computer"]
    )

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )

    # Prompt for generating parameters based on input
    with open("server.py", "r", encoding="utf-8") as f:
        code = f.read()

    print("Listening for wake word...")
    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = np.frombuffer(pcm, dtype=np.int16)
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                print("Wake word detected!")
                time.sleep(0.5)
                # Call your Whisper transcription or other logic here
                print("Speak now for 5 sec...")
                audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
                sd.wait()
                measure = time.time()
                print("Recording complete, processing...")
                audio_float = audio.astype('float32').flatten() / 32768.0
                result = model.transcribe(audio_float, language="en", fp16=False)   
                #Print each segment with timestamps
                input = ""
                for segment in result.get("segments", []):
                    print(f"[{segment['start']:.2f} - {segment['end']:.2f}] {segment['text']}")
                    input += segment['text']

                # Generate the prompt for LLM
                prompt_to_llm = generate_prompt(
                    input=input,
                    server_code_str=code
                )
                
                if client is None:
                    output = llm_query_local(prompt_to_llm)
                else:
                    output = llm_query(client, prompt_to_llm)
                    
                print("LLM output:", output)
                # Extract the code block between triple backticks
                match = re.search(r"\{[^{}]*\}", output, re.DOTALL)
                if match:
                    code_block = match.group(0)
                    # Normalize: single quotes to double quotes, b'0' or '0' to "0"
                    code_block = code_block.replace("'", '"').replace('b"0"', '"0"').replace('b\'0\'', '"0"')
                    try:
                        data = json.loads(code_block)
                        print(data)
                    except json.JSONDecodeError as e:
                        print("JSON decode error:", e)
                        print("Extracted string:", code_block)
                else:
                    print("No code block found.")

                # Send the payload to the server
                url = f"http://localhost/{data['topic']}"  
                if data['topic'] == "/error":
                    data = {
                        "payload": data.get("payload", "I cannot deduce the input")
                    }
                else:
                    data = {
                        "state": data.get("payload", False),           # Default to False if payload is not present
                    }

                send_payload(url, data)
                print(f"Transcription and LLM inference completed in {time.time() - measure:.2f} seconds")
                print("Listening for wake word...")
    finally:
        audio_stream.close()
        pa.terminate()
        porcupine.delete()
