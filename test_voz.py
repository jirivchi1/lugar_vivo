import os, json, urllib.request, urllib.error
from dotenv import load_dotenv

load_dotenv(override=True)
key = os.environ["ELEVENLABS_API_KEY"].strip()
voz = os.environ["ELEVENLABS_VOICE_ID"].strip()
print("Voice ID:", repr(voz))

req = urllib.request.Request(
    f"https://api.elevenlabs.io/v1/text-to-speech/{voz}",
    data=json.dumps(
        {"text": "Hola, soy un tenebrio.", "model_id": "eleven_flash_v2_5"}
    ).encode(),
    headers={"xi-api-key": key, "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req) as r:
        audio = r.read()
        open("prueba.mp3", "wb").write(audio)
        print("OK: audio recibido,", len(audio), "bytes -> prueba.mp3")
except urllib.error.HTTPError as e:
    print("ERROR", e.code, e.read().decode())
