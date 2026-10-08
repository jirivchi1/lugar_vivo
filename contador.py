import json
import time
from datetime import datetime
from pathlib import Path

from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import (
    LLMUsageMetricsData,
    STTUsageMetricsData,
    TTSUsageMetricsData,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.services.llm_service import LLMService
from pipecat.services.stt_service import STTService

# Precios en $ (revísalos de vez en cuando en las webs oficiales)
PRECIOS = {
    "llm_in_mtok": 1.00,  # Claude Haiku 4.5, entrada por millón de tokens
    "llm_out_mtok": 5.00,  # Claude Haiku 4.5, salida por millón de tokens
    "llm_cache_mtok": 0.10,  # lectura de caché
    "tts_1k_chars": 0.04,  # ElevenLabs Flash v2.5
    "stt_hora": 0.39,  # ElevenLabs Scribe v2 Realtime
}


class ContadorCostes(BaseObserver):
    """Suma el consumo de cada servicio durante una sesión."""

    def __init__(self, **kwargs):
        super().__init__(observe_every_push=False, **kwargs)
        self.inicio = time.time()
        self.llm_in = self.llm_out = self.llm_cache = 0
        self.tts_chars = 0
        self.stt_seg = 0.0

    async def on_push_frame(self, data: FramePushed):
        if not data.first_push or not isinstance(data.frame, MetricsFrame):
            return
        for m in data.frame.data:
            if isinstance(m, LLMUsageMetricsData):
                self.llm_in += m.value.prompt_tokens
                self.llm_out += m.value.completion_tokens
                self.llm_cache += m.value.cache_read_input_tokens or 0
            elif isinstance(m, TTSUsageMetricsData):
                self.tts_chars += m.value
            elif isinstance(m, STTUsageMetricsData):
                self.stt_seg += m.value.audio_seconds

    def resumen(self) -> dict:
        p = PRECIOS
        coste_llm = (
            (self.llm_in - self.llm_cache) * p["llm_in_mtok"]
            + self.llm_cache * p["llm_cache_mtok"]
            + self.llm_out * p["llm_out_mtok"]
        ) / 1_000_000
        coste_tts = self.tts_chars / 1000 * p["tts_1k_chars"]
        coste_stt = self.stt_seg / 3600 * p["stt_hora"]
        return {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "duracion_min": round((time.time() - self.inicio) / 60, 2),
            "claude_tokens_entrada": self.llm_in,
            "claude_tokens_salida": self.llm_out,
            "voz_caracteres": self.tts_chars,
            "oido_segundos": round(self.stt_seg, 1),
            "coste_claude_usd": round(coste_llm, 4),
            "coste_voz_usd": round(coste_tts, 4),
            "coste_oido_usd": round(coste_stt, 4),
            "coste_total_usd": round(coste_llm + coste_tts + coste_stt, 4),
        }


def guardar_sesion(contador: ContadorCostes, mensajes: list, carpeta="data/sesiones"):
    """Guarda el coste y la conversación completa en un JSON por sesión."""
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    datos = {"costes": contador.resumen(), "conversacion": mensajes}
    nombre = Path(carpeta) / f"sesion_{datetime.now():%Y%m%d_%H%M%S}.json"
    nombre.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("\n=== RESUMEN DE LA SESIÓN ===")
    for k, v in datos["costes"].items():
        print(f"{k:>24}: {v}")
    print(f"Guardado en {nombre}")


class Conversacion(BaseObserver):
    """Muestra la conversación y avisa de interrupciones, sin cargar el audio."""

    def __init__(self, **kwargs):
        super().__init__(observe_every_push=False, **kwargs)
        self._respuesta = []
        self._bot_hablando = False

    async def on_push_frame(self, data: FramePushed):
        f, src = data.frame, data.source
        hora = datetime.now().strftime("%H:%M:%S")
        if isinstance(f, TranscriptionFrame) and isinstance(src, STTService):
            print(f"[{hora}] 👤 Visitante: {f.text}")
        elif isinstance(f, LLMFullResponseStartFrame) and isinstance(src, LLMService):
            self._respuesta = []
        elif isinstance(f, LLMTextFrame) and isinstance(src, LLMService):
            self._respuesta.append(f.text)
        elif isinstance(f, LLMFullResponseEndFrame) and isinstance(src, LLMService):
            print(f"[{hora}] 🪲 Tenebrio: {''.join(self._respuesta).strip()}")
        elif isinstance(f, BotStartedSpeakingFrame):
            self._bot_hablando = True
        elif isinstance(f, BotStoppedSpeakingFrame):
            self._bot_hablando = False
        elif isinstance(f, InterruptionFrame) and self._bot_hablando:
            print(f"[{hora}] ⚠️  Interrupción mientras hablaba el tenebrio")
