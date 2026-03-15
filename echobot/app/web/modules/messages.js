import { DOM, UI_STATE } from "./state.js";
import {
    IMAGE_URL_CONTENT_BLOCK_TYPE,
    TEXT_CONTENT_BLOCK_TYPE,
    normalizeMessageContent,
} from "./content.js";
import { buildMarkdownFragment } from "./markdown.js";

let pendingScrollFrameId = 0;

export function addMessage(kind, content, label, options = {}) {
    const messageId = `msg-${++UI_STATE.messageCounter}`;
    const container = document.createElement("article");
    container.className = `message message-${kind}`;
    container.dataset.messageId = messageId;
    container.dataset.messageKind = kind;
    container.setAttribute("role", kind === "system" ? "status" : "group");
    container.setAttribute("aria-label", resolveMessageAriaLabel(kind, label));
    if (kind === "system") {
        container.setAttribute("aria-live", "polite");
    }

    const body = document.createElement("div");
    body.className = "message-text";
    renderMessageBody(body, kind, content, options);

    container.appendChild(body);
    syncMessageMeta(container, label, options);
    DOM.messages.appendChild(container);
    scheduleMessagesScrollToBottom();
    return messageId;
}

export function addSystemMessage(text) {
    addMessage("system", text, "Status");
}

export function updateMessage(messageId, content, label, options = {}) {
    const container = DOM.messages.querySelector(`[data-message-id="${messageId}"]`);
    if (!container) {
        return;
    }

    const body = container.querySelector(".message-text");
    const kind = container.dataset.messageKind || "assistant";
    container.setAttribute("aria-label", resolveMessageAriaLabel(kind, label));
    syncMessageMeta(container, label, options);
    if (body) {
        renderMessageBody(body, kind, content, options);
    }
    scheduleMessagesScrollToBottom();
}

export function clearMessages() {
    DOM.messages.innerHTML = "";
    UI_STATE.messageCounter = 0;
}

export function scheduleMessagesScrollToBottom() {
    if (!DOM.messages || pendingScrollFrameId) {
        return;
    }

    pendingScrollFrameId = window.requestAnimationFrame(() => {
        pendingScrollFrameId = 0;
        scrollMessagesToBottom();
    });
}

export function removeMessage(messageId) {
    const container = DOM.messages.querySelector(`[data-message-id="${messageId}"]`);
    if (!container) {
        return;
    }
    container.remove();
}

export function initializeMessageInteractions() {
    if (DOM.messages) {
        DOM.messages.addEventListener("click", handleMessageAreaClick);
    }
    if (DOM.messageImageDialogClose) {
        DOM.messageImageDialogClose.addEventListener("click", closeMessageImagePreview);
    }
    if (DOM.messageImageDialog) {
        DOM.messageImageDialog.addEventListener("click", handleMessageImageDialogClick);
        DOM.messageImageDialog.addEventListener("close", resetMessageImagePreview);
        DOM.messageImageDialog.addEventListener("cancel", () => {
            resetMessageImagePreview();
        });
    }
}

function syncMessageMeta(container, label, options = {}) {
    const existingMeta = container.querySelector(".message-meta");
    const body = container.querySelector(".message-text");

    if (!options.showMeta) {
        if (existingMeta) {
            existingMeta.remove();
        }
        return;
    }

    const meta = existingMeta || document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = String(label || "");

    if (!existingMeta) {
        if (body) {
            container.insertBefore(meta, body);
        } else {
            container.appendChild(meta);
        }
    }
}

function scrollMessagesToBottom() {
    if (!DOM.messages) {
        return;
    }

    DOM.messages.scrollTop = DOM.messages.scrollHeight;
}

function resolveMessageAriaLabel(kind, label) {
    const customLabel = String(label || "").trim();
    if (customLabel) {
        return customLabel;
    }

    if (kind === "user") {
        return "Your message";
    }
    if (kind === "assistant") {
        return "Echo reply";
    }
    if (kind === "system") {
        return "Status";
    }
    return "Message";
}

function renderMessageBody(element, kind, content, options = {}) {
    const normalizedContent = normalizeMessageContent(content);
    if (Array.isArray(normalizedContent)) {
        renderStructuredBody(element, kind, normalizedContent, options);
        return;
    }

    const renderMode = resolveMessageRenderMode(kind, options);
    if (renderMode === "markdown") {
        renderMarkdownBody(element, normalizedContent);
        return;
    }
    renderPlainTextBody(element, normalizedContent);
}

function resolveMessageRenderMode(kind, options) {
    if (options.renderMode === "markdown") {
        return "markdown";
    }
    if (options.renderMode === "plain") {
        return "plain";
    }
    return kind === "assistant" ? "markdown" : "plain";
}

function renderPlainTextBody(element, text) {
    element.className = "message-text message-text-plain";
    element.textContent = String(text || "");
}

function renderMarkdownBody(element, text) {
    element.className = "message-text message-text-markdown";
    element.replaceChildren(buildMarkdownFragment(String(text || "")));
}

function renderStructuredBody(element, kind, contentBlocks, options) {
    const renderMode = resolveMessageRenderMode(kind, options);
    const fragment = document.createDocumentFragment();

    contentBlocks.forEach((block) => {
        const blockType = String(block.type || "").trim();
        if (blockType === TEXT_CONTENT_BLOCK_TYPE) {
            fragment.appendChild(
                buildTextBlock(
                    String(block.text || ""),
                    renderMode,
                ),
            );
            return;
        }

        if (blockType === IMAGE_URL_CONTENT_BLOCK_TYPE) {
            const imageUrl = String(block.image_url?.url || "").trim();
            if (imageUrl) {
                fragment.appendChild(buildImageBlock(imageUrl));
            }
            return;
        }

        if (blockType) {
            fragment.appendChild(buildTextBlock(`[${blockType}]`, "plain"));
        }
    });

    element.className = "message-text message-text-structured";
    if (!fragment.childNodes.length) {
        element.textContent = "";
        return;
    }
    element.replaceChildren(fragment);
}

function buildTextBlock(text, renderMode) {
    const block = document.createElement("div");
    block.className = "message-block message-block-text";
    if (renderMode === "markdown") {
        block.classList.add("message-text-markdown");
        block.replaceChildren(buildMarkdownFragment(String(text || "")));
        return block;
    }

    block.classList.add("message-text-plain");
    block.textContent = String(text || "");
    return block;
}

function buildImageBlock(imageUrl) {
    const block = document.createElement("div");
    block.className = "message-block message-block-image";

    const previewButton = document.createElement("button");
    previewButton.type = "button";
    previewButton.className = "message-image-link";
    previewButton.dataset.imagePreview = "true";
    previewButton.dataset.imageUrl = imageUrl;
    previewButton.title = "点击预览图片";
    previewButton.setAttribute("aria-label", "预览图片");

    const image = document.createElement("img");
    image.className = "message-image";
    image.src = imageUrl;
    image.alt = "Attached image";
    image.loading = "lazy";

    previewButton.appendChild(image);
    block.appendChild(previewButton);
    return block;
}

function handleMessageAreaClick(event) {
    const previewTrigger = event.target.closest(".message-image-link[data-image-preview='true']");
    if (!previewTrigger || !DOM.messageImageDialog) {
        return;
    }

    const imageUrl = String(previewTrigger.dataset.imageUrl || "").trim();
    if (!imageUrl) {
        return;
    }

    openMessageImagePreview(imageUrl);
}

function openMessageImagePreview(imageUrl) {
    if (!DOM.messageImageDialog || !DOM.messageImageDialogImage) {
        return;
    }

    DOM.messageImageDialogImage.src = imageUrl;

    if (!DOM.messageImageDialog.open) {
        DOM.messageImageDialog.showModal();
    }
}

function closeMessageImagePreview() {
    if (DOM.messageImageDialog?.open) {
        DOM.messageImageDialog.close();
    }
}

function handleMessageImageDialogClick(event) {
    if (event.target === DOM.messageImageDialog) {
        closeMessageImagePreview();
    }
}

function resetMessageImagePreview() {
    if (DOM.messageImageDialogImage) {
        DOM.messageImageDialogImage.removeAttribute("src");
    }
}
