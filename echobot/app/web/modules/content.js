export const TEXT_CONTENT_BLOCK_TYPE = "text";
export const IMAGE_URL_CONTENT_BLOCK_TYPE = "image_url";

export function buildUserMessageContent(text, imageUrls = []) {
    const cleanedText = String(text || "").trim();
    const cleanedImageUrls = imageUrls
        .map((url) => String(url || "").trim())
        .filter(Boolean);

    if (cleanedImageUrls.length === 0) {
        return cleanedText;
    }

    const blocks = [];
    if (cleanedText) {
        blocks.push({
            type: TEXT_CONTENT_BLOCK_TYPE,
            text: cleanedText,
        });
    }

    cleanedImageUrls.forEach((imageUrl) => {
        blocks.push({
            type: IMAGE_URL_CONTENT_BLOCK_TYPE,
            image_url: {
                url: imageUrl,
            },
        });
    });
    return blocks;
}

export function normalizeMessageContent(content) {
    if (!Array.isArray(content)) {
        return String(content ?? "");
    }

    return content
        .filter((block) => block && typeof block === "object" && !Array.isArray(block))
        .map((block) => {
            const nextBlock = { ...block };
            if (block.image_url && typeof block.image_url === "object") {
                nextBlock.image_url = { ...block.image_url };
            }
            return nextBlock;
        });
}

export function messageContentImageUrls(content) {
    const normalized = normalizeMessageContent(content);
    if (!Array.isArray(normalized)) {
        return [];
    }

    return normalized
        .filter((block) => String(block.type || "").trim() === IMAGE_URL_CONTENT_BLOCK_TYPE)
        .map((block) => String(block.image_url?.url || "").trim())
        .filter(Boolean);
}

export function messageContentToText(content, options = {}) {
    const normalized = normalizeMessageContent(content);
    const includeImageMarker = options.includeImageMarker !== false;

    if (!Array.isArray(normalized)) {
        return normalized;
    }

    const parts = [];
    normalized.forEach((block) => {
        const blockType = String(block.type || "").trim();
        if (blockType === TEXT_CONTENT_BLOCK_TYPE) {
            const text = String(block.text || "").trim();
            if (text) {
                parts.push(text);
            }
            return;
        }
        if (blockType === IMAGE_URL_CONTENT_BLOCK_TYPE) {
            if (includeImageMarker) {
                parts.push("[image]");
            }
            return;
        }
        if (blockType) {
            parts.push(`[${blockType}]`);
        }
    });

    return parts.join("\n\n");
}

export function messageContentEquals(left, right) {
    return JSON.stringify(normalizeMessageContent(left)) === JSON.stringify(normalizeMessageContent(right));
}

export function hasMessageContent(content) {
    const text = messageContentToText(content, { includeImageMarker: false }).trim();
    return Boolean(text) || messageContentImageUrls(content).length > 0;
}
