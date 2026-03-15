import {
    DOM,
    TTS_STREAM_FIRST_SEGMENT_SENTENCES,
    TTS_STREAM_MAX_SEGMENT_LENGTH,
    TTS_STREAM_SENTENCE_BATCH_SIZE,
    UI_STATE,
} from "./state.js";

const EMOJI_PATTERN = /[\u200D\u20E3\uFE0E\uFE0F\u{1F1E6}-\u{1F1FF}\u{1F3FB}-\u{1F3FF}\u{1F300}-\u{1F5FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu;

export function createTtsModule(deps) {
    const {
        addMessage,
        applyMouthValue,
        clamp,
        requestJson,
        responseToError,
        setConnectionState,
        setRunStatus,
        smoothValue,
    } = deps;

    let hooks = {
        updateVoiceInputControls() {},
    };

    function bindHooks(nextHooks) {
        hooks = {
            ...hooks,
            ...(nextHooks || {}),
        };
    }

    function loadSavedTtsProvider() {
        return String(window.localStorage.getItem("echobot.web.tts.provider") || "").trim();
    }

    function persistTtsProvider(provider) {
        window.localStorage.setItem("echobot.web.tts.provider", provider);
    }

    function ttsVoiceStorageKey(provider) {
        const normalizedProvider = String(provider || "default").trim() || "default";
        return `echobot.web.tts.voice.${normalizedProvider}`;
    }

    function loadSavedTtsVoice(provider) {
        return String(window.localStorage.getItem(ttsVoiceStorageKey(provider)) || "").trim();
    }

    function persistTtsVoice(provider, voice) {
        window.localStorage.setItem(ttsVoiceStorageKey(provider), voice);
    }

    function resolveInitialTtsProvider(ttsConfig) {
        const providers = Array.isArray(ttsConfig && ttsConfig.providers)
            ? ttsConfig.providers
            : [];
        const providerNames = providers
            .map((item) => String((item && item.name) || ""))
            .filter(Boolean);
        const savedProvider = loadSavedTtsProvider();
        if (providerNames.includes(savedProvider)) {
            return savedProvider;
        }

        const defaultProvider = String((ttsConfig && ttsConfig.default_provider) || "edge");
        if (providerNames.includes(defaultProvider)) {
            return defaultProvider;
        }

        return providerNames[0] || defaultProvider;
    }

    function findTtsProviderStatus(ttsConfig, provider) {
        const providers = Array.isArray(ttsConfig && ttsConfig.providers)
            ? ttsConfig.providers
            : [];
        return providers.find((item) => item.name === provider) || null;
    }

    function renderTtsProviderOptions(ttsConfig, selectedProvider) {
        if (!DOM.ttsProviderSelect) {
            return;
        }

        DOM.ttsProviderSelect.innerHTML = "";
        const providers = Array.isArray(ttsConfig && ttsConfig.providers)
            ? ttsConfig.providers
            : [];

        providers.forEach((providerStatus) => {
            const option = document.createElement("option");
            option.value = providerStatus.name;
            option.textContent = providerStatus.available
                ? providerStatus.label
                : `${providerStatus.label} (未就绪)`;
            DOM.ttsProviderSelect.appendChild(option);
        });

        DOM.ttsProviderSelect.disabled = providers.length <= 1;
        if (selectedProvider) {
            DOM.ttsProviderSelect.value = selectedProvider;
        }
    }

    function buildTtsDetail(providerStatus) {
        if (!providerStatus) {
            return "当前没有可用的 TTS provider";
        }
        if (providerStatus.available) {
            return `${providerStatus.label} 已启用`;
        }
        return providerStatus.detail || `${providerStatus.label} 未就绪`;
    }

    async function loadTtsOptions(ttsConfig) {
        const provider = resolveInitialTtsProvider(ttsConfig);
        UI_STATE.selectedTtsProvider = provider;
        renderTtsProviderOptions(ttsConfig, provider);
        persistTtsProvider(provider);
        await loadVoiceOptions(ttsConfig, provider);
    }

    async function handleTtsProviderChange() {
        if (!DOM.ttsProviderSelect || !UI_STATE.config || !UI_STATE.config.tts) {
            return;
        }

        const provider = DOM.ttsProviderSelect.value;
        UI_STATE.selectedTtsProvider = provider;
        persistTtsProvider(provider);
        await loadVoiceOptions(UI_STATE.config.tts, provider);
    }

    function handleVoiceSelectionChange() {
        UI_STATE.selectedVoice = DOM.voiceSelect.value;
        persistTtsVoice(UI_STATE.selectedTtsProvider, UI_STATE.selectedVoice);
    }

    async function loadVoiceOptions(ttsConfig, provider) {
        const providerName = provider || UI_STATE.selectedTtsProvider || ttsConfig.default_provider || "edge";
        const defaultVoices = ttsConfig.default_voices || {};
        const selectedVoiceFromStorage = loadSavedTtsVoice(providerName);
        const defaultVoice = selectedVoiceFromStorage
            || defaultVoices[providerName]
            || "";
        UI_STATE.selectedVoice = defaultVoice;
        UI_STATE.selectedTtsProvider = providerName;

        if (DOM.ttsProviderSelect) {
            DOM.ttsProviderSelect.value = providerName;
        }

        DOM.ttsDetail.textContent = buildTtsDetail(
            findTtsProviderStatus(ttsConfig, providerName),
        );

        try {
            const payload = await requestJson(
                `/api/web/tts/voices?provider=${encodeURIComponent(providerName)}`,
            );
            renderVoiceOptions(payload.voices, defaultVoice, providerName);
        } catch (error) {
            console.error(error);
            DOM.voiceSelect.innerHTML = "";
            DOM.voiceSelect.disabled = true;
            DOM.ttsDetail.textContent = error.message || "语音列表加载失败";
        }
    }

    function renderVoiceOptions(voices, selectedVoice, provider) {
        DOM.voiceSelect.innerHTML = "";

        if (!voices || voices.length === 0) {
            DOM.voiceSelect.disabled = true;
            DOM.ttsDetail.textContent = "没有可用语音";
            return;
        }

        const preferredVoices = voices
            .slice()
            .sort((left, right) => {
                const leftScore = scoreVoiceOption(left);
                const rightScore = scoreVoiceOption(right);
                if (leftScore !== rightScore) {
                    return rightScore - leftScore;
                }
                return `${left.locale}-${left.short_name}`.localeCompare(`${right.locale}-${right.short_name}`);
            });

        preferredVoices.forEach((voice) => {
            const option = document.createElement("option");
            option.value = voice.short_name;
            option.textContent = buildVoiceLabel(voice);
            DOM.voiceSelect.appendChild(option);
        });

        const finalVoice = preferredVoices.some((item) => item.short_name === selectedVoice)
            ? selectedVoice
            : preferredVoices[0].short_name;

        DOM.voiceSelect.value = finalVoice;
        DOM.voiceSelect.disabled = false;
        UI_STATE.selectedVoice = finalVoice;
        persistTtsVoice(provider, finalVoice);
    }

    function buildVoiceLabel(voice) {
        const primaryName = voice.display_name || voice.short_name || voice.name;
        const parts = [primaryName];
        if (voice.short_name && voice.short_name !== primaryName) {
            parts.push(voice.short_name);
        }
        if (voice.locale) {
            parts.push(voice.locale);
        }
        if (voice.gender) {
            parts.push(voice.gender);
        }
        return parts.join(" · ");
    }

    function scoreVoiceOption(voice) {
        let score = 0;
        if ((voice.locale || "").startsWith("zh-CN")) {
            score += 30;
        } else if ((voice.locale || "").startsWith("zh-")) {
            score += 20;
        }
        if ((voice.short_name || "").includes("Xiaoxiao")) {
            score += 8;
        }
        if ((voice.short_name || "").includes("Neural")) {
            score += 4;
        }
        return score;
    }

    async function speakText(text, options = {}) {
        const preparedText = prepareTextForTts(text);
        if (!preparedText) {
            return;
        }

        if (!UI_STATE.ttsEnabled) {
            return;
        }

        stopSpeechPlayback();
        const speechSession = createSpeechSession();
        enqueueSpeechSegment(speechSession, preparedText);
        const completionPromise = finalizeSpeechSession(speechSession);

        if (Boolean(options.waitUntilEnd)) {
            await completionPromise;
            return;
        }

        await waitForSpeechSessionStart(speechSession);
    }

    function createSpeechSession() {
        const speechSession = {
            turnId: ++UI_STATE.speechTurnCounter,
            rawText: "",
            pendingText: "",
            nextSentenceTarget: TTS_STREAM_FIRST_SEGMENT_SENTENCES,
            queue: [],
            nextPlaybackIndex: 0,
            finalized: false,
            cancelled: false,
            eventResolvers: [],
            firstPlaybackStarted: false,
            resolveFirstPlaybackStarted: null,
            firstPlaybackStartedPromise: null,
            playbackPromise: null,
        };

        speechSession.firstPlaybackStartedPromise = new Promise((resolve) => {
            speechSession.resolveFirstPlaybackStarted = resolve;
        });

        UI_STATE.activeSpeechSession = speechSession;
        DOM.stopAudioButton.disabled = false;
        return speechSession;
    }

    function cancelSpeechSession(speechSession) {
        if (!speechSession || speechSession.cancelled) {
            return;
        }

        speechSession.cancelled = true;
        speechSession.finalized = true;
        resolveSpeechSessionStart(speechSession);
        notifySpeechSessionEvent(speechSession);

        if (UI_STATE.activeSpeechSession === speechSession) {
            UI_STATE.activeSpeechSession = null;
        }
    }

    function queueSpeechSessionText(speechSession, delta) {
        if (!speechSession || speechSession.cancelled || !UI_STATE.ttsEnabled) {
            return;
        }

        const text = String(delta || "");
        if (!text) {
            return;
        }

        speechSession.rawText += text;
        speechSession.pendingText += text;
        drainSpeechSessionSegments(speechSession, false);
    }

    function finalizeSpeechSession(speechSession, finalText = "") {
        if (!speechSession || speechSession.cancelled || !UI_STATE.ttsEnabled) {
            return Promise.resolve();
        }

        appendSpeechSessionFinalText(speechSession, finalText);
        speechSession.finalized = true;
        drainSpeechSessionSegments(speechSession, true);
        notifySpeechSessionEvent(speechSession);

        if (!speechSession.queue.length) {
            resolveSpeechSessionStart(speechSession);
            if (UI_STATE.activeSpeechSession === speechSession) {
                UI_STATE.activeSpeechSession = null;
            }
            DOM.stopAudioButton.disabled = true;
            setConnectionState("ready", "已连接");
            return Promise.resolve();
        }

        return waitForSpeechSession(speechSession);
    }

    function appendSpeechSessionFinalText(speechSession, finalText) {
        const finalValue = String(finalText || "");
        if (!finalValue) {
            return;
        }

        if (!speechSession.rawText) {
            speechSession.rawText = finalValue;
            speechSession.pendingText += finalValue;
            return;
        }

        if (finalValue.startsWith(speechSession.rawText)) {
            const suffix = finalValue.slice(speechSession.rawText.length);
            if (suffix) {
                speechSession.pendingText += suffix;
            }
            speechSession.rawText = finalValue;
            return;
        }

        if (!speechSession.queue.length && !speechSession.pendingText.trim()) {
            speechSession.pendingText = finalValue;
        }
        speechSession.rawText = finalValue;
    }

    function drainSpeechSessionSegments(speechSession, forceFlush) {
        while (true) {
            const segmentText = takeSpeechSegmentFromBuffer(speechSession, forceFlush);
            if (!segmentText) {
                break;
            }

            enqueueSpeechSegment(speechSession, segmentText);
            speechSession.nextSentenceTarget = TTS_STREAM_SENTENCE_BATCH_SIZE;
        }
    }

    function takeSpeechSegmentFromBuffer(speechSession, forceFlush) {
        const pendingText = speechSession.pendingText;
        if (!pendingText.trim()) {
            speechSession.pendingText = "";
            return "";
        }

        const sentenceBoundaryIndex = findNthSentenceBoundaryIndex(
            pendingText,
            speechSession.nextSentenceTarget,
        );

        let splitIndex = -1;
        if (
            sentenceBoundaryIndex !== -1
            && sentenceBoundaryIndex <= TTS_STREAM_MAX_SEGMENT_LENGTH
        ) {
            splitIndex = sentenceBoundaryIndex;
        } else if (pendingText.length >= TTS_STREAM_MAX_SEGMENT_LENGTH) {
            splitIndex = findForcedSpeechSplitIndex(
                pendingText,
                TTS_STREAM_MAX_SEGMENT_LENGTH,
            );
        } else if (forceFlush) {
            splitIndex = sentenceBoundaryIndex !== -1
                ? sentenceBoundaryIndex
                : pendingText.length;
        }

        if (splitIndex <= 0) {
            return "";
        }

        const segmentText = pendingText.slice(0, splitIndex).trim();
        speechSession.pendingText = pendingText.slice(splitIndex);
        return segmentText;
    }

    function findNthSentenceBoundaryIndex(text, targetCount) {
        let seenBoundaries = 0;

        for (let index = 0; index < text.length; index += 1) {
            if (!isSentenceBoundaryAt(text, index)) {
                continue;
            }

            seenBoundaries += 1;
            if (seenBoundaries === targetCount) {
                return consumeSplitSuffix(text, index);
            }
        }

        return -1;
    }

    function findForcedSpeechSplitIndex(text, maxLength) {
        const limit = Math.min(maxLength, text.length);

        for (let index = limit - 1; index >= 0; index -= 1) {
            if (isSentenceBoundaryAt(text, index)) {
                return consumeSplitSuffix(text, index);
            }
        }

        for (let index = limit - 1; index >= 0; index -= 1) {
            if (isSoftSpeechSplitCharacter(text[index])) {
                return consumeSplitSuffix(text, index);
            }
        }

        for (let index = limit - 1; index >= 0; index -= 1) {
            if (/\s/.test(text[index])) {
                return index + 1;
            }
        }

        return limit;
    }

    function isSentenceBoundaryAt(text, index) {
        const character = text[index];
        if (!".!?。！？；;".includes(character)) {
            return false;
        }

        if (character === ".") {
            const previous = text[index - 1] || "";
            const next = text[index + 1] || "";
            if (/\d/.test(previous) && /\d/.test(next)) {
                return false;
            }
            if (previous === "." || next === ".") {
                return false;
            }
        }

        return true;
    }

    function isSoftSpeechSplitCharacter(character) {
        return ",，、:：\n".includes(character);
    }

    function consumeSplitSuffix(text, index) {
        let nextIndex = index + 1;

        while (nextIndex < text.length && "\"'”’」』）》】".includes(text[nextIndex])) {
            nextIndex += 1;
        }
        while (nextIndex < text.length && /\s/.test(text[nextIndex])) {
            nextIndex += 1;
        }

        return nextIndex;
    }

    function enqueueSpeechSegment(speechSession, text) {
        const preparedText = prepareTextForTts(text);
        if (!preparedText) {
            return;
        }

        speechSession.queue.push({
            audioBufferPromise: synthesizeSpeechAudioBuffer(
                preparedText,
                speechSession.turnId,
            ),
        });
        DOM.stopAudioButton.disabled = false;
        ensureSpeechSessionPlayback(speechSession);
    }

    function ensureSpeechSessionPlayback(speechSession) {
        if (!speechSession.playbackPromise) {
            speechSession.playbackPromise = runSpeechSessionPlaybackLoop(speechSession);
        }
        return speechSession.playbackPromise;
    }

    function waitForSpeechSession(speechSession) {
        if (!speechSession) {
            return Promise.resolve();
        }
        return speechSession.playbackPromise || Promise.resolve();
    }

    async function waitForSpeechSessionStart(speechSession) {
        if (!speechSession) {
            return;
        }

        await Promise.race([
            speechSession.firstPlaybackStartedPromise,
            waitForSpeechSession(speechSession),
        ]);
    }

    async function runSpeechSessionPlaybackLoop(speechSession) {
        try {
            while (true) {
                if (isSpeechSessionInactive(speechSession)) {
                    break;
                }

                if (speechSession.nextPlaybackIndex < speechSession.queue.length) {
                    const item = speechSession.queue[speechSession.nextPlaybackIndex];
                    DOM.stopAudioButton.disabled = false;

                    let audioBuffer;
                    try {
                        audioBuffer = await item.audioBufferPromise;
                    } catch (error) {
                        if (!isSpeechSessionInactive(speechSession)) {
                            reportSpeechError(error);
                        }
                        break;
                    }

                    if (isSpeechSessionInactive(speechSession)) {
                        break;
                    }

                    speechSession.nextPlaybackIndex += 1;
                    if (!audioBuffer) {
                        continue;
                    }

                    resolveSpeechSessionStart(speechSession);

                    try {
                        await playSpeechAudioBuffer(audioBuffer, speechSession.turnId);
                    } catch (error) {
                        if (!isSpeechSessionInactive(speechSession)) {
                            reportSpeechError(error);
                        }
                        break;
                    }
                    continue;
                }

                if (speechSession.finalized) {
                    break;
                }

                await waitForSpeechSessionEvent(speechSession);
            }
        } finally {
            resolveSpeechSessionStart(speechSession);
            if (UI_STATE.activeSpeechSession === speechSession) {
                UI_STATE.activeSpeechSession = null;
            }
            if (!UI_STATE.audioSourceNode && !UI_STATE.activeSpeechSession) {
                DOM.stopAudioButton.disabled = true;
                setConnectionState("ready", "已连接");
            }
            notifySpeechSessionEvent(speechSession);
        }
    }

    function isSpeechSessionInactive(speechSession) {
        return (
            !speechSession
            || speechSession.cancelled
            || UI_STATE.activeSpeechSession !== speechSession
        );
    }

    function waitForSpeechSessionEvent(speechSession) {
        return new Promise((resolve) => {
            speechSession.eventResolvers.push(resolve);
        });
    }

    function notifySpeechSessionEvent(speechSession) {
        if (!speechSession || speechSession.eventResolvers.length === 0) {
            return;
        }

        const resolvers = speechSession.eventResolvers.splice(0);
        resolvers.forEach((resolve) => resolve());
    }

    function resolveSpeechSessionStart(speechSession) {
        if (!speechSession || speechSession.firstPlaybackStarted) {
            return;
        }

        speechSession.firstPlaybackStarted = true;
        if (speechSession.resolveFirstPlaybackStarted) {
            speechSession.resolveFirstPlaybackStarted();
            speechSession.resolveFirstPlaybackStarted = null;
        }
    }

    async function synthesizeSpeechAudioBuffer(text, turnId) {
        if (!isSpeechTurnActive(turnId)) {
            return null;
        }

        await ensureAudioContextReady();
        if (!isSpeechTurnActive(turnId)) {
            return null;
        }

        setConnectionState("busy", "语音合成中");
        DOM.stopAudioButton.disabled = false;

        const response = await fetch("/api/web/tts", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                text: text,
                provider: UI_STATE.selectedTtsProvider || UI_STATE.config.tts.default_provider,
                voice: UI_STATE.selectedVoice
                    || (UI_STATE.config.tts.default_voices || {})[UI_STATE.selectedTtsProvider]
                    || UI_STATE.config.tts.default_voice,
            }),
        });

        if (!response.ok) {
            throw await responseToError(response);
        }
        if (!isSpeechTurnActive(turnId)) {
            return null;
        }

        const audioBytes = await response.arrayBuffer();
        if (!isSpeechTurnActive(turnId)) {
            return null;
        }

        return await UI_STATE.audioContext.decodeAudioData(audioBytes.slice(0));
    }

    async function playSpeechAudioBuffer(audioBuffer, turnId) {
        if (!audioBuffer || !isSpeechTurnActive(turnId)) {
            return;
        }

        const sourceNode = UI_STATE.audioContext.createBufferSource();
        const analyserNode = UI_STATE.audioContext.createAnalyser();
        analyserNode.fftSize = 1024;

        sourceNode.buffer = audioBuffer;
        sourceNode.connect(analyserNode);
        analyserNode.connect(UI_STATE.audioContext.destination);

        UI_STATE.audioSourceNode = sourceNode;
        UI_STATE.audioAnalyser = analyserNode;
        UI_STATE.volumeBuffer = new Uint8Array(analyserNode.fftSize);
        UI_STATE.speaking = true;
        hooks.updateVoiceInputControls();

        const playbackEnded = new Promise((resolve) => {
            UI_STATE.speechEndedResolver = resolve;
        });

        sourceNode.onended = () => {
            clearSpeechState();
        };

        startLipSyncLoop();
        sourceNode.start(0);
        setRunStatus("正在播报回复");
        await playbackEnded;
    }

    function prepareTextForTts(text) {
        return String(text || "")
            .replace(/\r\n?/g, "\n")
            .replace(/^\s*(```|~~~)[^\n]*$/gm, "")
            .replace(/`([^`]+)`/g, "$1")
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
            .replace(/^\s{0,3}#{1,6}\s+/gm, "")
            .replace(/^\s*>\s?/gm, "")
            .replace(/^\s*[-*+]\s+/gm, "")
            .replace(/^\s*\d+[.)]\s+/gm, "")
            .replace(/[*_~]/g, "")
            .replace(EMOJI_PATTERN, " ")
            .replace(/\n{3,}/g, "\n\n")
            .replace(/[ \t]+\n/g, "\n")
            .replace(/[ \t]{2,}/g, " ")
            .trim();
    }

    function isSpeechTurnActive(turnId) {
        const speechSession = UI_STATE.activeSpeechSession;
        return Boolean(
            speechSession
            && speechSession.turnId === turnId
            && !speechSession.cancelled
            && UI_STATE.ttsEnabled,
        );
    }

    function reportSpeechError(error) {
        console.error(error);
        clearSpeechState();
        DOM.stopAudioButton.disabled = true;
        setRunStatus(error.message || "语音播放失败");
        addMessage("system", `TTS 失败：${error.message || error}`, "状态");
    }

    function stopSpeechPlayback() {
        cancelSpeechSession(UI_STATE.activeSpeechSession);
        if (UI_STATE.audioSourceNode) {
            try {
                UI_STATE.audioSourceNode.stop();
            } catch (error) {
                console.warn("Audio stop ignored", error);
            }
        }
        clearSpeechState();
        DOM.stopAudioButton.disabled = true;
        setConnectionState("ready", "已连接");
    }

    function clearSpeechState() {
        if (UI_STATE.audioSourceNode) {
            try {
                UI_STATE.audioSourceNode.disconnect();
            } catch (error) {
                console.warn("Audio source disconnect ignored", error);
            }
        }
        if (UI_STATE.audioAnalyser) {
            try {
                UI_STATE.audioAnalyser.disconnect();
            } catch (error) {
                console.warn("Audio analyser disconnect ignored", error);
            }
        }

        UI_STATE.audioSourceNode = null;
        UI_STATE.audioAnalyser = null;
        UI_STATE.volumeBuffer = null;
        UI_STATE.speaking = false;
        UI_STATE.currentMouthValue = 0;
        hooks.updateVoiceInputControls();

        if (UI_STATE.lipSyncFrameId) {
            window.cancelAnimationFrame(UI_STATE.lipSyncFrameId);
            UI_STATE.lipSyncFrameId = 0;
        }

        if (UI_STATE.config && UI_STATE.config.live2d) {
            applyMouthValue(UI_STATE.config.live2d, 0);
        }

        const hasPendingSpeech = Boolean(UI_STATE.activeSpeechSession);
        DOM.stopAudioButton.disabled = !hasPendingSpeech;
        setConnectionState(hasPendingSpeech ? "busy" : "ready", hasPendingSpeech ? "语音合成中" : "已连接");
        resolveSpeechWaiter();
    }

    function resolveSpeechWaiter() {
        if (!UI_STATE.speechEndedResolver) {
            return;
        }

        const resolve = UI_STATE.speechEndedResolver;
        UI_STATE.speechEndedResolver = null;
        resolve();
    }

    function startLipSyncLoop() {
        if (!UI_STATE.audioAnalyser || !UI_STATE.volumeBuffer) {
            return;
        }

        const updateFrame = () => {
            if (!UI_STATE.audioAnalyser || !UI_STATE.volumeBuffer || !UI_STATE.speaking) {
                return;
            }

            UI_STATE.audioAnalyser.getByteTimeDomainData(UI_STATE.volumeBuffer);

            let total = 0;
            for (let index = 0; index < UI_STATE.volumeBuffer.length; index += 1) {
                const sample = (UI_STATE.volumeBuffer[index] - 128) / 128;
                total += sample * sample;
            }

            const rms = Math.sqrt(total / UI_STATE.volumeBuffer.length);
            const scaledValue = clamp((rms - 0.02) * 5.4, 0, 1);
            UI_STATE.currentMouthValue = smoothValue(UI_STATE.currentMouthValue, scaledValue, 0.38);

            const live2dConfig = UI_STATE.config && UI_STATE.config.live2d
                ? UI_STATE.config.live2d
                : null;
            applyMouthValue(live2dConfig, UI_STATE.currentMouthValue);
            UI_STATE.lipSyncFrameId = window.requestAnimationFrame(updateFrame);
        };

        if (UI_STATE.lipSyncFrameId) {
            window.cancelAnimationFrame(UI_STATE.lipSyncFrameId);
        }
        UI_STATE.lipSyncFrameId = window.requestAnimationFrame(updateFrame);
    }

    async function ensureAudioContextReady() {
        if (!window.AudioContext && !window.webkitAudioContext) {
            return;
        }

        if (!UI_STATE.audioContext) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            UI_STATE.audioContext = new AudioContextClass();
        }

        if (UI_STATE.audioContext.state === "suspended") {
            await UI_STATE.audioContext.resume();
        }
    }

    return {
        bindHooks: bindHooks,
        ensureAudioContextReady: ensureAudioContextReady,
        loadTtsOptions: loadTtsOptions,
        handleTtsProviderChange: handleTtsProviderChange,
        handleVoiceSelectionChange: handleVoiceSelectionChange,
        speakText: speakText,
        createSpeechSession: createSpeechSession,
        queueSpeechSessionText: queueSpeechSessionText,
        finalizeSpeechSession: finalizeSpeechSession,
        stopSpeechPlayback: stopSpeechPlayback,
    };
}
