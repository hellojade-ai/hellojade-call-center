# AI Call Center Design Document

**Date**: 2026-02-20
**Status**: Approved

## Overview

Build an AI-powered call center on GKE Autopilot that handles inbound and outbound phone calls using self-hosted inference models.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform | LiveKit (Server + SIP + Agents + Egress) | Only platform with native SIP + AI Agents + K8s support |
| Cluster | GKE Autopilot (`inference-autopilot`, us-central1) | Existing cluster with GPU support |
| Media Gateway | STUNner | Autopilot forbids hostNetwork; STUNner provides TURN relay |
| STT | NVIDIA Riva (self-hosted, L4 GPU) | True gRPC streaming, first-party LiveKit plugin |
| TTS | Chatterbox (self-hosted, L4 GPU) | MIT license, voice cloning, 23 languages |
| LLM | vLLM + Llama 3.1 8B Instruct (self-hosted, L4 GPU) | Best speed/quality for voice agents on L4 |
| SIP Provider | Twilio | Account exists, Elastic SIP Trunking |
| Namespace | `call-center` (single namespace) | Tight pipeline coupling, simpler networking |
| Domain | `calls.hellojade.ai` | Static IP: 34.117.31.39 |
| Recording | All calls → GCS (`call-center-recordings-hellojade`) | LiveKit Egress with Workload Identity |
| Agent | Single general-purpose agent | Start simple, add multi-agent handoff later |
| Deployment | kubectl apply, no Terraform | Direct YAML to existing cluster |

## Architecture

```
Caller (PSTN) → Twilio → LiveKit SIP (LB:5060) → LiveKit Server
                                                        ↕ Redis
WebRTC Client → STUNner (LB:3478) → LiveKit Server
                                                        ↓
                                               Agent Worker (Python)
                                                 ├── Riva STT (gRPC:50051)
                                                 ├── vLLM (HTTP:8000)
                                                 └── Chatterbox TTS (HTTP:8880)
                                                        ↓
                                               LiveKit Egress → GCS
```

### External Entry Points

1. **Gateway API** (TCP:443) — `calls.hellojade.ai` → LiveKit signaling (WebSocket)
2. **STUNner LB** (UDP:3478) — TURN media relay for WebRTC clients
3. **SIP LB** (UDP:5060) — Twilio sends SIP INVITEs here

## Components

### LiveKit Stack
- **LiveKit Server**: 2 replicas, 2 CPU / 4Gi each, terminationGrace 5hr
- **LiveKit SIP**: 2 replicas, 1 CPU / 2Gi each, LoadBalancer for Twilio
- **LiveKit Egress**: 2 replicas, 2 CPU / 4Gi each, GCS via Workload Identity
- **LiveKit Agent**: 2-8 replicas (HPA at 50% CPU), 4 CPU / 8Gi each
- **Redis**: 1 replica, 500m CPU / 1Gi, PVC for persistence

### Inference (GPU)
- **Riva STT**: 1 replica, 1x L4 GPU, gRPC streaming, ~50-100 concurrent sessions
- **vLLM**: 1 replica, 1x L4 GPU, Llama 3.1 8B, ~25-50 concurrent chats
- **Chatterbox TTS**: 1 replica, 1x L4 GPU, custom FastAPI wrapper, ~10-30 concurrent streams

### Networking
- **Gateway API** (`gke-l7-global-external-managed`) with Certificate Manager TLS
- **STUNner** Gateway with UDPRoute to LiveKit Server
- **L4 LoadBalancer** for SIP service

## Chatterbox TTS Wrapper

Chatterbox has no OpenAI-compatible API. We build a FastAPI server that exposes `POST /v1/audio/speech` so LiveKit's `openai.TTS(base_url=...)` plugin works natively.

## Container Images

| Package | Build Method | Image |
|---------|-------------|-------|
| Agent | Google Cloud Buildpacks | `us-central1-docker.pkg.dev/hello-jade/call-center/agent` |
| Chatterbox TTS | Google Cloud Buildpacks | `us-central1-docker.pkg.dev/hello-jade/call-center/chatterbox-tts` |
| Riva STT | Pre-built NVIDIA image | `nvcr.io/nvidia/riva/riva-speech:2.17.0` |
| vLLM | Pre-built image | `vllm/vllm-openai:v0.8.5.post1` |
| LiveKit Server | Pre-built image | `livekit/livekit-server:latest` |
| LiveKit SIP | Pre-built image | `livekit/sip:latest` |
| LiveKit Egress | Pre-built image | `livekit/egress:latest` |

Buildpacks auto-detect Python via `requirements.txt` + `Procfile`. No Dockerfiles needed for custom packages.

**Note**: Chatterbox TTS needs CUDA runtime for GPU inference. If Cloud Buildpacks fail due to torch+cuda, fall back to a Dockerfile with `pytorch/pytorch` base image.

## Scale Target

25-100 concurrent calls at launch. 3x L4 GPUs (~$2.10/hr = ~$1,500/mo) for inference.
