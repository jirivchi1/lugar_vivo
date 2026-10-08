import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import (
    PipelineParams,
    PipelineWorker,
    ProcessorUnusablePolicy,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)
from pipecat.workers.runner import WorkerRunner

from contador import ContadorCostes, Conversacion, guardar_sesion

load_dotenv(override=True)
logger.remove(0)
logger.add(sys.stderr, level="INFO")

PERSONAJE = Path("personajes/tenebrio.md").read_text(encoding="utf-8")


async def main():
    # Micro y altavoz del ordenador
    transport = LocalAudioTransport(
        LocalAudioTransportParams(audio_in_enabled=True, audio_out_enabled=True)
    )

    # Oído: ElevenLabs Scribe en tiempo real, en español
    stt = ElevenLabsRealtimeSTTService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        settings=ElevenLabsRealtimeSTTService.Settings(language=Language.ES),
    )

    # Cerebro: Claude
    llm = AnthropicLLMService(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        settings=AnthropicLLMService.Settings(
            model="claude-haiku-4-5-20251001",
            system_instruction=PERSONAJE,
        ),
    )

    # Boca: voz de ElevenLabs
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        settings=ElevenLabsTTSService.Settings(voice=os.environ["ELEVENLABS_VOICE_ID"]),
    )

    # Memoria de la conversación + detección de voz
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),  # micro
            stt,  # voz -> texto
            user_aggregator,  # guarda lo que dice el visitante
            llm,  # piensa la respuesta
            tts,  # texto -> voz
            transport.output(),  # altavoz
            assistant_aggregator,  # guarda lo que dijo el tenebrio
        ]
    )

    # Observadores: coste + conversación en pantalla (ligeros)
    contador = ContadorCostes()
    observadores = [contador, Conversacion()]

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        processor_unusable_policy=ProcessorUnusablePolicy.END,
        observers=observadores,
    )

    runner = WorkerRunner()
    await runner.add_workers(worker)

    # El tenebrio habla primero
    context.add_message(
        {
            "role": "developer",
            "content": "Saluda a los visitantes que acaban de llegar.",
        }
    )
    await worker.queue_frames([LLMRunFrame()])

    try:
        await runner.run()
    finally:
        guardar_sesion(contador, context.messages)


if __name__ == "__main__":
    asyncio.run(main())
