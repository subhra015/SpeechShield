# 🛡️ SpeechShield
### A Deep Learning–Based Synthetic Speech Detection System — From Frozen Model to Controlled Full-Stack Application

![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![PyTorch 2.11](https://img.shields.io/badge/PyTorch-2.11%20CUDA%2012.8-EE4C2C?logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![React 19](https://img.shields.io/badge/React-19%20%2B%20TypeScript%205.7-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/Backend%20tests-90%20passed-brightgreen)
![Parity](https://img.shields.io/badge/V4%20parity-PASS-brightgreen)
![Status](https://img.shields.io/badge/Production%20inference-DISABLED-lightgrey)

> **The 3-minute gist**
> SpeechShield answers one question: *is this recording genuine human speech, or AI-generated / manipulated speech?*
> It is a **binary classifier** (0 = BONAFIDE, 1 = SPOOF) built on a frozen **97,761-parameter CompactCNN (V4)** that reads a normalized **64×401 log-Mel spectrogram**, wrapped in a **secure FastAPI + React application**.
> What makes it unusual is the **engineering discipline around the model**: speaker-independent training splits, multi-generator synthetic data, SHA-256-verified frozen checkpoints, **numerical parity validation** proving the app reproduces training-time preprocessing exactly, strict job/run state machines, ownership-enforced private audio storage, and an openly documented **real-world domain-shift limitation**.
> **Read §1–§2 for the working principle, §3 for architecture, §4–§5 for data & evidence, §8 for the map into the code.**

---

## Table of Contents
1. [Problem & Scope](#1-problem--scope)
2. [Working Principle](#2-working-principle)
3. [System Architecture & Data Model](#3-system-architecture--data-model)
4. [Datasets](#4-datasets)
5. [Model Card: Configuration, Metrics, Parity, Domain Shift](#5-model-card)
6. [Technology Stack](#6-technology-stack)
7. [Security Model](#7-security-model)
8. [Repository Layout & "Question → Code File" Map](#8-repository-layout--code-map)
9. [Quickstart](#9-quickstart)
10. [Testing & CI](#10-testing--ci)
11. [Development History](#11-development-history)
12. [Limitations & Honest Boundaries](#12-limitations--honest-boundaries)
13. [Misconception Checklist](#13-misconception-checklist)
14. [License & Contact](#14-license--contact)

---

## 1. Problem & Scope

Neural TTS and voice-conversion systems now produce speech that humans cannot reliably distinguish from real recordings, enabling impersonation, fraudulent voice messages, fabricated audio evidence and social-engineering attacks.

SpeechShield formulates detection as supervised binary classification over acoustic representations:

| Class | Label | Meaning |
|---|---|---|
| 0 | `BONAFIDE` | Genuine human speech |
| 1 | `SPOOF` | Synthetic (TTS) or converted (VC) speech |

**What SpeechShield IS:** a reproducible detector + a controlled application pipeline with verified preprocessing parity, checkpoint integrity, authorization gates and regression tests.
**What SpeechShield IS NOT:** a speaker-identification tool, a calibrated probability estimator, or a production-approved forensic authority.

---

## 2. Working Principle

### 2.1 The audio signal chain

Every recording — during training *and* inside the application — travels through this exact chain. The application's job is to reproduce it bit-faithfully:

```text
 File bytes (WAV / FLAC)
        │  decode (soundfile)
        ▼
 PCM  ·  sr ∈ [8 kHz … 96 kHz]  ·  ≤ 2 channels
        │  mono mixdown → resample to 16 000 Hz
        ▼
 Waveform @ 16 kHz
        │  centre pad / trim → exactly 64 000 samples (4.000 s)
        ▼
 Standardized waveform
        │  Mel filterbank: n_fft = 512 · hop = 160 · n_mels = 64
        ▼
 Mel spectrogram  (64 × 401)
        │  log(·)
        ▼
 Log-Mel  (64 × 401)
        │  per-recording normalization (μ, σ)
        ▼
 Normalized FP32 features
        │  FP16 cache round-trip  ← training-parity requirement
        ▼
 Model input tensor  (1, 1, 64, 401)
        │  CompactCNN V4  (97 761 params, frozen)
        ▼
 Raw logit z
        │  p = sigmoid(z / T),  T = 1.0
        ▼
 Spoof probability p
