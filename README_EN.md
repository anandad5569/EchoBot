<div align="center">

<img src="./assets/banner.jpg" width="100%" alt="EchoBot Banner" />

</div>

# EchoBot: Your Anime AI Companion

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> [中文文档 / Chinese README](./README.md)

**EchoBot** is an anime-style AI companion with Live2D support. It offers immersive role-play and emotional companionship, while quietly handling complex Agent productivity tasks like coding and file management in the background (๑>ᴗ<๑).

Whether you're using the web UI (with real-time voice and Live2D interaction) or chat platforms (QQ and Telegram supported), your companion is always ready to respond~

<p align="center">
  <img src="./assets/webui_1.png" alt="EchoBot WebUI Preview">
</p>

> The Live2D model shown in the demo is from: [【Free Model】Take this cute puppy home for free!](https://www.bilibili.com/video/BV1LM41137vK)

---

## ✨ Core Features

* **🎭 Immersive Live2D Interaction**: Real-time Live2D rendering and voice conversation in the browser.
* **🧠 Decision-Roleplay-Agent Three-Layer Architecture**: Fully decouples role-play from tool execution for fast responses without breaking character.
* **🛠️ Serious Productivity**: Local file read/write, scheduled and periodic tasks, Skills, and long-term memory — actually gets things done.
* **🌐 Multi-Platform Support**: Ready-to-use WebUI with seamless integration for QQ and Telegram.

---

## 🏗️ Core Architecture

Typical AI Agents are slow and token-heavy by nature due to large tool lists and skill systems. Mixing character settings with task instructions leads to "character dilution" and degrades execution efficiency.

EchoBot uses a **Decision - Roleplay - Agent** three-layer architecture to solve this:

### 1. 🧠 Decision Layer

Accurately and quickly identifies user intent.

* **Hybrid Intent Recognition**: Dual-engine using `Rules + Lightweight LLM`. Clear commands bypass the large model and trigger background tasks directly; ambiguous intent is classified by a lightweight LLM.
* **Smart Dispatch**: Casual chat is routed to the **Roleplay Layer**; complex tasks silently wake the **Agent Core** while the Roleplay Layer notifies the user that the task has started.

### 2. 🎭 Roleplay Layer

Focused purely on emotional value and immersion (๑˃̵ᴗ˂̵) ♡.

* **Clean Context**: Strips away tool-use metadata, optimized for text/voice generation — ensuring vivid tone, instant replies, and no out-of-character moments.
* **Context Awareness**: Intelligently switches dialogue based on system state (e.g., idle chat, task started, task completed).

### 3. ⚙️ Agent Core

Runs silently in the background to complete assigned tasks.

* **Full Agent Capabilities**: Integrated tool chains (Tools), skill libraries (Skills), and long/short-term memory (Memory).
* **System-Level Access**: Can read/write local files and interact with the operating system.
* **Async Collaboration**: Automatically summarizes results when done and has your anime companion personally deliver the report to you.

---

## 🔄 Workflow Examples

**Scenario A: Casual Chat**
> 🧑‍💻 **You**: "Good morning!"
> 🤖 **Decision Layer**: (Classified as casual chat) ➔ Forwarded to Roleplay Layer.
> 🌸 **Roleplay Layer**: "Good morning~ Let's have a great day today nya~"

**Scenario B: Complex Task Request**
> 🧑‍💻 **You**: "Write me a Python web scraper."
> 🤖 **Decision Layer**: (Rule matched) ➔ Triggers dual-track operation.
> 🌸 **Roleplay Layer** (instant reply): "Got it! I'll write that scraper for you right meow~"
> ⚙️ **Agent Core** (silent background execution): Search ➔ Write code ➔ Test code ➔ Return results.
> 🌸 **Roleplay Layer**: "Here it is! I worked really hard on this scraper, take a look~ [attached code file]"

---

## 🚀 Quick Start

💡 *Tip: Want to get up and running fast? Just hand this repo to a Coding Agent like Codex, Claude Code, or Cursor for one-click setup (≧∇≦)/*

### Install Dependencies

Python 3.11 or higher is recommended.

```shell
pip install -r requirements.txt
```

### Configure .env

Copy `.env.example` and rename it to `.env`, then fill in your LLM provider info (OpenAI-compatible format):

```text
LLM_API_KEY=your_api_key_here
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
```

### Start the Service

The following command starts both the chat platform gateway and the web UI:

```shell
python -m echobot app
```

### Start Using

Open your browser and visit the address below to meet your companion (≧◡≦) ♡:

```text
http://127.0.0.1:8000/web
```

---

## 🎨 Customization

### 👗 Import / Switch Live2D Models

A complete Live2D asset is typically a folder containing `.model3.json` and related files. The project ships with 2 built-in Live2D assets. You can upload or switch models directly from the web control panel:

<p align="center">
  <img src="./assets/webui_live2d.png" width="50%">
</p>

After uploading, the companion automatically copies the folder to `.echobot/live2d`. You can also manually copy a Live2D asset folder there — it will be loaded on next startup.

Eye-tracking (mouse follow) is enabled by default and can be toggled in the panel.

### 🖼️ Import / Switch Backgrounds

Upload your favorite background images via the web control panel:

<p align="center">
  <img src="./assets/webui_background.png" width="50%">
</p>

### 🖼️ Image Upload

For vision-capable models (e.g., qwen3.5-plus), you can send images directly to your companion. (Make sure the model supports vision — otherwise an empty response will be returned.)

<p align="center">
  <img src="./assets/webui_image.png" width="100%">
</p>

> The Live2D model shown in the demo is from: [【Ultra-Detailed Live2D Bulk Model】This bunny is so cute, I just have to eat you up!](https://www.bilibili.com/video/BV1YG6zYzEnN)

### ⏰ Scheduled & Periodic Tasks

Your companion can remember important things and execute them on time:

* **Cron Tasks**: Triggered at a specific time. Simply tell your companion "remind me to attend the meeting in 30 minutes" and a task will be created automatically.
  * Task data is stored in `.echobot/cron/jobs.json`.
* **Heartbeat Tasks**: Triggered at a fixed interval, defaulting to every 30 minutes.
  * Adjust the interval via `ECHOBOT_HEARTBEAT_INTERVAL_SECONDS` in `.env` (in seconds).
  * Edit the heartbeat task file from the web panel or directly at `.echobot/HEARTBEAT.md`.

<p align="center">
  <img src="./assets/webui_cron.png" height="300" alt="Cron Jobs">
  <img src="./assets/webui_heartbeat.png" height="300" alt="Heartbeat Jobs">
</p>

### 🚦 Router Mode

Switch the working mode manually in the web UI based on your needs:

🤖 **Auto (Default)**: Intelligently identifies intent and decides whether to invoke the background Agent (≧◡≦) ♡.

💬 **Chat Only**: Fully disables background tasks to prevent accidental triggers — perfect for companionship (⁄ ⁄•⁄ω⁄•⁄ ⁄).

🛠️ **Force Agent**: Become a relentless productivity machine — skips intent recognition and forces all messages through the background task pipeline (ง๑ •̀_•́)ง.

<p align="center">
<img src="./assets/webui_router.png" width="60%" alt="Router Mode">
</p>

### 🎙️ Voice Features (TTS & ASR)

EchoBot's web UI supports half-duplex voice interaction. Switch voice backends flexibly from the control panel:

**🗣️ Text-to-Speech (TTS):**

Two free backends are supported:

* [edge-tts](https://github.com/rany2/edge-tts): Online synthesis, free with no API key required.
* [kokoro-multi-lang-v1_1](https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html): Local offline synthesis; model weights are downloaded automatically on first launch.

<p align="center">
  <img src="./assets/webui_tts.png" width="75%">
</p>

**🎙️ Speech Recognition (ASR):**

Powered by the [SenseVoice](https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html) model via sherpa-onnx — fully local and offline; model weights are downloaded automatically on first launch.

EchoBot's web UI supports half-duplex voice interaction (microphone is muted during playback to prevent echo). Both "Push to Talk" and "Always-On Mic" modes are supported.

### 💡 Lighting & Effects

Adjust filters, lighting, and particle effects from the web control panel. Hold `Alt + Click` on a slider to reset it to its default value.

| Category | Parameters | Description |
|---|---|---|
| Toggles | Global Enable, Background Blur, Lighting, Light Drift, Air Particles | Enable or disable each rendering effect |
| Rendering | Background Blur (0–16), Hue (-180°–180°), Saturation (0–200%), Contrast (0–200%) | Adjust color and depth of field |
| Lighting Detail | Light X/Y (0–100%), Glow Intensity (0–160%), Vignette (0–60%), Grain (0–40%) | Control light source, vignette, and noise |
| Particle System | Density (0–100%), Opacity (0–160%), Size (40–240%), Speed (0–260%) | Control floating dust particles |

<p align="center">
  <img src="./assets/webui_light.png" width="50%">
</p>

Lighting effects enabled:

<p align="center">
  <img src="./assets/webui_light_on.png">
</p>

Lighting effects disabled:

<p align="center">
  <img src="./assets/webui_light_off.png">
</p>

> The Live2D model shown in the demo is from: [Live2D Official Free Sample](https://www.live2d.com/zh-CHS/learn/sample/)

---

## 📱 Chat Platform Integration

### 🐧 QQ Integration

Open the [QQ Open Platform](https://q.qq.com) and click the bot creation entry:

<p align="center">
  <img src="./assets/channel_qq_1.png">
</p>

Click "Create Bot" to get your `AppID` and `AppSecret`:

<p align="center">
  <img src="./assets/channel_qq_2.png">
</p>

Configure the QQ platform info in `.echobot/channels.json`:

```
"enabled": true
"app_id": "your AppID",
"client_secret": "your AppSecret"
```

Restart the service and you can chat with your companion directly in QQ~

<p align="center">
  <img src="./assets/channel_qq_3.jpg" width="50%">
</p>

### ✈️ Telegram Integration

Search for `@BotFather` in Telegram and open the official account (verified with a blue checkmark).

Send the command `/newbot` and follow the prompts to create a bot and get your `bot_token`.

Configure the Telegram platform info in `.echobot/channels.json`:

```
"enabled": true
"bot_token": "your bot_token",
"allow_from": ["your user ID"]
```

---

## 💻 Terminal & Chat Platform Commands

When running in the terminal or interacting via a chat platform, the following built-in commands are available for session management and persona switching~

### 📁 Session Management

| Command | Usage | Description |
|---|---|---|
| `/new` | `/new [title]` | Create a new session (optional title) |
| `/ls` | `/ls` | List all sessions |
| `/switch` | `/switch <number>` | Switch to the specified session |
| `/rename` | `/rename <title>` | Rename the current session |
| `/delete` | `/delete` | Delete the current session |
| `/current` | `/current` | View current session info |
| `/help` | `/help` | Show command help |

### 🎭 Role Management

| Command | Usage | Description |
|---|---|---|
| `/role` | `/role` | View current character card |
| `/role list` | `/role list` | List all character cards |
| `/role current` | `/role current` | View current character card details |
| `/role set` | `/role set <name>` | Switch to a specified character card |
| `/role help` | `/role help` | Show role command help |

---

## 💖 Acknowledgements

Standing on the shoulders of giants is what makes this companion so smart and adorable! EchoBot was inspired by and built upon the following excellent open-source projects (deep bow 🙇‍♀️):

* **[nanobot](https://github.com/HKUDS/nanobot)**
* **[CoPaw](https://github.com/agentscope-ai/CoPaw)**
* **[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)**
* **[AstrBot](https://github.com/AstrBotDevs/AstrBot)**
