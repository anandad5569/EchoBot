export const DEFAULT_STAGE_BACKGROUND_TRANSFORM = Object.freeze({
    positionX: 50,
    positionY: 50,
    scale: 100,
});

export const DEFAULT_STAGE_LIGHT_POSITION = Object.freeze({
    x: 0,
    y: 0,
});

export const DEFAULT_STAGE_RIM_LIGHT_POSITION = Object.freeze({
    x: 0.76,
    y: 0.42,
});

export const STAGE_EFFECTS_STORAGE_KEY = "echobot.web.stage.effects.v3";
export const STAGE_BACKGROUND_STORAGE_KEY = "echobot.web.stage.background";
export const LIVE2D_SELECTION_STORAGE_KEY = "echobot.web.live2d.selection";
export const LIVE2D_HOTKEYS_STORAGE_KEY = "echobot.web.live2d.hotkeys_enabled";
export const LIVE2D_MOUSE_FOLLOW_STORAGE_KEY = "echobot.web.live2d.mouse_follow";
export const STAGE_PARTICLE_COUNT = 96;

export const DEFAULT_STAGE_EFFECT_SETTINGS = Object.freeze({
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

export const ATMOSPHERE_FILTER_FRAGMENT = `
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
