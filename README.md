# HelloJade AI Call Center

AI-powered call center on GKE Autopilot with LiveKit, NVIDIA Riva STT, Chatterbox TTS, and vLLM.

## Architecture

```
Caller (PSTN) → Twilio → LiveKit SIP → LiveKit Server → Agent Worker
                                                            ├── Riva STT (GPU)
                                                            ├── vLLM LLM (GPU)
                                                            └── Chatterbox TTS (GPU)
```

## Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Media Server | LiveKit Server | WebRTC SFU, room management |
| SIP Bridge | LiveKit SIP | PSTN ↔ WebRTC bridging |
| Recording | LiveKit Egress | Call recording → GCS |
| Media Gateway | STUNner | TURN relay (Autopilot compat) |
| STT | NVIDIA Riva | Speech-to-text (self-hosted, GPU) |
| LLM | vLLM + Llama 3.1 8B | Agent brain (self-hosted, GPU) |
| TTS | Chatterbox | Text-to-speech (self-hosted, GPU) |
| SIP Provider | Twilio | Phone numbers, PSTN connectivity |

## Monorepo Structure

```
packages/
├── agent/              # Python LiveKit agent (voice AI)
├── chatterbox-tts/     # Chatterbox TTS FastAPI wrapper
├── k8s/
│   ├── base/           # Namespace, secrets, service accounts
│   ├── gateway/        # STUNner, Gateway API, TLS, Ingress
│   ├── livekit/        # LiveKit Server, SIP, Egress, Redis
│   ├── inference/      # Riva STT, vLLM, Chatterbox TTS
│   └── monitoring/     # Prometheus, Grafana (future)
docs/
├── plans/              # Design docs
├── architecture/       # Architecture diagrams
└── runbooks/           # Operational runbooks
```

## Infrastructure

- **Cluster**: `inference-autopilot` (GKE Autopilot, us-central1)
- **Namespace**: `call-center`
- **Domain**: `calls.hellojade.ai`
- **Static IP**: `34.117.31.39`
- **TLS**: Google-managed cert via Certificate Manager
- **Recordings**: `gs://call-center-recordings-hellojade`

## Deploy

```bash
# Create namespace and base resources
npm run deploy:namespace

# Deploy gateway (STUNner + Gateway API)
npm run deploy:gateway

# Deploy LiveKit stack (server, sip, egress, redis)
npm run deploy:livekit

# Deploy inference (Riva, vLLM, Chatterbox)
npm run deploy:inference
```
