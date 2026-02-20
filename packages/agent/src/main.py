"""HelloJade AI Call Center Agent

LiveKit voice agent with:
- NVIDIA Riva STT (self-hosted, gRPC streaming)
- vLLM + Llama 3.1 8B (self-hosted, OpenAI-compatible)
- Chatterbox TTS (self-hosted, OpenAI-compatible wrapper)
"""

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, function_tool, AgentServer
from livekit.plugins import openai, nvidia, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import room_io

server = AgentServer()


class CallCenterAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a helpful AI call center agent for HelloJade. "
                "Be concise, friendly, and professional. "
                "Ask clarifying questions when needed. "
                "If you cannot help, offer to transfer to a human agent."
            ),
        )

    # TODO: Add function tools for:
    # - Account lookup
    # - Call transfer
    # - FAQ retrieval
    # - Appointment scheduling


@server.rtc_session(agent_name="call-center-agent")
async def handle_call(ctx: agents.JobContext):
    session = AgentSession(
        stt=nvidia.STT(
            server="riva-stt.call-center.svc.cluster.local:50051",
            use_ssl=False,
            language="en-US",
            automatic_punctuation=True,
        ),
        llm=openai.LLM(
            model="meta-llama/Llama-3.1-8B-Instruct",
            base_url="http://vllm.call-center.svc.cluster.local:8000/v1",
            api_key="not-needed",
            temperature=0.7,
        ),
        tts=openai.TTS(
            model="chatterbox",
            voice="default",
            base_url="http://chatterbox-tts.call-center.svc.cluster.local:8880/v1",
            api_key="not-needed",
            response_format="wav",
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=CallCenterAgent(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    await session.generate_reply(
        instructions="Greet the caller warmly and ask how you can help them today."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
