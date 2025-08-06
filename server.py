from flask import Flask, request
import paho.mqtt.publish as publish

app = Flask(__name__)

@app.route('/')
def index():
    return "Flask is running!"


@app.route('/error', methods=['POST'])
def handle_error():
    """ This method expects a JSON payload with an 'error' key and 
        it's for handle when the listener fails in detect or
        processing an misunderstanding phrase."""
    error_message = request.json.get("error", "Unknown error")
    return {"status": "error", "message": error_message}

@app.route('/relay', methods=['POST'])
def control_relay():
    """ This endpoint controls a relay.
        It expects a JSON payload with a 'state' key, 
        which can be true or false
    
        Example payload: {"state": true}
        This will turn the relay on.

        Example curl command to test this endpoint:
        ```bash
        curl -X POST -H "Content-Type: application/json" -d '{"state": true}' http://localhost:5000/relay
        ```
        The relay will be turned on if 'state' is true."""
    state = request.json.get("state", False)
    payload = '1' if state else '0'  # send raw boolean byte
    # Publish to the MQTT topic
    publish.single("home/relay", payload)
    return {"status": "sent", "relay": state}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)