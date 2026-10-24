from dotenv import load_dotenv
from google.genai import types as genai_types
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import ai_coustics, google

from prompts import AGENT_INSTRUCTIONS

load_dotenv(".env.local")

# NOTE (Taty adaptation, 2026-10-18): the upstream jarvis-voice-butler template wires in
# generic Playwright browser-automation tools (open any URL, click, type, purchase) via
# BrowserTools. That is deliberately NOT ported here — Taty's guardrails (ARCHITECTURE.md
# Decisiones #13-#17, HARNESS.md) forbid autonomous financial/web actions. Taty's real tools
# are read-only Contexia endpoints (/financials, /centinela/alerts, /radar/proyeccion-caja,
# /pricing/pre-cotizacion) plus a single write path, enqueue_draft() into Approval Queue —
# see the master plan's Pieza 4 (tools/contexia.py). Wire those in here once that module
# exists; until then this agent has no tools beyond ending the call.


class Assistant(Agent):
    def __init__(self) -> None:
        self._end_call_tool = EndCallTool(
            extra_description=(
                "Only end the call after the user clearly says they are finished, "
                "says goodbye, or directly asks to end the call."
            ),
            end_instructions=(
                "Da una despedida breve y cálida de Taty, luego termina la llamada."
            ),
        )
        super().__init__(
            # Gemini Live (multilingual, low latency) — same choice as the
            # jarvis-voice-butler reference. Voice set to a feminine-sounding Gemini Live
            # voice ("Aoede") per the founder's explicit requirement (voz femenina, not
            # VoiceBox/Tatiana's cloned voice — that stays gated by VOICE_ENABLED=false).
            # language="es-419" (Latin American Spanish) — verify against the current
            # Gemini Live API language list before the demo; not yet tested live.
            llm=google.beta.realtime.RealtimeModel(
                model="gemini-3.1-flash-live-preview",
                voice="Aoede",
                language="es-419",
                tool_response_scheduling=genai_types.FunctionResponseScheduling.WHEN_IDLE,
            ),
            instructions=AGENT_INSTRUCTIONS,
            tools=[
                *self._end_call_tool.tools,
            ],
        )


server = AgentServer()


@server.rtc_session(agent_name="taty-contadora")
async def taty_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Gemini realtime handles the voice input and output for this session.
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        # stt=inference.STT(model="deepgram/nova-3", language="en"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        # tts=inference.TTS(
        #   model="fishaudio/s2.1-pro", voice="fa4c9eb3dccc4806b382b40d61c6b10a"
        # ),
        turn_handling=TurnHandlingOptions(
            # The LiveKit turn detector determines when the user is done speaking and the agent should respond.
            # TurnDetector is an end-of-turn model that listens to the user's audio directly, combining
            # semantic understanding with acoustic cues (intonation, pitch, rhythm) for state-of-the-art accuracy.
            # AgentSession supplies the required VAD automatically.
            # See more at https://docs.livekit.io/agents/build/turns
            turn_detection=inference.TurnDetector(),
            # Adaptive interruptions use the turn detector to tell a real interruption from a
            # backchannel like "mhm" or "right", so the agent keeps talking through the latter.
            interruption={"mode": "adaptive"},
            # allow the LLM to generate a response while waiting for the end of turn
            # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
            preemptive_generation={"enabled": True},
        ),
        # Expressive mode injects the TTS provider's markup guide into the LLM prompt, so the model
        # emits inline delivery tags (emotion, pacing, non-verbal sounds) that the TTS renders and
        # the transcript never shows. Requires a TTS model that supports markup, such as the Fish
        # Audio model above.
        # expressive=True, 
    )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            video_input=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                ),
            ),
        ),
    )
    
    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
