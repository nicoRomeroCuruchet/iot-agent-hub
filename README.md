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
