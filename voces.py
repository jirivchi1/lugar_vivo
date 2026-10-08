import os, json, urllib.request, urllib.error
from dotenv import load_dotenv

load_dotenv(override=True)
key = os.environ["ELEVENLABS_API_KEY"].strip()

req = urllib.request.Request(
    "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}
)
voces = json.load(urllib.request.urlopen(req))["voices"]

print("Voces que puedes usar con tu plan:\n")
for v in voces:
    if (
        v.get("category") in ("premade", "cloned", "generated", "professional")
        and v.get("category") != "library"
    ):
        etiquetas = v.get("labels", {})
        print(
            f"{v['voice_id']}  |  {v['name']:<12} | {v.get('category')} | "
            f"{etiquetas.get('gender', '')} {etiquetas.get('age', '')} {etiquetas.get('accent', '')} {etiquetas.get('description', '')}"
        )
