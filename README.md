## IoT Voice Assistant – Hello World
This is a minimal proof-of-concept for an  IoT assistant that combines wake word detection, fast speech-to-text, GPT‑4o‑mini function calling, and direct device control via a Flask backend.

It allows you to control relays or report errors through natural voice commands.

### Features

       -🎙 Wake word detection — activates when you say "terminator", "alexa", "computer", etc. 
       -⚡ Fast transcription — uses faster-whisper (CPU/GPU optimized Whisper.cpp) for quick local STT 
       -🤖 AI-powered intent recognition — GPT‑4o‑mini with tool calls to map voice commands to actions
       -🔌 IoT device control — sends POST requests to a Flask backend to switch relays or log errors
       -🔊 Text-to-speech responses — generates assistant replies with OpenAI TTS and plays them in memory
            

## Project Organization

      project/
      ├── server.py               # Flask app with MQTT publishing
      ├── voice_llm.py            # Voice capture, transcription, LLM query, payload sending
      ├── utils.py                # to play sounds
      ├── docker/
      │   ├── Dockerfile
      │   ├── docker-compose.yml
      │   ├── requirements.txt    # Python dependencies for Flask app
      │   └── mosquitto.conf      # MQTT broker config


## How It Works

1. Mosquitto runs as the MQTT broker.

2. Flask app (server.py) exposes:

    - POST /relay → Controls a relay by publishing to MQTT topic home/relay.
    - POST /error → Logs error messages.

3. voice_llm.py:

   - Wake word detection — Porcupine listens continuously for a predefined keyword.
   - Voice recording — After detection, records your voice for a few seconds.
   - Speech-to-text — Transcribes audio with faster-whisper.
   - AI intent recognition — Sends the transcription to GPT‑4o‑mini with function calling enabled.
   - Tool execution — If GPT chooses a tool, sends data to Flask server.
   - Assistant confirmation — GPT generates a confirmation, which is spoken aloud via OpenAI TTS.

4. Flask app publishes MQTT messages to devices.

## Setup Python Environment & API Keys

1. We’ll use **.iot** as the name of the virtual environment (it will be in the project folder).

            python3 -m venv .iot
            source .iot/bin/activate   # On Windows: .iot\Scripts\activate

2. Install the required packages from requirements.txt:

            pip install --upgrade pip
            pip install -r requirements.txt
   
4. Create a .keys file for API keys

         touch .keys
   
   Contents:
   
         OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxx
         PORCUPINE_ACCESS_KEY=yyyyyyyyyyyyyyyyyy

5. You can run voice_llm.py locally (not inside the container) so it has microphone access:

         python3 voice_llm.py

   - It will:

     - Wait for the wake word "computer".
     - Record 5 seconds of speech.
     - Send commands to the Flask app based on the LLM output.

## Running the flask server and the MQTT broker 

From the docker/ directory:

      cd docker
      docker-compose up --build

This starts:

 - flaskapp → The Flask REST API, listening on port 5000
- mosquitto → MQTT broker on port 1883

Both run in host network mode, so ports match the host machine.

## Testing the API

Once running, you can test the relay control endpoint:

            curl -X POST -H "Content-Type: application/json" -d '{"state": true}' http://localhost:5000/relay
            
And test the error endpoint:
      
            curl -X POST -H "Content-Type: application/json" -d '{"error": "Example error"}' http://localhost:5000/error










