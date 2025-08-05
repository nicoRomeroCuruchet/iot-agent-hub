## IoT Voice Assistant – Hello World
This is a minimal proof-of-concept for an IoT voice assistant that listens for a wake word, transcribes speech, decides an action using an LLM, and sends commands to devices via HTTP → MQTT.

The idea is that this can be integrated with devices that use the MQTT protocol (e.g., smart relays, sensors, actuators).

Features

- Wake word detection using Picovoice Porcupine.
- Speech-to-text transcription via OpenAI Whisper.
- Decision-making using an LLM (local Ollama or OpenAI API).
- Flask REST API that exposes /relay and /error endpoints.
- MQTT publishing via paho-mqtt to control devices.
- Dockerized setup with Mosquitto MQTT broke

      project/
      ├── server.py               # Flask app with MQTT publishing
      ├── voice_llm.py            # Voice capture, transcription, LLM query, payload sending
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

    - Listens for wake word "computer".
    - Records 5 seconds of audio.
    - Transcribes the audio using Whisper.
    - Builds a prompt including the server.py code.
    - Queries an LLM to determine the action (turn relay on/off, or send error).
    - Sends a JSON payload to the Flask app.

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

5. Run the voice llm server:

         python3 voice_llm.py

## Running the flask server and the MQTT broker 

From the docker/ directory:

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










