import io
import pygame
import threading

def _play_audio(buffer):
    """Plays audio from a BytesIO buffer using pygame."""
    buffer.seek(0)  # Ensure the buffer is at the start
    pygame.mixer.init()
    pygame.mixer.music.load(buffer)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

def speak_with_openai(client, text, blocking=False):
    """Sends text to OpenAI's TTS service and plays the audio.
    Args:
        client: OpenAI client instance.
        text: Text to convert to speech.
        blocking: If True, waits for audio to finish playing."""
    buffer = io.BytesIO()
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    ) as response:
        for chunk in response.iter_bytes():
            buffer.write(chunk)
    # Play audio in background thread
    if blocking:
        _play_audio(buffer)
    else:
        threading.Thread(target=_play_audio, args=(buffer,)).start()
       