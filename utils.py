import io
import pygame
import threading

def _play_audio(buffer):
    pygame.mixer.init()
    pygame.mixer.music.load(buffer)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

def speak_with_openai(client, text):
    buffer = io.BytesIO()
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    ) as response:
        for chunk in response.iter_bytes():
            buffer.write(chunk)
    buffer.seek(0)
    # Play audio in background thread
    threading.Thread(target=_play_audio, args=(buffer,), daemon=True).start()