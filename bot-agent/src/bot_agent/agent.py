"""LiveKit Agents worker backing the webapp's /bot/[nome] conversations.

Run it with::

    uv run bot-agent dev      # local development, connected to LiveKit Cloud
    uv run bot-agent start    # production

The worker registers itself under the name ``llm-bot``; the webapp asks for it
through the Agent Dispatch API from ``webapp/src/routes/api/token/+server.ts``.
The two names must stay in sync.

The pipeline is STT -> LLM -> TTS:

* STT and TTS run locally, on top of the helpers in :mod:`bot_agent.stt_tts`
  (faster-whisper and Piper) via the adapters in :mod:`bot_agent.plugins`;
* the LLM is a remote OpenAI-compatible endpoint. DeepSeek is the default
  (``LLM_BASE_URL`` defaults to their API, ``LLM_MODEL`` to ``deepseek-chat``),
  but any compatible service works by changing those two variables.

Everything that can be configured lives in the environment; see
``bot-agent/.env.example``.

The module exposes a module-level ``server`` (an :class:`AgentServer`). That is
not decorative: ``lk agent dev src/bot_agent/agent.py`` imports this file and
then introspects it for an ``AgentServer`` instance, so the worker must be
registered on an object that exists at import time. Building
``WorkerOptions`` inside ``main()`` (as earlier versions of this file did) is
still a valid *runtime* path, but it is invisible to ``lk agent dev`` and
fails with ``CLIError: Could not find AgentServer in module``. Keeping
``load_dotenv()`` at module scope follows from the same fact: discovery never
calls ``main()``, so anything that has to be configured before the server is
constructed must run on import.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RoomOutputOptions,
    cli,
)
from livekit.plugins import openai, silero

from .plugins import PiperTTS, WhisperSTT

# Module scope, not inside main(): `lk agent dev` imports this module and
# reads the environment while constructing `server` below, without ever
# calling main(). Doing it here also covers `uv run bot-agent dev|start`
# unchanged: livekit's CLI would load .env itself, but this keeps the
# behaviour independent of the version and makes the failure mode obvious.
load_dotenv()

# Must match the agent name dispatched by the webapp's token endpoint.
AGENT_NAME = "llm-bot"

DEFAULT_LANGUAGE = "it"
DEFAULT_LLM_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_LLM_MODEL = "deepseek-chat"
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_SPEED = "0.7"

DEFAULT_INSTRUCTIONS = (
    "Sei un assistente vocale che conversa a voce con l'utente. "
    "Rispondi in modo conciso e cordiale, in una o due frasi, "
    "come in una telefonata."
)

GREETING = "Saluta l'utente in una frase e chiedigli come puoi aiutarlo."

logger = logging.getLogger("bot-agent")

# The object `lk agent dev` looks for (the CLIError message is literal:
# "try to define the `server` variable"). Created at import time, after
# load_dotenv(), because the server may read LIVEKIT_URL / API key / secret
# from the environment.
server = AgentServer()


def _optional_env(name: str) -> str | None:
    """Read an env var, treating an empty string as "not set"."""
    value = os.getenv(name)
    return value if value else None


class Bot(Agent):
    """The conversational persona. Instructions come from BOT_INSTRUCTIONS."""

    def __init__(self) -> None:
        super().__init__(
            instructions=_optional_env("BOT_INSTRUCTIONS") or DEFAULT_INSTRUCTIONS
        )


# `agent_name` registers the worker under the name the webapp dispatches.
# This replaces `WorkerOptions(entrypoint_fnc=..., agent_name=...)`.
@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    language = _optional_env("BOT_LANGUAGE") or DEFAULT_LANGUAGE
    logger.info("starting llm-bot session (language=%s)", language)

    # Read the API key up front so a missing .env fails with a clear message
    # here, instead of surfacing later as an opaque 401 from the LLM provider.
    # We pass it to the plugin explicitly rather than relying on OPENAI_API_KEY,
    # so the worker never silently falls back to an OpenAI account.
    llm_api_key = _optional_env("LLM_API_KEY")
    if not llm_api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. Copy bot-agent/.env.example to .env and "
            "fill in your provider's API key."
        )

    # Constructing the plugins is synchronous and loads the local models.
    # That is deliberate (and matches how livekit's own silero.VAD.load() is
    # used): the job starts a fraction of a second slower, and the first
    # utterance never pays for the model load.
    session = AgentSession(
        # Both plugins are non-streaming, so the framework needs a VAD to cut
        # the incoming audio into utterances before transcribing them.
        vad=silero.VAD.load(),
        stt=WhisperSTT(
            language=language,
            model_size=_optional_env("WHISPER_MODEL") or DEFAULT_WHISPER_MODEL,
        ),
        # The plugin name is `openai`, but the service is whatever LLM_BASE_URL
        # points at. DeepSeek by default.
        llm=openai.LLM(
            model=_optional_env("LLM_MODEL") or DEFAULT_LLM_MODEL,
            base_url=_optional_env("LLM_BASE_URL") or DEFAULT_LLM_BASE_URL,
            api_key=llm_api_key,
        ),
        tts=PiperTTS(
            language=language,
            voice=_optional_env("BOT_VOICE"),
            speed=float(_optional_env("BOT_SPEED") or DEFAULT_SPEED),
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Bot(),
        # Publish both sides of the conversation into the room: the webapp
        # renders them from RoomEvent.TranscriptionReceived. Room-side
        # behaviour (audio and transcription publishing) is configured here
        # via RoomOutputOptions, not on the AgentSession constructor. The
        # default is True, but we set it explicitly so a future default change
        # can't silently swallow the transcript the UI depends on.
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )
    await session.generate_reply(instructions=GREETING)


def main() -> None:
    # `load_dotenv()` already ran at import time; no need to repeat it here.
    cli.run_app(server)


if __name__ == "__main__":
    main()
