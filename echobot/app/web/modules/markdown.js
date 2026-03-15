export function buildMarkdownFragment(markdownText) {
    const fragment = document.createDocumentFragment();
    const normalizedText = String(markdownText || "").replace(/\r\n?/g, "\n");
    const lines = normalizedText.split("\n");
    let index = 0;

    while (index < lines.length) {
        const line = lines[index];

        if (!line.trim()) {
            index += 1;
            continue;
        }

        const fence = parseFenceStart(line);
        if (fence) {
            const codeBlock = collectCodeBlock(lines, index, fence);
            fragment.appendChild(
                createCodeBlockElement(codeBlock.content, codeBlock.language),
            );
            index = codeBlock.nextIndex;
            continue;
        }

        if (isHorizontalRuleLine(line)) {
            fragment.appendChild(document.createElement("hr"));
            index += 1;
            continue;
        }

        const headingMatch = line.match(/^\s*(#{1,6})\s+(.*)$/);
        if (headingMatch) {
            fragment.appendChild(
                createHeadingElement(headingMatch[1].length, headingMatch[2].trim()),
            );
            index += 1;
            continue;
        }

        if (isBlockquoteLine(line)) {
            const blockquote = collectBlockquote(lines, index);
            fragment.appendChild(createBlockquoteElement(blockquote.lines));
            index = blockquote.nextIndex;
            continue;
        }

        const listType = detectListType(line);
        if (listType) {
            const list = collectList(lines, index, listType);
            fragment.appendChild(list.element);
            index = list.nextIndex;
            continue;
        }

        const paragraph = collectParagraph(lines, index);
        fragment.appendChild(createParagraphElement(paragraph.lines));
        index = paragraph.nextIndex;
    }

    return fragment;
}

function parseFenceStart(line) {
    const match = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
    if (!match) {
        return null;
    }

    const language = match[2].trim().split(/\s+/)[0] || "";
    return {
        marker: match[1][0],
        length: match[1].length,
        language: language,
    };
}

function collectCodeBlock(lines, startIndex, fence) {
    const contentLines = [];
    let index = startIndex + 1;

    while (index < lines.length) {
        const closeMatch = lines[index].match(/^\s*(`{3,}|~{3,})\s*$/);
        if (
            closeMatch
            && closeMatch[1][0] === fence.marker
            && closeMatch[1].length >= fence.length
        ) {
            return {
                content: contentLines.join("\n"),
                language: fence.language,
                nextIndex: index + 1,
            };
        }

        contentLines.push(lines[index]);
        index += 1;
    }

    return {
        content: contentLines.join("\n"),
        language: fence.language,
        nextIndex: lines.length,
    };
}

function isHorizontalRuleLine(line) {
    return /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line);
}

function isBlockquoteLine(line) {
    return /^\s*>\s?/.test(line);
}

function collectBlockquote(lines, startIndex) {
    const quoteLines = [];
    let index = startIndex;

    while (index < lines.length && isBlockquoteLine(lines[index])) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
    }

    return {
        lines: quoteLines,
        nextIndex: index,
    };
}

function detectListType(line) {
    if (/^\s*[-*+]\s+/.test(line)) {
        return "unordered";
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
        return "ordered";
    }
    return "";
}

function collectList(lines, startIndex, listType) {
    const listElement = document.createElement(listType === "ordered" ? "ol" : "ul");
    let index = startIndex;

    while (index < lines.length) {
        const currentType = detectListType(lines[index]);
        if (currentType !== listType) {
            break;
        }

        const item = document.createElement("li");
        appendInlineMarkdown(item, stripListMarker(lines[index]));
        listElement.appendChild(item);
        index += 1;
    }

    return {
        element: listElement,
        nextIndex: index,
    };
}

function stripListMarker(line) {
    return line
        .replace(/^\s*[-*+]\s+/, "")
        .replace(/^\s*\d+[.)]\s+/, "")
        .trimEnd();
}

function collectParagraph(lines, startIndex) {
    const paragraphLines = [];
    let index = startIndex;

    while (index < lines.length) {
        const line = lines[index];
        if (!line.trim()) {
            break;
        }
        if (paragraphLines.length > 0 && isMarkdownBlockStart(line)) {
            break;
        }

        paragraphLines.push(line.trimEnd());
        index += 1;
    }

    return {
        lines: paragraphLines,
        nextIndex: index,
    };
}

function isMarkdownBlockStart(line) {
    return Boolean(
        parseFenceStart(line)
        || isHorizontalRuleLine(line)
        || /^\s*(#{1,6})\s+/.test(line)
        || isBlockquoteLine(line)
        || detectListType(line),
    );
}

function createHeadingElement(level, text) {
    const heading = document.createElement(`h${level}`);
    appendInlineMarkdown(heading, text);
    return heading;
}

function createParagraphElement(lines) {
    const paragraph = document.createElement("p");
    appendInlineLines(paragraph, lines);
    return paragraph;
}

function createBlockquoteElement(lines) {
    const blockquote = document.createElement("blockquote");
    const content = buildMarkdownFragment(lines.join("\n"));
    if (!content.childNodes.length) {
        const paragraph = document.createElement("p");
        paragraph.textContent = "";
        blockquote.appendChild(paragraph);
        return blockquote;
    }
    blockquote.appendChild(content);
    return blockquote;
}

function createCodeBlockElement(content, language) {
    const pre = document.createElement("pre");
    pre.className = "message-code-block";
    if (language) {
        pre.dataset.language = language;
    }

    const code = document.createElement("code");
    code.textContent = content;
    pre.appendChild(code);
    return pre;
}

function appendInlineLines(container, lines) {
    lines.forEach((line, lineIndex) => {
        if (lineIndex > 0) {
            container.appendChild(document.createElement("br"));
        }
        appendInlineMarkdown(container, line);
    });
}

function appendInlineMarkdown(container, text) {
    const source = String(text || "");
    let index = 0;

    while (index < source.length) {
        const linkToken = parseLinkToken(source, index);
        if (linkToken) {
            appendLinkToken(container, linkToken);
            index += linkToken.length;
            continue;
        }

        const codeToken = parseCodeSpanToken(source, index);
        if (codeToken) {
            const code = document.createElement("code");
            code.textContent = codeToken.content;
            container.appendChild(code);
            index += codeToken.length;
            continue;
        }

        const strongToken = parseWrappedToken(source, index, "**")
            || parseWrappedToken(source, index, "__");
        if (strongToken) {
            const strong = document.createElement("strong");
            appendInlineMarkdown(strong, strongToken.content);
            container.appendChild(strong);
            index += strongToken.length;
            continue;
        }

        const emphasisToken = parseWrappedToken(source, index, "*")
            || parseWrappedToken(source, index, "_");
        if (emphasisToken) {
            const emphasis = document.createElement("em");
            appendInlineMarkdown(emphasis, emphasisToken.content);
            container.appendChild(emphasis);
            index += emphasisToken.length;
            continue;
        }

        const nextSpecialIndex = findNextInlineSpecialIndex(source, index + 1);
        const sliceEnd = nextSpecialIndex === -1 ? source.length : nextSpecialIndex;
        container.appendChild(document.createTextNode(source.slice(index, sliceEnd)));
        index = sliceEnd;
    }
}

function parseLinkToken(text, index) {
    if (text[index] !== "[") {
        return null;
    }

    const labelEnd = text.indexOf("](", index);
    if (labelEnd === -1) {
        return null;
    }

    const urlEnd = text.indexOf(")", labelEnd + 2);
    if (urlEnd === -1) {
        return null;
    }

    const label = text.slice(index + 1, labelEnd);
    const url = text.slice(labelEnd + 2, urlEnd).trim();
    if (!label || !url) {
        return null;
    }

    return {
        label: label,
        url: url,
        raw: text.slice(index, urlEnd + 1),
        length: urlEnd + 1 - index,
    };
}

function appendLinkToken(container, token) {
    const safeUrl = normalizeLinkUrl(token.url);
    if (!safeUrl) {
        container.appendChild(document.createTextNode(token.raw));
        return;
    }

    const link = document.createElement("a");
    link.href = safeUrl;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    appendInlineMarkdown(link, token.label);
    container.appendChild(link);
}

function normalizeLinkUrl(url) {
    const trimmed = String(url || "").trim();
    if (!trimmed) {
        return "";
    }
    if (trimmed.startsWith("/") || trimmed.startsWith("#")) {
        return trimmed;
    }

    try {
        const parsed = new URL(trimmed, window.location.origin);
        if (
            parsed.protocol === "http:"
            || parsed.protocol === "https:"
            || parsed.protocol === "mailto:"
        ) {
            return parsed.href;
        }
    } catch (_error) {
        return "";
    }

    return "";
}

function parseCodeSpanToken(text, index) {
    if (text[index] !== "`") {
        return null;
    }

    const closingIndex = text.indexOf("`", index + 1);
    if (closingIndex <= index + 1) {
        return null;
    }

    return {
        content: text.slice(index + 1, closingIndex),
        length: closingIndex + 1 - index,
    };
}

function parseWrappedToken(text, index, delimiter) {
    if (!text.startsWith(delimiter, index)) {
        return null;
    }

    const contentStart = index + delimiter.length;
    const closingIndex = findClosingDelimiter(text, delimiter, contentStart);
    if (closingIndex <= contentStart) {
        return null;
    }

    return {
        content: text.slice(contentStart, closingIndex),
        length: closingIndex + delimiter.length - index,
    };
}

function findClosingDelimiter(text, delimiter, startIndex) {
    let searchIndex = startIndex;

    while (searchIndex < text.length) {
        const foundIndex = text.indexOf(delimiter, searchIndex);
        if (foundIndex === -1) {
            return -1;
        }

        if (delimiter.length === 1) {
            const previousChar = text[foundIndex - 1] || "";
            const nextChar = text[foundIndex + 1] || "";
            if (previousChar === delimiter || nextChar === delimiter) {
                searchIndex = foundIndex + 1;
                continue;
            }
        }

        return foundIndex;
    }

    return -1;
}

function findNextInlineSpecialIndex(text, startIndex) {
    for (let index = startIndex; index < text.length; index += 1) {
        const character = text[index];
        if (character === "[" || character === "`" || character === "*" || character === "_") {
            return index;
        }
    }
    return -1;
}
