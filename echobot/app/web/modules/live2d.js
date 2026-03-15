import {
    DEFAULT_LIP_SYNC_IDS,
    DOM,
    UI_STATE,
} from "./state.js";

export function createLive2DModule(deps) {
    const {
        clamp,
        roundTo,
        responseToError,
        setRunStatus,
    } = deps;
    const DEFAULT_STAGE_BACKGROUND_TRANSFORM = Object.freeze({
        positionX: 50,
        positionY: 50,
        scale: 100,
    });
    const DEFAULT_STAGE_LIGHT_POSITION = Object.freeze({
        x: 0,
        y: 0,
    });
    const DEFAULT_STAGE_RIM_LIGHT_POSITION = Object.freeze({
        x: 0.76,
        y: 0.42,
    });
    const STAGE_EFFECTS_STORAGE_KEY = "echobot.web.stage.effects.v3";
    const DEFAULT_STAGE_EFFECT_SETTINGS = Object.freeze({
        enabled: true,
        backgroundBlurEnabled: true,
        backgroundBlur: 16,
        lightEnabled: true,
        lightFloatEnabled: true,
        particlesEnabled: true,
        particleDensity: 30,
        particleOpacity: 45,
        particleSize: 150,
        particleSpeed: 80,
        lightX: 0,
        lightY: 0,
        glowStrength: 25,
        vignetteStrength: 23,
        grainStrength: 16,
        hue: 0,
        saturation: 100,
        contrast: 100,
    });
    const STAGE_PARTICLE_COUNT = 96;
    const ATMOSPHERE_FILTER_FRAGMENT = `
        precision mediump float;

        varying vec2 vTextureCoord;
        uniform sampler2D uSampler;
        uniform vec2 uLightPos;
        uniform vec3 uAmbientColor;
        uniform vec3 uHighlightColor;
        uniform float uGlowStrength;
        uniform float uGrainStrength;
        uniform float uVignetteStrength;
        uniform float uPulse;
        uniform float uTime;

        float hash(vec2 value) {
            return fract(
                sin(dot(value, vec2(127.1, 311.7)) + uTime * 1.618)
                * 43758.5453123
            );
        }

        void main(void) {
            vec2 uv = vTextureCoord;
            vec4 source = texture2D(uSampler, uv);
            vec3 color = source.rgb;

            color = mix(color, color * uAmbientColor, 0.22);

            float dist = distance(uv, uLightPos);
            float halo = smoothstep(0.64, 0.0, dist);
            halo *= halo;

            float beam = smoothstep(
                0.18,
                0.0,
                abs((uv.x - uLightPos.x) * 0.88 + (uv.y - uLightPos.y) * 1.28)
            );
            float glow = (halo * 0.92 + beam * 0.35)
                * uGlowStrength
                * (0.94 + uPulse * 0.06);

            color += uHighlightColor * glow * 0.22;

            float vignette = smoothstep(0.98, 0.34, distance(uv, vec2(0.5, 0.52)));
            color *= mix(1.0 - uVignetteStrength, 1.0, vignette);

            float grain = (hash(uv * 1400.0) - 0.5) * 0.018 * uGrainStrength;
            color += grain;

            color = clamp((color - 0.5) * 1.06 + 0.5, 0.0, 1.0);
            gl_FragColor = vec4(color, source.a);
        }
    `;

    function normalizeStageEffectsSettings(settings) {
        const input = settings || {};
        const backgroundBlur = Number.parseFloat(String(input.backgroundBlur));
        const lightX = Number.parseFloat(String(input.lightX));
        const lightY = Number.parseFloat(String(input.lightY));
        const glowStrength = Number.parseFloat(String(input.glowStrength));
        const vignetteStrength = Number.parseFloat(String(input.vignetteStrength));
        const grainStrength = Number.parseFloat(String(input.grainStrength));
        const particleDensity = Number.parseFloat(String(input.particleDensity));
        const particleOpacity = Number.parseFloat(String(input.particleOpacity));
        const particleSize = Number.parseFloat(String(input.particleSize));
        const particleSpeed = Number.parseFloat(String(input.particleSpeed));
        const hue = Number.parseFloat(String(input.hue));
        const saturation = Number.parseFloat(String(input.saturation));
        const contrast = Number.parseFloat(String(input.contrast));

        return {
            enabled: input.enabled !== false,
            backgroundBlurEnabled: input.backgroundBlurEnabled !== false,
            backgroundBlur: roundTo(
                clamp(
                    Number.isFinite(backgroundBlur)
                        ? backgroundBlur
                        : DEFAULT_STAGE_EFFECT_SETTINGS.backgroundBlur,
                    0,
                    16,
                ),
                1,
            ),
            lightEnabled: input.lightEnabled !== false,
            lightFloatEnabled: input.lightFloatEnabled !== false,
            particlesEnabled: input.particlesEnabled !== false,
            particleDensity: roundTo(
                clamp(
                    Number.isFinite(particleDensity)
                        ? particleDensity
                        : DEFAULT_STAGE_EFFECT_SETTINGS.particleDensity,
                    0,
                    100,
                ),
                0,
            ),
            particleOpacity: roundTo(
                clamp(
                    Number.isFinite(particleOpacity)
                        ? particleOpacity
                        : DEFAULT_STAGE_EFFECT_SETTINGS.particleOpacity,
                    0,
                    160,
                ),
                0,
            ),
            particleSize: roundTo(
                clamp(
                    Number.isFinite(particleSize)
                        ? particleSize
                        : DEFAULT_STAGE_EFFECT_SETTINGS.particleSize,
                    40,
                    240,
                ),
                0,
            ),
            particleSpeed: roundTo(
                clamp(
                    Number.isFinite(particleSpeed)
                        ? particleSpeed
                        : DEFAULT_STAGE_EFFECT_SETTINGS.particleSpeed,
                    0,
                    260,
                ),
                0,
            ),
            lightX: roundTo(
                clamp(
                    Number.isFinite(lightX)
                        ? lightX
                        : DEFAULT_STAGE_EFFECT_SETTINGS.lightX,
                    0,
                    100,
                ),
                0,
            ),
            lightY: roundTo(
                clamp(
                    Number.isFinite(lightY)
                        ? lightY
                        : DEFAULT_STAGE_EFFECT_SETTINGS.lightY,
                    0,
                    100,
                ),
                0,
            ),
            glowStrength: roundTo(
                clamp(
                    Number.isFinite(glowStrength)
                        ? glowStrength
                        : DEFAULT_STAGE_EFFECT_SETTINGS.glowStrength,
                    0,
                    160,
                ),
                0,
            ),
            vignetteStrength: roundTo(
                clamp(
                    Number.isFinite(vignetteStrength)
                        ? vignetteStrength
                        : DEFAULT_STAGE_EFFECT_SETTINGS.vignetteStrength,
                    0,
                    60,
                ),
                0,
            ),
            grainStrength: roundTo(
                clamp(
                    Number.isFinite(grainStrength)
                        ? grainStrength
                        : DEFAULT_STAGE_EFFECT_SETTINGS.grainStrength,
                    0,
                    40,
                ),
                0,
            ),
            hue: roundTo(
                clamp(
                    Number.isFinite(hue)
                        ? hue
                        : DEFAULT_STAGE_EFFECT_SETTINGS.hue,
                    -180,
                    180,
                ),
                0,
            ),
            saturation: roundTo(
                clamp(
                    Number.isFinite(saturation)
                        ? saturation
                        : DEFAULT_STAGE_EFFECT_SETTINGS.saturation,
                    0,
                    200,
                ),
                0,
            ),
            contrast: roundTo(
                clamp(
                    Number.isFinite(contrast)
                        ? contrast
                        : DEFAULT_STAGE_EFFECT_SETTINGS.contrast,
                    0,
                    200,
                ),
                0,
            ),
        };
    }

    function loadSavedStageEffectsSettings() {
        try {
            const raw = window.localStorage.getItem(STAGE_EFFECTS_STORAGE_KEY);
            if (!raw) {
                return {
                    ...DEFAULT_STAGE_EFFECT_SETTINGS,
                };
            }
            return normalizeStageEffectsSettings(JSON.parse(raw));
        } catch (error) {
            console.warn("Failed to read saved stage effects settings", error);
            return {
                ...DEFAULT_STAGE_EFFECT_SETTINGS,
            };
        }
    }

    function persistStageEffectsSettings(settings) {
        window.localStorage.setItem(
            STAGE_EFFECTS_STORAGE_KEY,
            JSON.stringify(normalizeStageEffectsSettings(settings)),
        );
    }

    function applyConfigToUI(config) {
        const rememberedSessionName = String(
            window.localStorage.getItem("echobot.web.session") || config.session_name,
        ).trim() || config.session_name;
        const live2dModelOptions = resolveLive2DModelOptions(config.live2d);
        const currentLive2DConfig = resolveInitialLive2DConfig(config.live2d, live2dModelOptions);
        const stageConfig = normalizeStageConfig(config.stage);
        const stageBackgroundKey = resolveInitialStageBackgroundKey(stageConfig);
        UI_STATE.currentSessionName = rememberedSessionName;
        UI_STATE.currentRoleName = config.role_name || "default";
        UI_STATE.currentRouteMode = config.route_mode || "auto";
        UI_STATE.ttsEnabled = DOM.autoTtsCheckbox.checked;
        UI_STATE.live2dMouseFollowEnabled = loadSavedLive2DMouseFollowEnabled();
        UI_STATE.config.live2d = currentLive2DConfig;
        UI_STATE.config.stage = stageConfig;
        UI_STATE.selectedStageBackgroundKey = stageBackgroundKey;
        UI_STATE.stageEffects = loadSavedStageEffectsSettings();

        if (DOM.live2dMouseFollowCheckbox) {
            DOM.live2dMouseFollowCheckbox.checked = UI_STATE.live2dMouseFollowEnabled;
        }

        if (DOM.routeModeSelect) {
            DOM.routeModeSelect.value = UI_STATE.currentRouteMode;
        }

        DOM.sessionLabel.textContent = `会话: ${rememberedSessionName}`;
        renderLive2DModelOptions(live2dModelOptions, currentLive2DConfig.selection_key);
        renderStageBackgroundOptions(stageConfig, stageBackgroundKey);
        applyStageBackgroundByKey(stageConfig, stageBackgroundKey);
        applyStageEffectsSettings(UI_STATE.stageEffects, { persist: false });

        if (!currentLive2DConfig.available) {
            setStageMessage("未找到 Live2D 模型。请检查 .echobot/live2d 目录。");
        } else {
            setStageMessage("");
        }
        return currentLive2DConfig;
    }

    function resolveLive2DModelOptions(live2dConfig) {
        const modelOptions = Array.isArray(live2dConfig && live2dConfig.models)
            ? live2dConfig.models
            : [];
        const normalizedOptions = modelOptions
            .map(normalizeLive2DModelOption)
            .filter((item) => item.model_url);

        if (normalizedOptions.length > 0) {
            return normalizedOptions;
        }

        const fallbackOption = normalizeLive2DModelOption(live2dConfig);
        return fallbackOption.model_url ? [fallbackOption] : [];
    }

    function normalizeLive2DModelOption(modelOption) {
        const lipSyncParameterIds = Array.isArray(modelOption && modelOption.lip_sync_parameter_ids)
            ? modelOption.lip_sync_parameter_ids.filter((item) => typeof item === "string")
            : [];
        return {
            source: String((modelOption && modelOption.source) || ""),
            selection_key: String(
                (modelOption && modelOption.selection_key)
                || (modelOption && modelOption.model_url)
                || "",
            ),
            model_name: String((modelOption && modelOption.model_name) || ""),
            model_url: String((modelOption && modelOption.model_url) || ""),
            directory_name: String((modelOption && modelOption.directory_name) || ""),
            lip_sync_parameter_ids: lipSyncParameterIds,
            mouth_form_parameter_id: typeof (modelOption && modelOption.mouth_form_parameter_id) === "string"
                ? modelOption.mouth_form_parameter_id
                : null,
        };
    }

    function resolveInitialLive2DConfig(live2dConfig, modelOptions) {
        const selectedOption = findLive2DModelOption(modelOptions, loadSavedLive2DSelectionKey())
            || findLive2DModelOption(modelOptions, live2dConfig && live2dConfig.selection_key)
            || modelOptions[0]
            || null;
        return buildCurrentLive2DConfig(selectedOption, modelOptions);
    }

    function buildCurrentLive2DConfig(selectedOption, modelOptions) {
        if (!selectedOption) {
            return {
                available: false,
                source: "",
                selection_key: "",
                model_name: "",
                model_url: "",
                directory_name: "",
                lip_sync_parameter_ids: DEFAULT_LIP_SYNC_IDS.slice(),
                mouth_form_parameter_id: null,
                models: [],
            };
        }

        const normalizedOption = normalizeLive2DModelOption(selectedOption);
        const normalizedOptions = modelOptions.map(normalizeLive2DModelOption);
        persistLive2DSelectionKey(normalizedOption.selection_key);
        return {
            available: true,
            source: normalizedOption.source,
            selection_key: normalizedOption.selection_key,
            model_name: normalizedOption.model_name,
            model_url: normalizedOption.model_url,
            directory_name: normalizedOption.directory_name,
            lip_sync_parameter_ids: normalizedOption.lip_sync_parameter_ids,
            mouth_form_parameter_id: normalizedOption.mouth_form_parameter_id,
            models: normalizedOptions,
        };
    }

    function renderLive2DModelOptions(modelOptions, selectedKey) {
        if (!DOM.modelSelect) {
            return;
        }

        DOM.modelSelect.innerHTML = "";

        if (!modelOptions || modelOptions.length === 0) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "未找到 Live2D 模型";
            DOM.modelSelect.appendChild(option);
            updateLive2DUploadControls();
            return;
        }

        modelOptions.forEach((modelOption) => {
            const option = document.createElement("option");
            option.value = modelOption.selection_key;
            option.textContent = buildLive2DModelLabel(modelOption);
            DOM.modelSelect.appendChild(option);
        });

        DOM.modelSelect.value = selectedKey || modelOptions[0].selection_key;
        updateLive2DUploadControls();
    }

    function buildLive2DModelLabel(modelOption) {
        const sourceLabel = modelOption.source === "builtin" ? "内置" : "工作区";
        const baseName = modelOption.directory_name && modelOption.directory_name !== modelOption.model_name
            ? `${modelOption.directory_name} / ${modelOption.model_name}`
            : (modelOption.model_name || modelOption.directory_name || modelOption.selection_key);
        return `${baseName} (${sourceLabel})`;
    }

    function updateLive2DUploadControls(options = {}) {
        const isUploading = Boolean(options.isUploading);
        const modelOptions = resolveLive2DModelOptions(UI_STATE.config && UI_STATE.config.live2d);

        if (DOM.modelSelect) {
            if (isUploading || modelOptions.length === 0) {
                DOM.modelSelect.disabled = true;
            } else {
                DOM.modelSelect.disabled = modelOptions.length <= 1;
            }
        }
        if (DOM.live2dUploadButton) {
            DOM.live2dUploadButton.disabled = isUploading;
        }
        if (DOM.live2dUploadInput) {
            DOM.live2dUploadInput.disabled = isUploading;
        }
    }

    function normalizeStageConfig(stageConfig) {
        const backgrounds = Array.isArray(stageConfig && stageConfig.backgrounds)
            ? stageConfig.backgrounds
                .map((item) => ({
                    key: String((item && item.key) || "").trim(),
                    label: String((item && item.label) || "").trim(),
                    url: String((item && item.url) || "").trim(),
                    kind: String((item && item.kind) || "uploaded").trim() || "uploaded",
                }))
                .filter((item) => item.key)
            : [];

        const defaultBackgroundKey = String(
            (stageConfig && stageConfig.default_background_key) || "default",
        ).trim() || "default";

        if (!backgrounds.some((item) => item.key === defaultBackgroundKey)) {
            backgrounds.unshift({
                key: defaultBackgroundKey,
                label: "不使用背景",
                url: "",
                kind: "none",
            });
        }

        return {
            default_background_key: defaultBackgroundKey,
            backgrounds: backgrounds,
        };
    }

    function loadSavedStageBackgroundKey() {
        return String(window.localStorage.getItem("echobot.web.stage.background") || "").trim();
    }

    function persistStageBackgroundKey(backgroundKey) {
        window.localStorage.setItem(
            "echobot.web.stage.background",
            String(backgroundKey || "default"),
        );
    }

    function normalizeStageBackgroundTransform(transform) {
        const positionX = Number.parseFloat(String(transform && transform.positionX));
        const positionY = Number.parseFloat(String(transform && transform.positionY));
        const scale = Number.parseFloat(String(transform && transform.scale));

        return {
            positionX: roundTo(
                clamp(
                    Number.isFinite(positionX)
                        ? positionX
                        : DEFAULT_STAGE_BACKGROUND_TRANSFORM.positionX,
                    0,
                    100,
                ),
                0,
            ),
            positionY: roundTo(
                clamp(
                    Number.isFinite(positionY)
                        ? positionY
                        : DEFAULT_STAGE_BACKGROUND_TRANSFORM.positionY,
                    0,
                    100,
                ),
                0,
            ),
            scale: roundTo(
                clamp(
                    Number.isFinite(scale)
                        ? scale
                        : DEFAULT_STAGE_BACKGROUND_TRANSFORM.scale,
                    60,
                    200,
                ),
                0,
            ),
        };
    }

    function stageBackgroundTransformStorageKey(backgroundKey) {
        return `echobot.web.stage.background.transform.${String(backgroundKey || "default").trim() || "default"}`;
    }

    function loadSavedStageBackgroundTransform(backgroundKey) {
        try {
            const raw = window.localStorage.getItem(
                stageBackgroundTransformStorageKey(backgroundKey),
            );
            if (!raw) {
                return null;
            }
            return normalizeStageBackgroundTransform(JSON.parse(raw));
        } catch (error) {
            console.warn("Failed to read saved stage background transform", error);
            return null;
        }
    }

    function persistStageBackgroundTransform(backgroundKey, transform) {
        const normalizedTransform = normalizeStageBackgroundTransform(transform);
        window.localStorage.setItem(
            stageBackgroundTransformStorageKey(backgroundKey),
            JSON.stringify(normalizedTransform),
        );
    }

    function clearSavedStageBackgroundTransform(backgroundKey) {
        window.localStorage.removeItem(stageBackgroundTransformStorageKey(backgroundKey));
    }

    function resolveInitialStageBackgroundKey(stageConfig) {
        const savedKey = loadSavedStageBackgroundKey();
        if (findStageBackgroundOption(stageConfig, savedKey)) {
            return savedKey;
        }
        return stageConfig.default_background_key || "default";
    }

    function findStageBackgroundOption(stageConfig, backgroundKey) {
        const normalizedKey = String(backgroundKey || "").trim();
        if (!normalizedKey || !stageConfig || !Array.isArray(stageConfig.backgrounds)) {
            return null;
        }
        return stageConfig.backgrounds.find((item) => item.key === normalizedKey) || null;
    }

    function currentStageBackgroundOption() {
        if (!UI_STATE.config || !UI_STATE.config.stage) {
            return null;
        }
        return findStageBackgroundOption(
            UI_STATE.config.stage,
            UI_STATE.selectedStageBackgroundKey,
        );
    }

    function resolveStageBackgroundTransform(backgroundOption) {
        if (!backgroundOption || !backgroundOption.url) {
            return {
                ...DEFAULT_STAGE_BACKGROUND_TRANSFORM,
            };
        }
        return loadSavedStageBackgroundTransform(backgroundOption.key) || {
            ...DEFAULT_STAGE_BACKGROUND_TRANSFORM,
        };
    }

    function renderStageBackgroundOptions(stageConfig, selectedKey) {
        if (!DOM.stageBackgroundSelect) {
            return;
        }

        const backgrounds = Array.isArray(stageConfig && stageConfig.backgrounds)
            ? stageConfig.backgrounds
            : [];
        DOM.stageBackgroundSelect.innerHTML = "";

        backgrounds.forEach((background) => {
            const option = document.createElement("option");
            option.value = background.key;
            option.textContent = background.label || background.key;
            DOM.stageBackgroundSelect.appendChild(option);
        });

        if (backgrounds.length === 0) {
            const option = document.createElement("option");
            option.value = "default";
            option.textContent = "不使用背景";
            DOM.stageBackgroundSelect.appendChild(option);
        }

        DOM.stageBackgroundSelect.value = selectedKey || stageConfig.default_background_key || "default";
    }

    function applyStageBackgroundByKey(stageConfig, backgroundKey) {
        const selectedOption = findStageBackgroundOption(stageConfig, backgroundKey)
            || findStageBackgroundOption(stageConfig, stageConfig.default_background_key)
            || null;
        const nextKey = selectedOption ? selectedOption.key : (stageConfig.default_background_key || "default");
        const nextTransform = resolveStageBackgroundTransform(selectedOption);

        UI_STATE.selectedStageBackgroundKey = nextKey;
        UI_STATE.currentStageBackgroundTransform = nextTransform;
        persistStageBackgroundKey(nextKey);
        renderStageBackgroundOptions(stageConfig, nextKey);
        applyStageBackgroundOption(selectedOption, nextTransform);
        syncStageBackgroundTransformInputs(selectedOption, nextTransform);
        updateStageBackgroundDetail(selectedOption, nextTransform);
        updateStageBackgroundControls();
    }

    function calculateStageBackgroundMetrics(normalizedTransform) {
        if (!DOM.stageElement) {
            return null;
        }

        const containerW = DOM.stageElement.offsetWidth;
        const containerH = DOM.stageElement.offsetHeight;
        if (containerW <= 0 || containerH <= 0) {
            return null;
        }

        const naturalSize = UI_STATE.currentBackgroundImageNaturalSize;
        if (!naturalSize || naturalSize.w <= 0 || naturalSize.h <= 0) {
            return {
                containerW: containerW,
                containerH: containerH,
                bgW: containerW,
                bgH: containerH,
                offsetX: 0,
                offsetY: 0,
            };
        }

        const coverFactor = Math.max(containerW / naturalSize.w, containerH / naturalSize.h);
        const scaleFactor = normalizedTransform.scale / 100;
        const bgW = Math.round(naturalSize.w * coverFactor * scaleFactor);
        const bgH = Math.round(naturalSize.h * coverFactor * scaleFactor);

        return {
            containerW: containerW,
            containerH: containerH,
            bgW: bgW,
            bgH: bgH,
            offsetX: Math.round((containerW - bgW) * (normalizedTransform.positionX / 100)),
            offsetY: Math.round((containerH - bgH) * (normalizedTransform.positionY / 100)),
        };
    }

    function applyDomStageBackgroundTransform(normalizedTransform) {
        if (!DOM.stageElement) {
            return;
        }

        const metrics = calculateStageBackgroundMetrics(normalizedTransform);
        if (metrics) {
            DOM.stageElement.style.setProperty(
                "--stage-background-size",
                `${metrics.bgW}px ${metrics.bgH}px`,
            );
        } else {
            DOM.stageElement.style.removeProperty("--stage-background-size");
        }

        DOM.stageElement.style.setProperty(
            "--stage-background-position-x",
            `${normalizedTransform.positionX}%`,
        );
        DOM.stageElement.style.setProperty(
            "--stage-background-position-y",
            `${normalizedTransform.positionY}%`,
        );
    }

    function updateStageBackgroundSpriteTransform(normalizedTransform) {
        if (!UI_STATE.stageBackgroundSprite) {
            return;
        }

        const metrics = calculateStageBackgroundMetrics(normalizedTransform);
        if (!metrics) {
            return;
        }

        UI_STATE.stageBackgroundSprite.position.set(metrics.offsetX, metrics.offsetY);
        UI_STATE.stageBackgroundSprite.width = metrics.bgW;
        UI_STATE.stageBackgroundSprite.height = metrics.bgH;
    }

    function applyStageBackgroundTransform(transform) {
        const normalizedTransform = normalizeStageBackgroundTransform(transform);
        applyDomStageBackgroundTransform(normalizedTransform);
        updateStageBackgroundSpriteTransform(normalizedTransform);
    }

    function clearStageBackgroundTransformStyles() {
        if (!DOM.stageElement) {
            return;
        }

        DOM.stageElement.style.removeProperty("--stage-background-position-x");
        DOM.stageElement.style.removeProperty("--stage-background-position-y");
        DOM.stageElement.style.removeProperty("--stage-background-size");
    }

    function applyDomStageBackgroundOption(backgroundOption, transform) {
        if (!DOM.stageElement || !DOM.stageBackgroundImage) {
            return;
        }

        const url = backgroundOption ? String(backgroundOption.url || "").trim() : "";
        if (!url) {
            DOM.stageBackgroundImage.hidden = true;
            DOM.stageBackgroundImage.style.backgroundImage = "";
            clearStageBackgroundTransformStyles();
            DOM.stageElement.classList.remove("has-custom-background");
            return;
        }

        const safeUrl = url.replace(/"/g, "%22");
        DOM.stageBackgroundImage.style.backgroundImage = `url("${safeUrl}")`;
        DOM.stageBackgroundImage.hidden = false;
        applyDomStageBackgroundTransform(normalizeStageBackgroundTransform(transform));
        DOM.stageElement.classList.add("has-custom-background");

        const img = new Image();
        img.onload = () => {
            if (DOM.stageBackgroundImage.style.backgroundImage !== `url("${safeUrl}")`) {
                return;
            }
            UI_STATE.currentBackgroundImageNaturalSize = { w: img.naturalWidth, h: img.naturalHeight };
            applyStageBackgroundTransform(UI_STATE.currentStageBackgroundTransform || transform);
        };
        img.src = safeUrl;
    }

    function applyStageBackgroundOption(backgroundOption, transform) {
        applyDomStageBackgroundOption(backgroundOption, transform);
        void syncPixiStageBackground(backgroundOption, transform);
    }

    function updateStageEffectsValueLabels(settings) {
        if (DOM.stageEffectsBackgroundBlurValue) {
            DOM.stageEffectsBackgroundBlurValue.textContent = String(settings.backgroundBlur);
        }
        if (DOM.stageEffectsLightXValue) {
            DOM.stageEffectsLightXValue.textContent = `${settings.lightX}%`;
        }
        if (DOM.stageEffectsLightYValue) {
            DOM.stageEffectsLightYValue.textContent = `${settings.lightY}%`;
        }
        if (DOM.stageEffectsGlowValue) {
            DOM.stageEffectsGlowValue.textContent = `${settings.glowStrength}%`;
        }
        if (DOM.stageEffectsVignetteValue) {
            DOM.stageEffectsVignetteValue.textContent = `${settings.vignetteStrength}%`;
        }
        if (DOM.stageEffectsGrainValue) {
            DOM.stageEffectsGrainValue.textContent = `${settings.grainStrength}%`;
        }
        if (DOM.stageEffectsParticleDensityValue) {
            DOM.stageEffectsParticleDensityValue.textContent = `${settings.particleDensity}%`;
        }
        if (DOM.stageEffectsParticleOpacityValue) {
            DOM.stageEffectsParticleOpacityValue.textContent = `${settings.particleOpacity}%`;
        }
        if (DOM.stageEffectsParticleSizeValue) {
            DOM.stageEffectsParticleSizeValue.textContent = `${settings.particleSize}%`;
        }
        if (DOM.stageEffectsParticleSpeedValue) {
            DOM.stageEffectsParticleSpeedValue.textContent = `${settings.particleSpeed}%`;
        }
        if (DOM.stageEffectsHueValue) {
            DOM.stageEffectsHueValue.textContent = `${settings.hue}\u00B0`;
        }
        if (DOM.stageEffectsSaturationValue) {
            DOM.stageEffectsSaturationValue.textContent = `${settings.saturation}%`;
        }
        if (DOM.stageEffectsContrastValue) {
            DOM.stageEffectsContrastValue.textContent = `${settings.contrast}%`;
        }
    }

    function syncStageEffectsInputs(settings) {
        if (DOM.stageEffectsEnabledCheckbox) {
            DOM.stageEffectsEnabledCheckbox.checked = settings.enabled;
        }
        if (DOM.stageEffectsBackgroundBlurCheckbox) {
            DOM.stageEffectsBackgroundBlurCheckbox.checked = settings.backgroundBlurEnabled;
        }
        if (DOM.stageEffectsLightEnabledCheckbox) {
            DOM.stageEffectsLightEnabledCheckbox.checked = settings.lightEnabled;
        }
        if (DOM.stageEffectsLightFloatCheckbox) {
            DOM.stageEffectsLightFloatCheckbox.checked = settings.lightFloatEnabled;
        }
        if (DOM.stageEffectsParticlesEnabledCheckbox) {
            DOM.stageEffectsParticlesEnabledCheckbox.checked = settings.particlesEnabled;
        }
        if (DOM.stageEffectsBackgroundBlurInput) {
            DOM.stageEffectsBackgroundBlurInput.value = String(settings.backgroundBlur);
        }
        if (DOM.stageEffectsLightXInput) {
            DOM.stageEffectsLightXInput.value = String(settings.lightX);
        }
        if (DOM.stageEffectsLightYInput) {
            DOM.stageEffectsLightYInput.value = String(settings.lightY);
        }
        if (DOM.stageEffectsGlowInput) {
            DOM.stageEffectsGlowInput.value = String(settings.glowStrength);
        }
        if (DOM.stageEffectsVignetteInput) {
            DOM.stageEffectsVignetteInput.value = String(settings.vignetteStrength);
        }
        if (DOM.stageEffectsGrainInput) {
            DOM.stageEffectsGrainInput.value = String(settings.grainStrength);
        }
        if (DOM.stageEffectsParticleDensityInput) {
            DOM.stageEffectsParticleDensityInput.value = String(settings.particleDensity);
        }
        if (DOM.stageEffectsParticleOpacityInput) {
            DOM.stageEffectsParticleOpacityInput.value = String(settings.particleOpacity);
        }
        if (DOM.stageEffectsParticleSizeInput) {
            DOM.stageEffectsParticleSizeInput.value = String(settings.particleSize);
        }
        if (DOM.stageEffectsParticleSpeedInput) {
            DOM.stageEffectsParticleSpeedInput.value = String(settings.particleSpeed);
        }
        if (DOM.stageEffectsHueInput) {
            DOM.stageEffectsHueInput.value = String(settings.hue);
        }
        if (DOM.stageEffectsSaturationInput) {
            DOM.stageEffectsSaturationInput.value = String(settings.saturation);
        }
        if (DOM.stageEffectsContrastInput) {
            DOM.stageEffectsContrastInput.value = String(settings.contrast);
        }

        updateStageEffectsValueLabels(settings);
    }

    function updateStageEffectsControls(settings) {
        const controlsLocked = !settings.enabled;
        const lightControlsLocked = controlsLocked || !settings.lightEnabled;
        const blurControlsLocked = controlsLocked || !settings.backgroundBlurEnabled;
        const particleControlsLocked = controlsLocked || !settings.particlesEnabled;

        if (DOM.stageEffectsBackgroundBlurCheckbox) {
            DOM.stageEffectsBackgroundBlurCheckbox.disabled = controlsLocked;
        }
        if (DOM.stageEffectsBackgroundBlurInput) {
            DOM.stageEffectsBackgroundBlurInput.disabled = blurControlsLocked;
        }
        if (DOM.stageEffectsLightEnabledCheckbox) {
            DOM.stageEffectsLightEnabledCheckbox.disabled = controlsLocked;
        }
        if (DOM.stageEffectsLightFloatCheckbox) {
            DOM.stageEffectsLightFloatCheckbox.disabled = lightControlsLocked;
        }
        if (DOM.stageEffectsParticlesEnabledCheckbox) {
            DOM.stageEffectsParticlesEnabledCheckbox.disabled = controlsLocked;
        }
        if (DOM.stageEffectsLightXInput) {
            DOM.stageEffectsLightXInput.disabled = lightControlsLocked;
        }
        if (DOM.stageEffectsLightYInput) {
            DOM.stageEffectsLightYInput.disabled = lightControlsLocked;
        }
        if (DOM.stageEffectsGlowInput) {
            DOM.stageEffectsGlowInput.disabled = lightControlsLocked;
        }
        if (DOM.stageEffectsVignetteInput) {
            DOM.stageEffectsVignetteInput.disabled = controlsLocked;
        }
        if (DOM.stageEffectsGrainInput) {
            DOM.stageEffectsGrainInput.disabled = controlsLocked;
        }
        if (DOM.stageEffectsParticleDensityInput) {
            DOM.stageEffectsParticleDensityInput.disabled = particleControlsLocked;
        }
        if (DOM.stageEffectsParticleOpacityInput) {
            DOM.stageEffectsParticleOpacityInput.disabled = particleControlsLocked;
        }
        if (DOM.stageEffectsParticleSizeInput) {
            DOM.stageEffectsParticleSizeInput.disabled = particleControlsLocked;
        }
        if (DOM.stageEffectsParticleSpeedInput) {
            DOM.stageEffectsParticleSpeedInput.disabled = particleControlsLocked;
        }
        if (DOM.stageEffectsHueInput) {
            DOM.stageEffectsHueInput.disabled = controlsLocked;
        }
        if (DOM.stageEffectsSaturationInput) {
            DOM.stageEffectsSaturationInput.disabled = controlsLocked;
        }
        if (DOM.stageEffectsContrastInput) {
            DOM.stageEffectsContrastInput.disabled = controlsLocked;
        }
    }

    function buildStageColorAdjustmentCss(settings) {
        const hasColorAdjustment = (
            settings.hue !== DEFAULT_STAGE_EFFECT_SETTINGS.hue
            || settings.saturation !== DEFAULT_STAGE_EFFECT_SETTINGS.saturation
            || settings.contrast !== DEFAULT_STAGE_EFFECT_SETTINGS.contrast
        );

        if (!settings.enabled || !hasColorAdjustment) {
            return "";
        }

        return [
            `hue-rotate(${settings.hue}deg)`,
            `saturate(${settings.saturation}%)`,
            `contrast(${settings.contrast}%)`,
        ].join(" ");
    }

    function applyStageEffectsToRuntime(settings) {
        const effectsEnabled = settings.enabled;
        const lightEnabled = effectsEnabled && settings.lightEnabled;
        const particlesEnabled = effectsEnabled && settings.particlesEnabled;
        const baseLightX = settings.lightX / 100;
        const baseLightY = settings.lightY / 100;

        if (UI_STATE.stageBackgroundBlurFilter) {
            UI_STATE.stageBackgroundBlurFilter.blur = (
                effectsEnabled && settings.backgroundBlurEnabled
            )
                ? settings.backgroundBlur
                : 0;
        }

        if (UI_STATE.stagePostFilter) {
            UI_STATE.stagePostFilter.enabled = effectsEnabled;
            UI_STATE.stagePostFilter.uniforms.uGlowStrength = lightEnabled
                ? settings.glowStrength / 100
                : 0;
            UI_STATE.stagePostFilter.uniforms.uGrainStrength = effectsEnabled
                ? settings.grainStrength / 16
                : 0;
            UI_STATE.stagePostFilter.uniforms.uVignetteStrength = effectsEnabled
                ? settings.vignetteStrength / 100
                : 0;
            UI_STATE.stagePostFilter.uniforms.uLightPos = [baseLightX, baseLightY];
        }

        if (DOM.stageLightBack) {
            DOM.stageLightBack.style.opacity = lightEnabled
                ? String(clamp(0.24 + settings.glowStrength / 145, 0, 0.98))
                : "0";
        }
        if (DOM.stageLightRim) {
            DOM.stageLightRim.style.opacity = lightEnabled
                ? String(clamp(0.14 + settings.glowStrength / 240, 0, 0.82))
                : "0";
        }
        if (DOM.stageVignette) {
            DOM.stageVignette.style.opacity = effectsEnabled
                ? String(clamp(settings.vignetteStrength / 24, 0, 1))
                : "0";
        }
        if (DOM.stageGrain) {
            DOM.stageGrain.style.opacity = effectsEnabled
                ? String(clamp(settings.grainStrength / 100, 0, 0.4))
                : "0";
        }
        if (DOM.stageGradient) {
            DOM.stageGradient.style.opacity = effectsEnabled ? "1" : "0.35";
        }
        if (UI_STATE.live2dParticleLayer) {
            UI_STATE.live2dParticleLayer.visible = particlesEnabled;
        }
        if (DOM.stageElement) {
            const colorAdjustment = buildStageColorAdjustmentCss(settings);
            if (colorAdjustment) {
                DOM.stageElement.style.setProperty("--stage-color-adjustment", colorAdjustment);
                DOM.stageElement.classList.add("has-stage-color-adjustment");
            } else {
                DOM.stageElement.style.removeProperty("--stage-color-adjustment");
                DOM.stageElement.classList.remove("has-stage-color-adjustment");
            }
        }

        UI_STATE.stageLightCurrentX = baseLightX;
        UI_STATE.stageLightCurrentY = baseLightY;
        applyStageLightingVars(baseLightX, baseLightY, lightEnabled ? 1 : 0.9);

        if (UI_STATE.pixiApp) {
            updateStageAtmosphereFrame();
        }
    }

    function applyStageEffectsSettings(nextSettings, options = {}) {
        const settings = normalizeStageEffectsSettings(nextSettings);
        UI_STATE.stageEffects = settings;

        if (options.persist !== false) {
            persistStageEffectsSettings(settings);
        }

        syncStageEffectsInputs(settings);
        renderStageEffectsDetail(settings);
        updateStageEffectsControls(settings);
        applyStageEffectsToRuntime(settings);
    }

    function readStageEffectsSettingsFromInputs() {
        return normalizeStageEffectsSettings({
            enabled: DOM.stageEffectsEnabledCheckbox
                ? DOM.stageEffectsEnabledCheckbox.checked
                : DEFAULT_STAGE_EFFECT_SETTINGS.enabled,
            backgroundBlurEnabled: DOM.stageEffectsBackgroundBlurCheckbox
                ? DOM.stageEffectsBackgroundBlurCheckbox.checked
                : DEFAULT_STAGE_EFFECT_SETTINGS.backgroundBlurEnabled,
            backgroundBlur: DOM.stageEffectsBackgroundBlurInput
                ? DOM.stageEffectsBackgroundBlurInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.backgroundBlur,
            lightEnabled: DOM.stageEffectsLightEnabledCheckbox
                ? DOM.stageEffectsLightEnabledCheckbox.checked
                : DEFAULT_STAGE_EFFECT_SETTINGS.lightEnabled,
            lightFloatEnabled: DOM.stageEffectsLightFloatCheckbox
                ? DOM.stageEffectsLightFloatCheckbox.checked
                : DEFAULT_STAGE_EFFECT_SETTINGS.lightFloatEnabled,
            particlesEnabled: DOM.stageEffectsParticlesEnabledCheckbox
                ? DOM.stageEffectsParticlesEnabledCheckbox.checked
                : DEFAULT_STAGE_EFFECT_SETTINGS.particlesEnabled,
            lightX: DOM.stageEffectsLightXInput
                ? DOM.stageEffectsLightXInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.lightX,
            lightY: DOM.stageEffectsLightYInput
                ? DOM.stageEffectsLightYInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.lightY,
            glowStrength: DOM.stageEffectsGlowInput
                ? DOM.stageEffectsGlowInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.glowStrength,
            vignetteStrength: DOM.stageEffectsVignetteInput
                ? DOM.stageEffectsVignetteInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.vignetteStrength,
            grainStrength: DOM.stageEffectsGrainInput
                ? DOM.stageEffectsGrainInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.grainStrength,
            particleDensity: DOM.stageEffectsParticleDensityInput
                ? DOM.stageEffectsParticleDensityInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.particleDensity,
            particleOpacity: DOM.stageEffectsParticleOpacityInput
                ? DOM.stageEffectsParticleOpacityInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.particleOpacity,
            particleSize: DOM.stageEffectsParticleSizeInput
                ? DOM.stageEffectsParticleSizeInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.particleSize,
            particleSpeed: DOM.stageEffectsParticleSpeedInput
                ? DOM.stageEffectsParticleSpeedInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.particleSpeed,
            hue: DOM.stageEffectsHueInput
                ? DOM.stageEffectsHueInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.hue,
            saturation: DOM.stageEffectsSaturationInput
                ? DOM.stageEffectsSaturationInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.saturation,
            contrast: DOM.stageEffectsContrastInput
                ? DOM.stageEffectsContrastInput.value
                : DEFAULT_STAGE_EFFECT_SETTINGS.contrast,
        });
    }

    function handleStageEffectsInput() {
        applyStageEffectsSettings(readStageEffectsSettingsFromInputs());
    }

    function handleStageEffectsReset() {
        applyStageEffectsSettings(DEFAULT_STAGE_EFFECT_SETTINGS);
        setRunStatus("已重置光影参数");
    }

    function renderStageEffectsDetail(settings) {
        if (!DOM.stageEffectsDetail) {
            return;
        }

        if (!settings.enabled) {
            DOM.stageEffectsDetail.textContent = "当前已关闭全部光影效果";
            return;
        }

        const blurText = settings.backgroundBlurEnabled
            ? `模糊 ${settings.backgroundBlur}`
            : "模糊关闭";
        const lightText = settings.lightEnabled
            ? `光位 ${settings.lightX}% / ${settings.lightY}%`
            : "光位关闭";
        const floatText = settings.lightEnabled && settings.lightFloatEnabled
            ? "光位漂移开启"
            : "光位漂移关闭";
        const particleText = settings.particlesEnabled
            ? `粒子 ${settings.particleDensity}% / 透明 ${settings.particleOpacity}% / 尺寸 ${settings.particleSize}% / 速度 ${settings.particleSpeed}%`
            : "粒子关闭";
        const colorText = `色调 ${settings.hue}\u00B0 / 饱和 ${settings.saturation}% / 对比 ${settings.contrast}%`;
        DOM.stageEffectsDetail.textContent = `${blurText} · ${lightText} · ${floatText} · ${particleText} · 光晕 ${settings.glowStrength}% · 暗角 ${settings.vignetteStrength}% · 颗粒 ${settings.grainStrength}% · ${colorText}`;
    }

    function updateStageBackgroundTransformValueLabels(transform) {
        const normalizedTransform = normalizeStageBackgroundTransform(transform);

        if (DOM.stageBackgroundPositionXValue) {
            DOM.stageBackgroundPositionXValue.textContent = `${normalizedTransform.positionX}%`;
        }
        if (DOM.stageBackgroundPositionYValue) {
            DOM.stageBackgroundPositionYValue.textContent = `${normalizedTransform.positionY}%`;
        }
        if (DOM.stageBackgroundScaleValue) {
            DOM.stageBackgroundScaleValue.textContent = `${normalizedTransform.scale}%`;
        }
    }

    function syncStageBackgroundTransformInputs(backgroundOption, transform) {
        const normalizedTransform = normalizeStageBackgroundTransform(transform);
        UI_STATE.currentStageBackgroundTransform = normalizedTransform;

        if (DOM.stageBackgroundPositionXInput) {
            DOM.stageBackgroundPositionXInput.value = String(normalizedTransform.positionX);
        }
        if (DOM.stageBackgroundPositionYInput) {
            DOM.stageBackgroundPositionYInput.value = String(normalizedTransform.positionY);
        }
        if (DOM.stageBackgroundScaleInput) {
            DOM.stageBackgroundScaleInput.value = String(normalizedTransform.scale);
        }

        if (!backgroundOption || !backgroundOption.url) {
            updateStageBackgroundTransformValueLabels(DEFAULT_STAGE_BACKGROUND_TRANSFORM);
            return;
        }

        updateStageBackgroundTransformValueLabels(normalizedTransform);
    }

    function readStageBackgroundTransformFromInputs() {
        return normalizeStageBackgroundTransform({
            positionX: DOM.stageBackgroundPositionXInput
                ? DOM.stageBackgroundPositionXInput.value
                : DEFAULT_STAGE_BACKGROUND_TRANSFORM.positionX,
            positionY: DOM.stageBackgroundPositionYInput
                ? DOM.stageBackgroundPositionYInput.value
                : DEFAULT_STAGE_BACKGROUND_TRANSFORM.positionY,
            scale: DOM.stageBackgroundScaleInput
                ? DOM.stageBackgroundScaleInput.value
                : DEFAULT_STAGE_BACKGROUND_TRANSFORM.scale,
        });
    }

    function updateStageBackgroundDetail(backgroundOption, transform) {
        if (!DOM.stageBackgroundDetail) {
            return;
        }

        if (!backgroundOption || !backgroundOption.url) {
            DOM.stageBackgroundDetail.textContent = "当前未使用背景";
            return;
        }

        const normalizedTransform = normalizeStageBackgroundTransform(transform);
        DOM.stageBackgroundDetail.textContent = `当前背景：${backgroundOption.label || backgroundOption.key} · 位置 ${normalizedTransform.positionX}% / ${normalizedTransform.positionY}% · 缩放 ${normalizedTransform.scale}%`;
    }

    function updateStageBackgroundControls(options = {}) {
        const isUploading = Boolean(options.isUploading);
        const selectedOption = currentStageBackgroundOption();
        const hasCustomBackground = Boolean(selectedOption && selectedOption.url);

        if (DOM.stageBackgroundSelect) {
            DOM.stageBackgroundSelect.disabled = isUploading;
        }
        if (DOM.stageBackgroundUploadButton) {
            DOM.stageBackgroundUploadButton.disabled = isUploading;
        }
        if (DOM.stageBackgroundResetButton) {
            DOM.stageBackgroundResetButton.disabled = isUploading
                || UI_STATE.selectedStageBackgroundKey === (
                    UI_STATE.config
                    && UI_STATE.config.stage
                    && UI_STATE.config.stage.default_background_key
                );
        }
        if (DOM.stageBackgroundPositionXInput) {
            DOM.stageBackgroundPositionXInput.disabled = isUploading || !hasCustomBackground;
        }
        if (DOM.stageBackgroundPositionYInput) {
            DOM.stageBackgroundPositionYInput.disabled = isUploading || !hasCustomBackground;
        }
        if (DOM.stageBackgroundScaleInput) {
            DOM.stageBackgroundScaleInput.disabled = isUploading || !hasCustomBackground;
        }
        if (DOM.stageBackgroundTransformResetButton) {
            DOM.stageBackgroundTransformResetButton.disabled = isUploading || !hasCustomBackground;
        }
    }

    function handleStageBackgroundChange(backgroundKey) {
        if (!UI_STATE.config || !UI_STATE.config.stage) {
            return;
        }

        applyStageBackgroundByKey(UI_STATE.config.stage, backgroundKey);
        const selectedOption = currentStageBackgroundOption();
        if (!selectedOption || !selectedOption.url) {
            setRunStatus("已切换为不使用背景");
            return;
        }
        setRunStatus(`已切换舞台背景：${selectedOption.label || selectedOption.key}`);
    }

    function handleStageBackgroundReset() {
        if (!UI_STATE.config || !UI_STATE.config.stage) {
            return;
        }

        applyStageBackgroundByKey(
            UI_STATE.config.stage,
            UI_STATE.config.stage.default_background_key,
        );
        setRunStatus("已切换为不使用背景");
    }

    function handleStageBackgroundTransformInput() {
        const selectedOption = currentStageBackgroundOption();
        if (!selectedOption || !selectedOption.url) {
            syncStageBackgroundTransformInputs(null, DEFAULT_STAGE_BACKGROUND_TRANSFORM);
            updateStageBackgroundControls();
            return;
        }

        const nextTransform = readStageBackgroundTransformFromInputs();
        UI_STATE.currentStageBackgroundTransform = nextTransform;
        applyStageBackgroundTransform(nextTransform);
        persistStageBackgroundTransform(selectedOption.key, nextTransform);
        updateStageBackgroundTransformValueLabels(nextTransform);
        updateStageBackgroundDetail(selectedOption, nextTransform);
        updateStageBackgroundControls();
    }

    function handleStageBackgroundTransformReset() {
        const selectedOption = currentStageBackgroundOption();
        if (!selectedOption || !selectedOption.url) {
            return;
        }

        clearSavedStageBackgroundTransform(selectedOption.key);
        const nextTransform = {
            ...DEFAULT_STAGE_BACKGROUND_TRANSFORM,
        };
        UI_STATE.currentStageBackgroundTransform = nextTransform;
        applyStageBackgroundTransform(nextTransform);
        syncStageBackgroundTransformInputs(selectedOption, nextTransform);
        updateStageBackgroundDetail(selectedOption, nextTransform);
        updateStageBackgroundControls();
        setRunStatus(`已重置背景取景：${selectedOption.label || selectedOption.key}`);
    }

    async function handleStageBackgroundUpload() {
        if (!DOM.stageBackgroundUploadInput || !UI_STATE.config) {
            return;
        }

        const [file] = DOM.stageBackgroundUploadInput.files || [];
        DOM.stageBackgroundUploadInput.value = "";
        if (!file) {
            return;
        }

        const previousStageConfig = UI_STATE.config.stage || normalizeStageConfig(null);
        const previousKeys = new Set(
            (previousStageConfig.backgrounds || []).map((item) => item.key),
        );

        updateStageBackgroundControls({ isUploading: true });
        setRunStatus("正在上传舞台背景…");

        try {
            const formData = new FormData();
            formData.append("image", file);

            const response = await fetch("/api/web/stage/backgrounds", {
                method: "POST",
                body: formData,
            });
            if (!response.ok) {
                throw await responseToError(response);
            }

            const payload = await response.json();
            const nextStageConfig = normalizeStageConfig(payload);
            UI_STATE.config.stage = nextStageConfig;

            const uploadedOption = nextStageConfig.backgrounds.find(
                (item) => item.kind !== "default" && !previousKeys.has(item.key),
            ) || nextStageConfig.backgrounds[nextStageConfig.backgrounds.length - 1] || null;

            const nextKey = uploadedOption
                ? uploadedOption.key
                : nextStageConfig.default_background_key;
            applyStageBackgroundByKey(nextStageConfig, nextKey);
            setRunStatus(`已上传舞台背景：${uploadedOption ? uploadedOption.label : file.name}`);
        } catch (error) {
            console.error(error);
            applyStageBackgroundByKey(previousStageConfig, UI_STATE.selectedStageBackgroundKey);
            setRunStatus(error.message || "舞台背景上传失败");
        } finally {
            updateStageBackgroundControls();
        }
    }

    function findLive2DModelOption(modelOptions, selectionKey) {
        const normalizedSelectionKey = String(selectionKey || "").trim();
        if (!normalizedSelectionKey) {
            return null;
        }
        return modelOptions.find((item) => item.selection_key === normalizedSelectionKey) || null;
    }

    async function handleLive2DDirectoryUpload() {
        if (!DOM.live2dUploadInput || !UI_STATE.config) {
            return;
        }

        const uploadEntries = Array.from(DOM.live2dUploadInput.files || [])
            .map((file) => ({
                file: file,
                relativePath: String(file.webkitRelativePath || file.name || "").trim(),
            }))
            .filter((item) => item.relativePath);
        DOM.live2dUploadInput.value = "";
        if (uploadEntries.length === 0) {
            return;
        }

        const previousLive2DConfig = UI_STATE.config.live2d;
        const previousModelOptions = resolveLive2DModelOptions(previousLive2DConfig);
        const previousKeys = new Set(previousModelOptions.map((item) => item.selection_key));

        updateLive2DUploadControls({ isUploading: true });
        setRunStatus("正在上传 Live2D 文件夹…");

        try {
            const formData = new FormData();
            uploadEntries.forEach((item) => {
                formData.append("files", item.file, item.file.name);
                formData.append("relative_paths", item.relativePath);
            });

            const response = await fetch("/api/web/live2d", {
                method: "POST",
                body: formData,
            });
            if (!response.ok) {
                throw await responseToError(response);
            }

            const payload = await response.json();
            const nextModelOptions = resolveLive2DModelOptions(payload);
            const uploadedOption = nextModelOptions.find(
                (item) => !previousKeys.has(item.selection_key),
            ) || findLive2DModelOption(nextModelOptions, payload.selection_key)
                || nextModelOptions[0]
                || null;

            if (!uploadedOption) {
                throw new Error("No Live2D model was found after upload.");
            }

            const nextLive2DConfig = buildCurrentLive2DConfig(uploadedOption, nextModelOptions);
            UI_STATE.config.live2d = nextLive2DConfig;
            renderLive2DModelOptions(nextModelOptions, nextLive2DConfig.selection_key);

            const didLoadModel = await loadLive2DModel(nextLive2DConfig);
            if (
                !didLoadModel
                || UI_STATE.config.live2d.selection_key !== nextLive2DConfig.selection_key
            ) {
                return;
            }

            setRunStatus(`已上传 Live2D 模型：${buildLive2DModelLabel(uploadedOption)}`);
        } catch (error) {
            console.error(error);
            UI_STATE.config.live2d = previousLive2DConfig;
            renderLive2DModelOptions(previousModelOptions, previousLive2DConfig.selection_key);
            persistLive2DSelectionKey(previousLive2DConfig.selection_key);
            setRunStatus(error.message || "Live2D 文件夹上传失败");
        } finally {
            updateLive2DUploadControls();
        }
    }

    async function handleLive2DModelChange(selectionKey) {
        if (!UI_STATE.config) {
            return;
        }

        const modelOptions = resolveLive2DModelOptions(UI_STATE.config.live2d);
        const nextModelOption = findLive2DModelOption(modelOptions, selectionKey);
        if (!nextModelOption) {
            renderLive2DModelOptions(modelOptions, UI_STATE.config.live2d.selection_key);
            return;
        }

        if (UI_STATE.config.live2d.selection_key === nextModelOption.selection_key) {
            return;
        }

        const previousLive2DConfig = UI_STATE.config.live2d;
        const nextLive2DConfig = buildCurrentLive2DConfig(nextModelOption, modelOptions);
        UI_STATE.config.live2d = nextLive2DConfig;
        renderLive2DModelOptions(modelOptions, nextLive2DConfig.selection_key);
        setRunStatus(`Switching model: ${buildLive2DModelLabel(nextModelOption)}`);

        try {
            const didLoadModel = await loadLive2DModel(nextLive2DConfig);
            if (
                !didLoadModel
                || UI_STATE.config.live2d.selection_key !== nextLive2DConfig.selection_key
            ) {
                return;
            }
            setRunStatus(`Model switched: ${buildLive2DModelLabel(nextModelOption)}`);
        } catch (error) {
            console.error(error);
            if (UI_STATE.config.live2d.selection_key !== nextLive2DConfig.selection_key) {
                return;
            }
            UI_STATE.config.live2d = previousLive2DConfig;
            renderLive2DModelOptions(modelOptions, previousLive2DConfig.selection_key);
            persistLive2DSelectionKey(previousLive2DConfig.selection_key);

            if (previousLive2DConfig.available && previousLive2DConfig.model_url) {
                try {
                    await loadLive2DModel(previousLive2DConfig);
                } catch (restoreError) {
                    console.error("Failed to restore previous Live2D model", restoreError);
                }
            }

            setRunStatus(error.message || "Live2D 模型加载失败");
        }
    }

    function loadSavedLive2DSelectionKey() {
        return String(window.localStorage.getItem("echobot.web.live2d.selection") || "").trim();
    }

    function persistLive2DSelectionKey(selectionKey) {
        window.localStorage.setItem("echobot.web.live2d.selection", String(selectionKey || ""));
    }

    function loadSavedLive2DMouseFollowEnabled() {
        const raw = window.localStorage.getItem("echobot.web.live2d.mouse_follow");
        if (raw === null) {
            return true;
        }
        return raw === "true";
    }

    function persistLive2DMouseFollowEnabled(enabled) {
        window.localStorage.setItem(
            "echobot.web.live2d.mouse_follow",
            String(Boolean(enabled)),
        );
    }

    function handleMouseFollowToggle() {
        if (!DOM.live2dMouseFollowCheckbox) {
            return;
        }

        UI_STATE.live2dMouseFollowEnabled = DOM.live2dMouseFollowCheckbox.checked;
        persistLive2DMouseFollowEnabled(UI_STATE.live2dMouseFollowEnabled);
        applyLive2DMouseFollowSetting();
        setRunStatus(
            UI_STATE.live2dMouseFollowEnabled
                ? "已开启 Live 2D 眼神跟随"
                : "已关闭 Live 2D 眼神跟随",
        );
    }

    function updateSceneFilterBounds() {
        if (!UI_STATE.pixiApp || !UI_STATE.live2dStage) {
            return;
        }

        UI_STATE.live2dStage.hitArea = UI_STATE.pixiApp.screen;
        if (UI_STATE.live2dScene) {
            UI_STATE.live2dScene.filterArea = UI_STATE.pixiApp.screen;
        }
        if (UI_STATE.live2dBackgroundLayer) {
            UI_STATE.live2dBackgroundLayer.filterArea = UI_STATE.pixiApp.screen;
        }
    }

    function createStagePostFilter() {
        return new window.PIXI.Filter(undefined, ATMOSPHERE_FILTER_FRAGMENT, {
            uLightPos: [DEFAULT_STAGE_LIGHT_POSITION.x, DEFAULT_STAGE_LIGHT_POSITION.y],
            uAmbientColor: [1.04, 1.02, 1.08],
            uHighlightColor: [1.0, 0.92, 0.98],
            uGlowStrength: 0.84,
            uGrainStrength: 1,
            uVignetteStrength: 0.2,
            uPulse: 1,
            uTime: 0,
        });
    }

    function randomBetween(min, max) {
        return min + Math.random() * (max - min);
    }

    function createSoftParticleTexture(size, colorStops) {
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const context = canvas.getContext("2d");
        if (!context) {
            return window.PIXI.Texture.WHITE;
        }

        const gradient = context.createRadialGradient(
            size * 0.5,
            size * 0.5,
            0,
            size * 0.5,
            size * 0.5,
            size * 0.5,
        );
        colorStops.forEach(([offset, color]) => {
            gradient.addColorStop(offset, color);
        });

        context.fillStyle = gradient;
        context.fillRect(0, 0, size, size);
        return window.PIXI.Texture.from(canvas);
    }

    function ensureStageParticleTextures() {
        if (UI_STATE.stageParticleTextures) {
            return UI_STATE.stageParticleTextures;
        }

        UI_STATE.stageParticleTextures = createSoftParticleTexture(80, [
            [0, "rgba(255,255,255,0.98)"],
            [0.16, "rgba(255,251,246,0.68)"],
            [0.38, "rgba(255,244,232,0.22)"],
            [1, "rgba(255,255,255,0)"],
        ]);
        return UI_STATE.stageParticleTextures;
    }

    function resetStageParticleSprite(sprite, stageWidth, stageHeight, spawnEdge = "random") {
        if (!sprite || !sprite.stageParticle) {
            return;
        }

        const particle = sprite.stageParticle;
        const margin = 110;
        const width = Math.max(stageWidth, 1);
        const height = Math.max(stageHeight, 1);

        particle.margin = margin;
        particle.baseAlpha = randomBetween(0.2, 0.42);
        particle.baseScale = randomBetween(0.12, 0.3);
        particle.driftX = randomBetween(-12, 12);
        particle.driftY = randomBetween(-20, -8);
        particle.wobbleAmplitudeX = randomBetween(10, 26);
        particle.wobbleAmplitudeY = randomBetween(6, 14);
        particle.wobbleSpeed = randomBetween(0.35, 0.95);
        particle.pulseSpeed = randomBetween(0.55, 1.35);
        particle.wobblePhase = randomBetween(0, Math.PI * 2);
        particle.pulsePhase = randomBetween(0, Math.PI * 2);
        particle.rotationSpeed = randomBetween(-0.08, 0.08);
        particle.baseX = randomBetween(-margin, width + margin);
        particle.baseY = spawnEdge === "bottom"
            ? height + randomBetween(0, margin)
            : randomBetween(-margin, height + margin);

        sprite.scale.set(particle.baseScale);
        sprite.rotation = randomBetween(0, Math.PI * 2);
        sprite.alpha = 0;
        sprite.visible = false;
        sprite.tint = Math.random() < 0.5 ? 0xfffdf8 : 0xf5efe7;
    }

    function ensureStageParticleLayer() {
        if (UI_STATE.live2dParticleLayer) {
            return UI_STATE.live2dParticleLayer;
        }

        const texture = ensureStageParticleTextures();
        const layer = new window.PIXI.Container();
        layer.interactiveChildren = false;
        UI_STATE.live2dParticleLayer = layer;
        UI_STATE.stageParticleSprites = [];

        for (let index = 0; index < STAGE_PARTICLE_COUNT; index += 1) {
            const sprite = new window.PIXI.Sprite(texture);
            sprite.anchor.set(0.5);
            sprite.interactive = false;
            sprite.blendMode = window.PIXI.BLEND_MODES.SCREEN;
            sprite.stageParticle = {
                margin: 0,
                baseAlpha: 0,
                baseScale: 0,
                baseX: 0,
                baseY: 0,
                driftX: 0,
                driftY: 0,
                wobbleAmplitudeX: 0,
                wobbleAmplitudeY: 0,
                wobbleSpeed: 0,
                pulseSpeed: 0,
                wobblePhase: 0,
                pulsePhase: 0,
                rotationSpeed: 0,
            };
            resetStageParticleSprite(sprite, 1, 1);
            UI_STATE.stageParticleSprites.push(sprite);
            layer.addChild(sprite);
        }

        return layer;
    }

    function resetAllStageParticles(stageWidth, stageHeight) {
        if (!Array.isArray(UI_STATE.stageParticleSprites)) {
            return;
        }

        UI_STATE.stageParticleSprites.forEach((sprite) => {
            if (!sprite || !sprite.stageParticle) {
                return;
            }
            resetStageParticleSprite(sprite, stageWidth, stageHeight, "random");
        });
    }

    function resolveStageParticleTargets(settings) {
        const density = clamp(settings.particleDensity / 100, 0, 1);
        return {
            density: density,
            count: density <= 0
                ? 0
                : Math.max(1, Math.round(STAGE_PARTICLE_COUNT * Math.pow(density, 0.72))),
        };
    }

    function updateStageParticleLayer(now, deltaSeconds) {
        if (
            !UI_STATE.pixiApp
            || !UI_STATE.live2dParticleLayer
            || !Array.isArray(UI_STATE.stageParticleSprites)
            || UI_STATE.stageParticleSprites.length === 0
        ) {
            return;
        }

        const settings = UI_STATE.stageEffects || DEFAULT_STAGE_EFFECT_SETTINGS;
        const particlesEnabled = settings.enabled && settings.particlesEnabled;
        UI_STATE.live2dParticleLayer.visible = particlesEnabled;
        if (!particlesEnabled) {
            return;
        }

        const { density, count } = resolveStageParticleTargets(settings);
        const stageWidth = Math.max(UI_STATE.pixiApp.screen.width, 1);
        const stageHeight = Math.max(UI_STATE.pixiApp.screen.height, 1);
        const lightPosX = UI_STATE.stageLightCurrentX * stageWidth;
        const lightPosY = UI_STATE.stageLightCurrentY * stageHeight;
        const speedMultiplier = clamp(settings.particleSpeed / 100, 0, 3);
        const sizeMultiplier = clamp(settings.particleSize / 100, 0.4, 2.8);
        const opacityMultiplier = clamp(settings.particleOpacity / 100, 0, 1.8);
        const densityAlpha = clamp(0.72 + density * 1.18, 0.48, 1.9);
        const lightBoost = settings.lightEnabled
            ? clamp(0.96 + settings.glowStrength / 160, 0.96, 1.6)
            : 1;
        const motionSpeed = Math.max(speedMultiplier, 0.05);
        let visibleCount = 0;

        UI_STATE.stageParticleSprites.forEach((sprite) => {
            const particle = sprite.stageParticle;
            if (!particle) {
                return;
            }

            const isVisible = visibleCount < count;
            visibleCount += 1;
            sprite.visible = isVisible;
            if (!isVisible) {
                sprite.alpha = 0;
                return;
            }

            particle.baseX += particle.driftX * deltaSeconds * speedMultiplier;
            particle.baseY += particle.driftY * deltaSeconds * speedMultiplier;

            const wobbleX = Math.sin(now * particle.wobbleSpeed * motionSpeed + particle.wobblePhase)
                * particle.wobbleAmplitudeX;
            const wobbleY = Math.cos(
                now * particle.wobbleSpeed * 0.72 * motionSpeed + particle.wobblePhase,
            ) * particle.wobbleAmplitudeY;
            sprite.x = particle.baseX + wobbleX;
            sprite.y = particle.baseY + wobbleY;
            sprite.rotation += particle.rotationSpeed * deltaSeconds * motionSpeed;

            const lightDistance = Math.hypot(sprite.x - lightPosX, sprite.y - lightPosY);
            const lightRadius = Math.max(stageWidth, stageHeight) * 0.86;
            const lightFactor = clamp(
                1 - lightDistance / Math.max(lightRadius, 1),
                0.78,
                1,
            );
            const pulse = 0.92 + Math.sin(
                now * particle.pulseSpeed * motionSpeed + particle.pulsePhase,
            ) * 0.08;
            sprite.alpha = clamp(
                particle.baseAlpha
                * densityAlpha
                * opacityMultiplier
                * lightBoost
                * lightFactor
                * pulse,
                0,
                1,
            );

            const scalePulse = 0.96 + Math.sin(
                now * particle.pulseSpeed * motionSpeed + particle.pulsePhase,
            ) * 0.04;
            sprite.scale.set(particle.baseScale * sizeMultiplier * scalePulse);

            if (
                sprite.y < -particle.margin
                || sprite.x < -particle.margin * 1.5
                || sprite.x > stageWidth + particle.margin * 1.5
            ) {
                resetStageParticleSprite(sprite, stageWidth, stageHeight, "bottom");
            }
        });
    }

    function applyStageLightingVars(lightX, lightY, pulse) {
        if (!DOM.stageElement) {
            return;
        }

        const rimX = clamp(
            lightX + (DEFAULT_STAGE_RIM_LIGHT_POSITION.x - DEFAULT_STAGE_LIGHT_POSITION.x),
            0.12,
            0.9,
        );
        const rimY = clamp(
            lightY + (DEFAULT_STAGE_RIM_LIGHT_POSITION.y - DEFAULT_STAGE_LIGHT_POSITION.y),
            0.16,
            0.82,
        );
        DOM.stageElement.style.setProperty("--stage-light-x", `${roundTo(lightX * 100, 1)}%`);
        DOM.stageElement.style.setProperty("--stage-light-y", `${roundTo(lightY * 100, 1)}%`);
        DOM.stageElement.style.setProperty("--stage-light-rim-x", `${roundTo(rimX * 100, 1)}%`);
        DOM.stageElement.style.setProperty("--stage-light-rim-y", `${roundTo(rimY * 100, 1)}%`);
        DOM.stageElement.style.setProperty("--stage-pulse", String(roundTo(pulse, 3)));
    }

    function updateStageAtmosphereFrame() {
        if (!UI_STATE.pixiApp) {
            return;
        }

        const effects = UI_STATE.stageEffects || DEFAULT_STAGE_EFFECT_SETTINGS;
        const lightEnabled = effects.enabled && effects.lightEnabled;
        const now = performance.now() / 1000;
        const deltaSeconds = clamp(
            UI_STATE.pixiApp.ticker && Number.isFinite(UI_STATE.pixiApp.ticker.deltaMS)
                ? UI_STATE.pixiApp.ticker.deltaMS / 1000
                : 1 / 60,
            1 / 120,
            0.05,
        );
        const manualLightX = effects.lightX / 100;
        const manualLightY = effects.lightY / 100;
        const baseLightX = effects.lightFloatEnabled && lightEnabled
            ? manualLightX + Math.sin(now * 0.37) * 0.028
            : manualLightX;
        const baseLightY = effects.lightFloatEnabled && lightEnabled
            ? manualLightY + Math.cos(now * 0.29) * 0.018
            : manualLightY;
        const targetX = clamp(baseLightX, 0, 1);
        const targetY = clamp(baseLightY, 0, 1);

        UI_STATE.stageLightCurrentX += (targetX - UI_STATE.stageLightCurrentX) * 0.08;
        UI_STATE.stageLightCurrentY += (targetY - UI_STATE.stageLightCurrentY) * 0.08;

        const pulse = lightEnabled
            ? 0.96 + Math.sin(now * 1.7) * 0.04
            : 0.9;
        applyStageLightingVars(UI_STATE.stageLightCurrentX, UI_STATE.stageLightCurrentY, pulse);

        if (UI_STATE.stagePostFilter) {
            UI_STATE.stagePostFilter.uniforms.uLightPos = [
                UI_STATE.stageLightCurrentX,
                UI_STATE.stageLightCurrentY,
            ];
            UI_STATE.stagePostFilter.uniforms.uPulse = pulse;
            UI_STATE.stagePostFilter.uniforms.uTime = now;
        }

        updateStageParticleLayer(now, deltaSeconds);
        updateSceneFilterBounds();
    }

    function installStageAtmosphereTicker() {
        if (!UI_STATE.pixiApp || UI_STATE.stageAtmosphereTick) {
            return;
        }

        UI_STATE.stageAtmosphereTick = () => {
            updateStageAtmosphereFrame();
        };
        UI_STATE.pixiApp.ticker.add(UI_STATE.stageAtmosphereTick);
        updateStageAtmosphereFrame();
    }

    function ensureStageResizeObserver() {
        if (!window.ResizeObserver || UI_STATE.stageResizeObserver || !DOM.stageElement) {
            return;
        }

        UI_STATE.stageResizeObserver = new window.ResizeObserver(() => {
            window.requestAnimationFrame(() => {
                updateSceneFilterBounds();
                if (UI_STATE.pixiApp) {
                    resetAllStageParticles(
                        Math.max(UI_STATE.pixiApp.screen.width, 1),
                        Math.max(UI_STATE.pixiApp.screen.height, 1),
                    );
                }
                if (UI_STATE.currentStageBackgroundTransform) {
                    applyStageBackgroundTransform(UI_STATE.currentStageBackgroundTransform);
                }
                refreshLive2DFocusFromLastPointer();
            });
        });
        UI_STATE.stageResizeObserver.observe(DOM.stageElement);
    }

    function ensureDefaultStageBackgroundTexture() {
        if (UI_STATE.defaultStageBackgroundTexture) {
            return UI_STATE.defaultStageBackgroundTexture;
        }

        const canvas = document.createElement("canvas");
        canvas.width = 1200;
        canvas.height = 900;
        const context = canvas.getContext("2d");
        if (!context) {
            UI_STATE.defaultStageBackgroundTexture = window.PIXI.Texture.WHITE;
            return UI_STATE.defaultStageBackgroundTexture;
        }

        const baseGradient = context.createLinearGradient(0, 0, 0, canvas.height);
        baseGradient.addColorStop(0, "#f8f0e7");
        baseGradient.addColorStop(0.46, "#edd9c5");
        baseGradient.addColorStop(1, "#d8bba0");
        context.fillStyle = baseGradient;
        context.fillRect(0, 0, canvas.width, canvas.height);

        const topGlow = context.createRadialGradient(
            canvas.width * 0.5,
            canvas.height * 0.16,
            0,
            canvas.width * 0.5,
            canvas.height * 0.16,
            canvas.width * 0.42,
        );
        topGlow.addColorStop(0, "rgba(255,255,255,0.72)");
        topGlow.addColorStop(1, "rgba(255,255,255,0)");
        context.fillStyle = topGlow;
        context.fillRect(0, 0, canvas.width, canvas.height);

        const warmGlow = context.createRadialGradient(
            canvas.width * 0.5,
            canvas.height * 0.98,
            0,
            canvas.width * 0.5,
            canvas.height * 0.98,
            canvas.width * 0.54,
        );
        warmGlow.addColorStop(0, "rgba(202,92,54,0.18)");
        warmGlow.addColorStop(1, "rgba(202,92,54,0)");
        context.fillStyle = warmGlow;
        context.fillRect(0, 0, canvas.width, canvas.height);

        UI_STATE.defaultStageBackgroundTexture = window.PIXI.Texture.from(canvas);
        return UI_STATE.defaultStageBackgroundTexture;
    }

    function loadPixiTexture(url) {
        return new Promise((resolve, reject) => {
            const texture = window.PIXI.Texture.from(url);
            const baseTexture = texture.baseTexture;

            if (baseTexture.valid) {
                resolve(texture);
                return;
            }

            const handleLoaded = () => {
                cleanup();
                resolve(texture);
            };
            const handleError = (error) => {
                cleanup();
                reject(error || new Error(`Failed to load texture: ${url}`));
            };
            const cleanup = () => {
                baseTexture.off("loaded", handleLoaded);
                baseTexture.off("error", handleError);
            };

            baseTexture.on("loaded", handleLoaded);
            baseTexture.on("error", handleError);
        });
    }

    function ensureStageBackgroundSprite() {
        if (UI_STATE.stageBackgroundSprite) {
            return UI_STATE.stageBackgroundSprite;
        }

        const sprite = new window.PIXI.Sprite(window.PIXI.Texture.WHITE);
        sprite.anchor.set(0, 0);
        sprite.zIndex = 0;
        UI_STATE.stageBackgroundSprite = sprite;

        if (UI_STATE.live2dBackgroundLayer) {
            UI_STATE.live2dBackgroundLayer.addChild(sprite);
        }

        return sprite;
    }

    async function syncPixiStageBackground(backgroundOption, transform) {
        if (!UI_STATE.pixiApp || !UI_STATE.live2dBackgroundLayer) {
            return;
        }

        const loadToken = ++UI_STATE.stageBackgroundLoadToken;
        const hasCustomBackground = Boolean(backgroundOption && String(backgroundOption.url || "").trim());

        try {
            let texture;
            if (hasCustomBackground) {
                const url = String(backgroundOption.url || "").trim().replace(/"/g, "%22");
                texture = await loadPixiTexture(url);
            } else {
                texture = ensureDefaultStageBackgroundTexture();
            }

            if (loadToken !== UI_STATE.stageBackgroundLoadToken) {
                return;
            }

            const sprite = ensureStageBackgroundSprite();
            sprite.texture = texture;
            sprite.visible = true;
            sprite.alpha = hasCustomBackground ? 0.98 : 1;

            const realWidth = texture.baseTexture && texture.baseTexture.realWidth
                ? texture.baseTexture.realWidth
                : texture.width;
            const realHeight = texture.baseTexture && texture.baseTexture.realHeight
                ? texture.baseTexture.realHeight
                : texture.height;
            UI_STATE.currentBackgroundImageNaturalSize = {
                w: realWidth,
                h: realHeight,
            };

            applyStageBackgroundTransform(transform);
            applyStageEffectsToRuntime(
                UI_STATE.stageEffects || DEFAULT_STAGE_EFFECT_SETTINGS,
            );
        } catch (error) {
            console.warn("Failed to sync Pixi stage background", error);
        }
    }

    function createStageScene() {
        UI_STATE.live2dScene = new window.PIXI.Container();
        UI_STATE.live2dBackgroundLayer = new window.PIXI.Container();
        UI_STATE.live2dParticleLayer = ensureStageParticleLayer();
        UI_STATE.live2dCharacterLayer = new window.PIXI.Container();
        UI_STATE.stageLightCurrentX = DEFAULT_STAGE_LIGHT_POSITION.x;
        UI_STATE.stageLightCurrentY = DEFAULT_STAGE_LIGHT_POSITION.y;

        UI_STATE.stageBackgroundBlurFilter = new window.PIXI.filters.BlurFilter();
        UI_STATE.stageBackgroundBlurFilter.blur = 1.2;
        UI_STATE.live2dBackgroundLayer.filters = [UI_STATE.stageBackgroundBlurFilter];

        UI_STATE.stagePostFilter = createStagePostFilter();
        UI_STATE.live2dScene.filters = [UI_STATE.stagePostFilter];

        UI_STATE.live2dScene.addChild(UI_STATE.live2dBackgroundLayer);
        UI_STATE.live2dScene.addChild(UI_STATE.live2dParticleLayer);
        UI_STATE.live2dScene.addChild(UI_STATE.live2dCharacterLayer);
        UI_STATE.live2dStage.addChild(UI_STATE.live2dScene);

        if (UI_STATE.pixiApp) {
            resetAllStageParticles(
                Math.max(UI_STATE.pixiApp.screen.width, 1),
                Math.max(UI_STATE.pixiApp.screen.height, 1),
            );
        }

        ensureStageResizeObserver();
        installStageAtmosphereTicker();
        updateSceneFilterBounds();
        applyStageEffectsSettings(
            UI_STATE.stageEffects || DEFAULT_STAGE_EFFECT_SETTINGS,
            { persist: false },
        );

        const activeBackground = currentStageBackgroundOption();
        const activeTransform = UI_STATE.currentStageBackgroundTransform
            || DEFAULT_STAGE_BACKGROUND_TRANSFORM;
        void syncPixiStageBackground(activeBackground, activeTransform);
    }

    function initializePixiApplication() {
        if (!window.PIXI) {
            throw new Error("Failed to load PIXI");
        }

        if (!window.PIXI.live2d || !window.PIXI.live2d.Live2DModel) {
            throw new Error("Failed to load pixi-live2d-display");
        }

        UI_STATE.pixiApp = new window.PIXI.Application({
            view: document.getElementById("live2d-canvas"),
            resizeTo: DOM.stageElement,
            autoStart: true,
            antialias: true,
            backgroundAlpha: 0,
        });
        UI_STATE.live2dStage = UI_STATE.pixiApp.stage;
        UI_STATE.live2dStage.interactive = true;
        UI_STATE.live2dStage.hitArea = UI_STATE.pixiApp.screen;
        createStageScene();
    }

    async function loadLive2DModel(live2dConfig) {
        if (!live2dConfig.available || !live2dConfig.model_url) {
            disposeCurrentLive2DModel();
            setStageMessage("未找到 Live2D 模型。请检查 .echobot/live2d 目录。");
            return false;
        }

        const loadToken = ++UI_STATE.live2dLoadToken;
        setStageMessage("正在加载 Live2D 模型…");

        try {
            const model = await window.PIXI.live2d.Live2DModel.from(live2dConfig.model_url, {
                autoInteract: false,
            });
            if (loadToken !== UI_STATE.live2dLoadToken) {
                destroyLive2DModel(model);
                return false;
            }

            disposeCurrentLive2DModel();
            UI_STATE.live2dModel = model;
            if (UI_STATE.live2dCharacterLayer) {
                UI_STATE.live2dCharacterLayer.addChild(model);
            } else {
                UI_STATE.live2dStage.addChild(model);
            }

            model.anchor.set(0.5, 0.5);
            model.cursor = "grab";
            model.interactive = true;

            applyLive2DMouseFollowSetting();
            bindLive2DDrag(model);
            attachLipSyncHook(model, live2dConfig);
            resetLive2DView();

            setStageMessage("");
            return true;
        } catch (error) {
            console.error(error);
            if (loadToken === UI_STATE.live2dLoadToken) {
                setStageMessage(`Failed to load model: ${error.message || error}`);
            }
            throw new Error(`Failed to load Live2D model: ${error.message || error}`);
        }
    }

    function setStageMessage(text) {
        const message = String(text || "").trim();
        DOM.stageMessage.textContent = message;
        DOM.stageMessage.hidden = message === "";
    }

    function bindLive2DDrag(model) {
        unbindLive2DDrag();

        const pointerDown = (event) => {
            const point = event.data.getLocalPosition(UI_STATE.live2dStage);
            UI_STATE.dragging = true;
            UI_STATE.dragPointerId = event.data.pointerId;
            UI_STATE.dragOffsetX = model.x - point.x;
            UI_STATE.dragOffsetY = model.y - point.y;
            model.cursor = "grabbing";
        };

        const pointerMove = (event) => {
            if (!UI_STATE.dragging || event.data.pointerId !== UI_STATE.dragPointerId) {
                return;
            }

            const point = event.data.getLocalPosition(UI_STATE.live2dStage);
            model.x = point.x + UI_STATE.dragOffsetX;
            model.y = point.y + UI_STATE.dragOffsetY;
            refreshLive2DFocusFromLastPointer();
            persistLive2DTransform();
        };

        const stopDragging = () => {
            if (!UI_STATE.dragging) {
                return;
            }

            UI_STATE.dragging = false;
            UI_STATE.dragPointerId = null;
            model.cursor = "grab";
            persistLive2DTransform();
        };

        model.on("pointerdown", pointerDown);
        UI_STATE.live2dStage.on("pointermove", pointerMove);
        UI_STATE.live2dStage.on("pointerup", stopDragging);
        UI_STATE.live2dStage.on("pointerupoutside", stopDragging);
        UI_STATE.live2dStage.on("pointerleave", stopDragging);

        UI_STATE.live2dDragModel = model;
        UI_STATE.live2dDragHandlers = {
            pointerDown: pointerDown,
            pointerMove: pointerMove,
            stopDragging: stopDragging,
        };
    }

    function unbindLive2DDrag() {
        if (!UI_STATE.live2dDragHandlers || !UI_STATE.live2dStage) {
            return;
        }

        if (UI_STATE.live2dDragModel && typeof UI_STATE.live2dDragModel.off === "function") {
            UI_STATE.live2dDragModel.off("pointerdown", UI_STATE.live2dDragHandlers.pointerDown);
        }

        UI_STATE.live2dStage.off("pointermove", UI_STATE.live2dDragHandlers.pointerMove);
        UI_STATE.live2dStage.off("pointerup", UI_STATE.live2dDragHandlers.stopDragging);
        UI_STATE.live2dStage.off("pointerupoutside", UI_STATE.live2dDragHandlers.stopDragging);
        UI_STATE.live2dStage.off("pointerleave", UI_STATE.live2dDragHandlers.stopDragging);

        UI_STATE.live2dDragModel = null;
        UI_STATE.live2dDragHandlers = null;
    }

    function bindLive2DFocus() {
        unbindLive2DFocus();

        if (!UI_STATE.live2dStage) {
            return;
        }

        const pointerMove = (event) => {
            const globalPoint = event && event.data ? event.data.global : null;
            if (!globalPoint) {
                return;
            }

            UI_STATE.live2dLastPointerX = globalPoint.x;
            UI_STATE.live2dLastPointerY = globalPoint.y;
            updateLive2DFocusFromGlobalPoint(globalPoint.x, globalPoint.y);
        };

        UI_STATE.live2dStage.on("pointermove", pointerMove);
        UI_STATE.live2dFocusHandlers = {
            pointerMove: pointerMove,
        };
        refreshLive2DFocusFromLastPointer();
    }

    function unbindLive2DFocus() {
        if (!UI_STATE.live2dFocusHandlers || !UI_STATE.live2dStage) {
            return;
        }

        UI_STATE.live2dStage.off("pointermove", UI_STATE.live2dFocusHandlers.pointerMove);
        UI_STATE.live2dFocusHandlers = null;
    }

    function refreshLive2DFocusFromLastPointer() {
        if (
            !UI_STATE.live2dMouseFollowEnabled
            || !Number.isFinite(UI_STATE.live2dLastPointerX)
            || !Number.isFinite(UI_STATE.live2dLastPointerY)
        ) {
            return;
        }

        updateLive2DFocusFromGlobalPoint(
            UI_STATE.live2dLastPointerX,
            UI_STATE.live2dLastPointerY,
        );
    }

    function updateLive2DFocusFromGlobalPoint(globalX, globalY) {
        const model = UI_STATE.live2dModel;
        const internalModel = model && model.internalModel;
        if (
            !model
            || !internalModel
            || !internalModel.focusController
            || typeof internalModel.focusController.focus !== "function"
        ) {
            return;
        }

        const localPoint = toLive2DModelPoint(model, globalX, globalY);
        if (!localPoint) {
            return;
        }

        const rawFocusX = normalizeLive2DFocusAxis(
            localPoint.x,
            0,
            internalModel.originalWidth,
        );
        const visibleVerticalBounds = resolveVisibleLive2DVerticalBounds(model);
        const rawFocusY = visibleVerticalBounds
            ? normalizeLive2DFocusAxis(
                localPoint.y,
                visibleVerticalBounds.top,
                visibleVerticalBounds.bottom,
            )
            : normalizeLive2DFocusAxis(
                localPoint.y,
                0,
                internalModel.originalHeight,
            );

        applyLive2DFocusTarget(
            internalModel.focusController,
            rawFocusX,
            rawFocusY,
        );
    }

    function toLive2DModelPoint(model, globalX, globalY) {
        if (
            !window.PIXI
            || typeof window.PIXI.Point !== "function"
            || typeof model.toModelPosition !== "function"
        ) {
            return null;
        }

        const globalPoint = new window.PIXI.Point(globalX, globalY);
        return model.toModelPosition(globalPoint, new window.PIXI.Point());
    }

    function resolveVisibleLive2DVerticalBounds(model) {
        if (!UI_STATE.pixiApp || typeof model.getBounds !== "function") {
            return null;
        }

        const modelBounds = model.getBounds();
        const screen = UI_STATE.pixiApp.screen;
        if (
            !modelBounds
            || modelBounds.width <= 0
            || modelBounds.height <= 0
            || screen.width <= 0
            || screen.height <= 0
        ) {
            return null;
        }

        const visibleLeft = Math.max(modelBounds.x, screen.x);
        const visibleTop = Math.max(modelBounds.y, screen.y);
        const visibleRight = Math.min(
            modelBounds.x + modelBounds.width,
            screen.x + screen.width,
        );
        const visibleBottom = Math.min(
            modelBounds.y + modelBounds.height,
            screen.y + screen.height,
        );

        if (visibleRight <= visibleLeft || visibleBottom <= visibleTop) {
            return null;
        }

        const topPoint = toLive2DModelPoint(model, visibleLeft, visibleTop);
        const bottomPoint = toLive2DModelPoint(model, visibleLeft, visibleBottom);
        if (!topPoint || !bottomPoint) {
            return null;
        }

        const top = Math.min(topPoint.y, bottomPoint.y);
        const bottom = Math.max(topPoint.y, bottomPoint.y);
        if (bottom - top <= 0.0001) {
            return null;
        }

        return {
            top: top,
            bottom: bottom,
        };
    }

    function normalizeLive2DFocusAxis(value, min, max) {
        const span = max - min;
        if (!Number.isFinite(span) || Math.abs(span) <= 0.0001) {
            return 0;
        }

        return clamp(((value - min) / span) * 2 - 1, -1, 1);
    }

    function applyLive2DFocusTarget(focusController, rawX, rawY) {
        const distance = Math.hypot(rawX, rawY);
        if (!Number.isFinite(distance) || distance <= 0.0001) {
            focusController.focus(0, 0);
            return;
        }

        focusController.focus(rawX / distance, -rawY / distance);
    }

    function attachLipSyncHook(model, live2dConfig) {
        detachLive2DLipSyncHook();

        const internalModel = model.internalModel;
        if (!internalModel || typeof internalModel.on !== "function") {
            return;
        }

        UI_STATE.lipSyncHook = function () {
            applyMouthValue(live2dConfig, UI_STATE.currentMouthValue);
        };
        internalModel.on("beforeModelUpdate", UI_STATE.lipSyncHook);
        UI_STATE.live2dInternalModel = internalModel;
    }

    function applyLive2DMouseFollowSetting() {
        const model = UI_STATE.live2dModel;
        if (!model) {
            return;
        }

        model.interactive = true;
        model.autoInteract = false;
        if (typeof model.unregisterInteraction === "function") {
            model.unregisterInteraction();
        }

        if (!UI_STATE.live2dMouseFollowEnabled) {
            unbindLive2DFocus();
            resetLive2DFocus();
            return;
        }

        bindLive2DFocus();
    }

    function resetLive2DFocus() {
        const internalModel = UI_STATE.live2dModel && UI_STATE.live2dModel.internalModel;
        if (
            !internalModel
            || !internalModel.focusController
            || typeof internalModel.focusController.focus !== "function"
        ) {
            return;
        }

        internalModel.focusController.focus(0, 0, true);
    }

    function detachLive2DLipSyncHook() {
        if (
            UI_STATE.live2dInternalModel
            && UI_STATE.lipSyncHook
            && typeof UI_STATE.live2dInternalModel.off === "function"
        ) {
            UI_STATE.live2dInternalModel.off("beforeModelUpdate", UI_STATE.lipSyncHook);
        }

        UI_STATE.live2dInternalModel = null;
        UI_STATE.lipSyncHook = null;
    }

    function disposeCurrentLive2DModel() {
        unbindLive2DDrag();
        unbindLive2DFocus();
        detachLive2DLipSyncHook();

        if (UI_STATE.live2dCharacterLayer) {
            UI_STATE.live2dCharacterLayer.removeChildren();
        } else if (UI_STATE.live2dStage) {
            UI_STATE.live2dStage.removeChildren();
        }

        if (UI_STATE.live2dModel) {
            destroyLive2DModel(UI_STATE.live2dModel);
        }

        UI_STATE.live2dModel = null;
        UI_STATE.dragging = false;
        UI_STATE.dragPointerId = null;
    }

    function destroyLive2DModel(model) {
        if (!model || typeof model.destroy !== "function") {
            return;
        }

        try {
            model.destroy({
                children: true,
            });
        } catch (error) {
            console.warn("Failed to destroy Live2D model", error);
        }
    }

    function handleStageWheel(event) {
        if (!UI_STATE.live2dModel) {
            return;
        }

        event.preventDefault();
        const scaleStep = event.deltaY < 0 ? 1.06 : 0.94;
        const nextScale = clamp(
            UI_STATE.live2dModel.scale.x * scaleStep,
            0.08,
            3.2,
        );
        UI_STATE.live2dModel.scale.set(nextScale);
        refreshLive2DFocusFromLastPointer();
        persistLive2DTransform();
    }

    function resetLive2DView() {
        const model = UI_STATE.live2dModel;
        if (!model || !UI_STATE.pixiApp) {
            return;
        }

        const savedTransform = loadSavedLive2DTransform();
        if (savedTransform) {
            model.position.set(savedTransform.x, savedTransform.y);
            model.scale.set(savedTransform.scale);
            refreshLive2DFocusFromLastPointer();
            return;
        }

        applyDefaultLive2DTransform(model);
        refreshLive2DFocusFromLastPointer();
        persistLive2DTransform();
    }

    function resetLive2DViewToDefault() {
        const model = UI_STATE.live2dModel;
        if (!model || !UI_STATE.pixiApp) {
            return;
        }

        clearSavedLive2DTransform();
        applyDefaultLive2DTransform(model);
        refreshLive2DFocusFromLastPointer();
        persistLive2DTransform();
    }

    function applyDefaultLive2DTransform(model) {
        const stageWidth = UI_STATE.pixiApp.screen.width;
        const stageHeight = UI_STATE.pixiApp.screen.height;
        const baseSize = measureLive2DBaseSize(model);
        const widthRatio = stageWidth / Math.max(baseSize.width, 1);
        const heightRatio = stageHeight / Math.max(baseSize.height, 1);
        const nextScale = Math.min(widthRatio, heightRatio) * 0.82;

        model.scale.set(nextScale);
        model.position.set(stageWidth * 0.5, stageHeight * 0.62);
    }

    function measureLive2DBaseSize(model) {
        if (typeof model.getLocalBounds === "function") {
            const bounds = model.getLocalBounds();
            if (bounds && bounds.width > 0 && bounds.height > 0) {
                return {
                    width: bounds.width,
                    height: bounds.height,
                };
            }
        }

        const scaleX = Math.max(Math.abs(model.scale.x) || 0, 0.0001);
        const scaleY = Math.max(Math.abs(model.scale.y) || 0, 0.0001);
        return {
            width: model.width / scaleX,
            height: model.height / scaleY,
        };
    }

    function persistLive2DTransform() {
        const model = UI_STATE.live2dModel;
        if (!model) {
            return;
        }

        const key = live2dStorageKey();
        const payload = {
            x: roundTo(model.x, 2),
            y: roundTo(model.y, 2),
            scale: roundTo(model.scale.x, 4),
        };
        window.localStorage.setItem(key, JSON.stringify(payload));
    }

    function loadSavedLive2DTransform() {
        try {
            const raw = window.localStorage.getItem(live2dStorageKey());
            if (!raw) {
                return null;
            }

            const payload = JSON.parse(raw);
            if (
                typeof payload.x === "number"
                && typeof payload.y === "number"
                && typeof payload.scale === "number"
            ) {
                return payload;
            }
        } catch (error) {
            console.warn("Failed to read saved Live2D transform", error);
        }
        return null;
    }

    function clearSavedLive2DTransform() {
        window.localStorage.removeItem(live2dStorageKey());
    }

    function live2dStorageKey() {
        const selectionKey = UI_STATE.config && UI_STATE.config.live2d
            ? (UI_STATE.config.live2d.selection_key || UI_STATE.config.live2d.model_url)
            : "default";
        return `echobot.web.live2d.${selectionKey}`;
    }

    function applyMouthValue(live2dConfig, value) {
        if (!live2dConfig || !UI_STATE.live2dModel || !UI_STATE.live2dModel.internalModel) {
            return;
        }

        const coreModel = UI_STATE.live2dModel.internalModel.coreModel;
        if (!coreModel || typeof coreModel.setParameterValueById !== "function") {
            return;
        }

        const lipSyncIds = (live2dConfig.lip_sync_parameter_ids || []).length > 0
            ? live2dConfig.lip_sync_parameter_ids
            : DEFAULT_LIP_SYNC_IDS;

        lipSyncIds.forEach((parameterId) => {
            try {
                coreModel.setParameterValueById(parameterId, value);
            } catch (error) {
                console.warn(`Failed to update lip sync parameter ${parameterId}`, error);
            }
        });

        if (live2dConfig.mouth_form_parameter_id) {
            try {
                coreModel.setParameterValueById(live2dConfig.mouth_form_parameter_id, 0);
            } catch (error) {
                console.warn("Failed to reset mouth form parameter", error);
            }
        }
    }

    return {
        applyConfigToUI: applyConfigToUI,
        handleLive2DDirectoryUpload: handleLive2DDirectoryUpload,
        handleLive2DModelChange: handleLive2DModelChange,
        handleMouseFollowToggle: handleMouseFollowToggle,
        handleStageBackgroundChange: handleStageBackgroundChange,
        handleStageBackgroundReset: handleStageBackgroundReset,
        handleStageBackgroundTransformInput: handleStageBackgroundTransformInput,
        handleStageBackgroundTransformReset: handleStageBackgroundTransformReset,
        handleStageBackgroundUpload: handleStageBackgroundUpload,
        handleStageEffectsInput: handleStageEffectsInput,
        handleStageEffectsReset: handleStageEffectsReset,
        initializePixiApplication: initializePixiApplication,
        loadLive2DModel: loadLive2DModel,
        setStageMessage: setStageMessage,
        applyLive2DMouseFollowSetting: applyLive2DMouseFollowSetting,
        resetLive2DViewToDefault: resetLive2DViewToDefault,
        handleStageWheel: handleStageWheel,
        applyMouthValue: applyMouthValue,
    };
}
