import {
    DEFAULT_SESSION_NAME,
    DOM,
    SESSION_SYNC_POLL_INTERVAL_MS,
    UI_STATE,
} from "./state.js";
import {
    messageContentEquals,
    messageContentToText,
    normalizeMessageContent,
} from "./content.js";

const ROUTE_MODE_VALUES = new Set(["auto", "chat_only", "force_agent"]);

export function createSessionsModule(deps) {
    const {
        addMessage,
        addSystemMessage,
        clearMessages,
        formatTimestamp,
        normalizeSessionName,
        requestJson,
        speakText,
        setRunStatus,
        stopSpeechPlayback,
    } = deps;

    let roleHooks = {
        closeRoleEditor() {},
        syncRolePanelForCurrentSession() {
            return Promise.resolve();
        },
    };

    function bindRoleHooks(hooks) {
        roleHooks = {
            ...roleHooks,
            ...(hooks || {}),
        };
    }

    function normalizeRouteMode(routeMode) {
        const value = String(routeMode || "").trim().toLowerCase();
        return ROUTE_MODE_VALUES.has(value) ? value : "auto";
    }

    function syncRouteModeSelect() {
        if (!DOM.routeModeSelect) {
            return;
        }
        DOM.routeModeSelect.value = normalizeRouteMode(UI_STATE.currentRouteMode);
    }

    async function initializeSessionPanel(defaultSessionName) {
        setSessionControlsBusy(true, "正在加载会话…");

        try {
            const sessionSummaries = await requestSessionSummaries();
            applySessionSummaries(sessionSummaries);

            const initialSessionName = resolveInitialSessionName(defaultSessionName, sessionSummaries);
            const sessionDetail = initialSessionName === defaultSessionName
                ? await requestJson("/api/sessions/current")
                : await requestJson("/api/sessions/current", {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ name: initialSessionName }),
                });

            applySessionDetail(sessionDetail);
            setSessionSidebarStatus("");
            startSessionSyncPolling();
        } finally {
            setSessionControlsBusy(false);
        }
    }

    function resolveInitialSessionName(defaultSessionName, sessionSummaries) {
        const storedSessionName = String(window.localStorage.getItem("echobot.web.session") || "").trim();
        const candidateNames = new Set((sessionSummaries || []).map((item) => item.name));

        if (storedSessionName && candidateNames.has(storedSessionName)) {
            return storedSessionName;
        }
        if (defaultSessionName && candidateNames.has(defaultSessionName)) {
            return defaultSessionName;
        }
        if (sessionSummaries && sessionSummaries.length > 0) {
            return sessionSummaries[0].name;
        }
        return defaultSessionName || DEFAULT_SESSION_NAME;
    }

    async function requestSessionSummaries() {
        const payload = await requestJson("/api/sessions");
        return Array.isArray(payload) ? payload : [];
    }

    async function requestSessionDetail(sessionName) {
        return await requestJson(`/api/sessions/${encodeURIComponent(sessionName)}`);
    }

    function applySessionSummaries(sessionSummaries) {
        UI_STATE.sessions = Array.isArray(sessionSummaries) ? sessionSummaries : [];
        renderSessionList(UI_STATE.sessions);
        updateSessionSidebarSummary();
    }

    async function refreshSessionList() {
        if (UI_STATE.sessionLoading) {
            return;
        }

        setSessionControlsBusy(true, "正在加载会话…");
        try {
            const sessionSummaries = await requestSessionSummaries();
            applySessionSummaries(sessionSummaries);
            setSessionSidebarStatus("");
        } catch (error) {
            console.error(error);
            setSessionSidebarStatus(error.message || "会话列表加载失败");
            addMessage("system", `会话列表加载失败：${error.message || error}`, "状态");
        } finally {
            setSessionControlsBusy(false);
        }
    }

    function startSessionSyncPolling() {
        if (UI_STATE.sessionSyncPollTimerId) {
            return;
        }

        UI_STATE.sessionSyncPollTimerId = window.setInterval(() => {
            void syncCurrentSessionFromServer({
                announceNewMessages: true,
                refreshSummaries: true,
            });
        }, SESSION_SYNC_POLL_INTERVAL_MS);
    }

    async function syncCurrentSessionFromServer(options = {}) {
        if (
            UI_STATE.sessionSyncInFlight
            || UI_STATE.sessionLoading
            || (
                !options.force
                && (UI_STATE.chatBusy || UI_STATE.activeChatJobId)
            )
        ) {
            return;
        }

        const sessionName = normalizeSessionName(
            options.sessionName || UI_STATE.currentSessionName || DEFAULT_SESSION_NAME,
        );
        UI_STATE.sessionSyncInFlight = true;
        try {
            const sessionDetail = await requestSessionDetail(sessionName);
            if (
                !options.force
                && sessionDetail.updated_at === UI_STATE.currentSessionUpdatedAt
            ) {
                return;
            }
            applySessionDetail(sessionDetail, {
                announceNewMessages: Boolean(options.announceNewMessages),
            });
            if (Boolean(options.refreshSummaries)) {
                applySessionSummaries(await requestSessionSummaries());
            }
        } catch (error) {
            console.error("Failed to sync session detail", error);
        } finally {
            UI_STATE.sessionSyncInFlight = false;
        }
    }

    function setSessionControlsBusy(isBusy, statusText = null) {
        UI_STATE.sessionLoading = isBusy;

        if (DOM.sessionCreateButton) {
            DOM.sessionCreateButton.disabled = isBusy || UI_STATE.chatBusy;
        }
        if (DOM.sessionRefreshButton) {
            DOM.sessionRefreshButton.disabled = isBusy || UI_STATE.chatBusy;
        }
        if (DOM.sessionSidebarClose) {
            DOM.sessionSidebarClose.disabled = isBusy;
        }
        if (DOM.routeModeSelect) {
            DOM.routeModeSelect.disabled = (
                isBusy
                || UI_STATE.chatBusy
                || Boolean(UI_STATE.activeChatJobId)
            );
        }

        renderSessionList(UI_STATE.sessions);
        if (typeof statusText === "string") {
            setSessionSidebarStatus(statusText);
        }
    }

    function setSessionSidebarStatus(text) {
        if (!DOM.sessionSidebarStatus) {
            return;
        }
        DOM.sessionSidebarStatus.textContent = String(text || "").trim();
    }

    function updateSessionSidebarSummary() {
        if (!DOM.sessionSidebarSummary) {
            return;
        }

        if (!UI_STATE.sessions || UI_STATE.sessions.length === 0) {
            DOM.sessionSidebarSummary.textContent = "暂无会话";
            return;
        }

        const currentSessionName = UI_STATE.currentSessionName || UI_STATE.sessions[0].name;
        DOM.sessionSidebarSummary.textContent = `共 ${UI_STATE.sessions.length} 个会话 · 当前会话：${currentSessionName}`;
    }

    function renderSessionList(sessionSummaries) {
        if (!DOM.sessionList) {
            return;
        }

        DOM.sessionList.innerHTML = "";
        if (!sessionSummaries || sessionSummaries.length === 0) {
            const empty = document.createElement("p");
            empty.className = "session-empty";
            empty.textContent = "当前还没有会话。";
            DOM.sessionList.appendChild(empty);
            return;
        }

        sessionSummaries.forEach((sessionSummary) => {
            DOM.sessionList.appendChild(buildSessionCard(sessionSummary));
        });
    }

    function buildSessionCard(sessionSummary) {
        const isActive = sessionSummary.name === UI_STATE.currentSessionName;
        const container = document.createElement("article");
        container.className = isActive ? "session-card session-card-active" : "session-card";

        const mainButton = document.createElement("button");
        mainButton.type = "button";
        mainButton.className = "session-card-main";
        mainButton.dataset.sessionAction = "switch";
        mainButton.dataset.sessionName = sessionSummary.name;
        mainButton.disabled = UI_STATE.chatBusy || UI_STATE.sessionLoading || isActive;

        const header = document.createElement("div");
        header.className = "session-card-header";

        const title = document.createElement("p");
        title.className = "session-card-title";
        title.textContent = sessionSummary.name;

        const count = document.createElement("span");
        count.className = "session-card-count";
        count.textContent = `${sessionSummary.message_count || 0} 条`;

        header.appendChild(title);
        header.appendChild(count);
        mainButton.appendChild(header);

        const meta = document.createElement("div");
        meta.className = "session-card-meta";
        meta.textContent = formatTimestamp(sessionSummary.updated_at) || "暂无更新时间";
        mainButton.appendChild(meta);

        const actions = document.createElement("div");
        actions.className = "session-card-actions";
        actions.appendChild(
            buildSessionActionButton("重命名", "rename", sessionSummary.name),
        );
        actions.appendChild(
            buildSessionActionButton("删除", "delete", sessionSummary.name, {
                danger: true,
            }),
        );

        container.appendChild(mainButton);
        container.appendChild(actions);
        return container;
    }

    function buildSessionActionButton(label, action, sessionName, options = {}) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = options.danger
            ? "session-card-action session-card-action-danger"
            : "session-card-action";
        button.textContent = label;
        button.dataset.sessionAction = action;
        button.dataset.sessionName = sessionName;
        button.disabled = UI_STATE.chatBusy || UI_STATE.sessionLoading;
        return button;
    }

    async function handleSessionListClick(event) {
        const actionButton = event.target.closest("[data-session-action]");
        if (!actionButton || !DOM.sessionList || !DOM.sessionList.contains(actionButton)) {
            return;
        }

        const action = actionButton.dataset.sessionAction || "";
        const sessionName = actionButton.dataset.sessionName || "";
        if (!sessionName) {
            return;
        }

        if (action === "switch") {
            await switchSession(sessionName);
            return;
        }
        if (action === "rename") {
            await handleRenameSession(sessionName);
            return;
        }
        if (action === "delete") {
            await handleDeleteSession(sessionName);
        }
    }

    async function switchSession(sessionName) {
        if (
            UI_STATE.chatBusy
            || UI_STATE.sessionLoading
            || !sessionName
            || sessionName === UI_STATE.currentSessionName
        ) {
            return;
        }

        stopSpeechPlayback();
        setSessionControlsBusy(true, "正在切换会话…");

        try {
            const sessionDetail = await requestJson("/api/sessions/current", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ name: sessionName }),
            });
            applySessionDetail(sessionDetail);
            setSessionSidebarStatus("");
            setRunStatus(`已切换到会话： ${sessionDetail.name}`);
        } catch (error) {
            console.error(error);
            setSessionSidebarStatus(error.message || "切换会话失败");
            addMessage("system", `切换会话失败：${error.message || error}`, "状态");
        } finally {
            setSessionControlsBusy(false);
        }
    }

    async function handleCreateSession() {
        if (UI_STATE.chatBusy || UI_STATE.sessionLoading) {
            return;
        }

        const rawName = window.prompt("输入新会话名，留空则自动生成：", "");
        if (rawName === null) {
            return;
        }

        let sessionName = "";
        const preferredRoleName = UI_STATE.currentRoleName || "default";
        const preferredRouteMode = normalizeRouteMode(UI_STATE.currentRouteMode);
        try {
            sessionName = rawName.trim() ? normalizeSessionName(rawName) : "";
        } catch (error) {
            setSessionSidebarStatus(error.message || "会话名不合法");
            addMessage("system", `新建会话失败：${error.message || error}`, "状态");
            return;
        }

        stopSpeechPlayback();
        setSessionControlsBusy(true, "正在创建会话…");

        try {
            let sessionDetail = await requestJson("/api/sessions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(sessionName ? { name: sessionName } : {}),
            });
            if (
                preferredRoleName
                && sessionDetail.role_name !== preferredRoleName
            ) {
                sessionDetail = await requestJson(
                    `/api/sessions/${encodeURIComponent(sessionDetail.name)}/role`,
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ role_name: preferredRoleName }),
                    },
                );
            }
            if (sessionDetail.route_mode !== preferredRouteMode) {
                sessionDetail = await requestJson(
                    `/api/sessions/${encodeURIComponent(sessionDetail.name)}/route-mode`,
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ route_mode: preferredRouteMode }),
                    },
                );
            }
            applySessionSummaries(await requestSessionSummaries());
            applySessionDetail(sessionDetail);
            setSessionSidebarStatus("");
            setRunStatus(`已新建会话：${sessionDetail.name}`);
        } catch (error) {
            console.error(error);
            setSessionSidebarStatus(error.message || "创建会话失败");
            addMessage("system", `创建会话失败：${error.message || error}`, "状态");
        } finally {
            setSessionControlsBusy(false);
        }
    }

    async function handleRenameSession(sessionName) {
        if (UI_STATE.chatBusy || UI_STATE.sessionLoading || !sessionName) {
            return;
        }

        const rawName = window.prompt("输入新的会话名：", sessionName);
        if (rawName === null) {
            return;
        }

        let nextSessionName = "";
        try {
            nextSessionName = normalizeSessionName(rawName);
        } catch (error) {
            setSessionSidebarStatus(error.message || "会话名不合法");
            addMessage("system", `重命名会话失败：${error.message || error}`, "状态");
            return;
        }

        if (nextSessionName === sessionName) {
            return;
        }

        setSessionControlsBusy(true, "正在重命名会话…");

        try {
            const sessionDetail = await requestJson(`/api/sessions/${encodeURIComponent(sessionName)}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ name: nextSessionName }),
            });
            applySessionSummaries(await requestSessionSummaries());
            applySessionDetail(sessionDetail);
            setSessionSidebarStatus("");
            setRunStatus(`会话已重命名为：${sessionDetail.name}`);
        } catch (error) {
            console.error(error);
            setSessionSidebarStatus(error.message || "重命名会话失败");
            addMessage("system", `重命名会话失败：${error.message || error}`, "状态");
        } finally {
            setSessionControlsBusy(false);
        }
    }

    async function handleDeleteSession(sessionName) {
        if (UI_STATE.chatBusy || UI_STATE.sessionLoading || !sessionName) {
            return;
        }
        if (!window.confirm(`确定删除会话“${sessionName}”吗？`)) {
            return;
        }

        stopSpeechPlayback();
        setSessionControlsBusy(true, "正在删除会话…");

        try {
            await requestJson(`/api/sessions/${encodeURIComponent(sessionName)}`, {
                method: "DELETE",
            });
            applySessionSummaries(await requestSessionSummaries());

            if (sessionName === UI_STATE.currentSessionName) {
                const sessionDetail = await requestJson("/api/sessions/current");
                applySessionDetail(sessionDetail);
                setRunStatus(`已删除会话：${sessionName}`);
            } else {
                renderSessionList(UI_STATE.sessions);
                updateSessionSidebarSummary();
                setRunStatus(`已删除会话：${sessionName}`);
            }

            setSessionSidebarStatus("");
        } catch (error) {
            console.error(error);
            setSessionSidebarStatus(error.message || "删除会话失败");
            addMessage("system", `删除会话失败：${error.message || error}`, "状态");
        } finally {
            setSessionControlsBusy(false);
        }
    }

    function applySessionDetail(sessionDetail, options = {}) {
        const sessionName = normalizeSessionName(sessionDetail.name || DEFAULT_SESSION_NAME);
        const nextHistory = normalizeHistory(sessionDetail.history);
        const appendedMessages = shouldAnnounceNewMessages(options, sessionName)
            ? findAppendedMessages(UI_STATE.currentSessionHistory, nextHistory)
            : [];
        roleHooks.closeRoleEditor();
        UI_STATE.currentSessionName = sessionName;
        UI_STATE.currentSessionUpdatedAt = String(sessionDetail.updated_at || "").trim();
        UI_STATE.currentSessionHistory = nextHistory;
        UI_STATE.currentRoleName = sessionDetail.role_name || "default";
        UI_STATE.currentRouteMode = normalizeRouteMode(sessionDetail.route_mode);

        DOM.sessionLabel.textContent = `会话: ${sessionName}`;
        window.localStorage.setItem("echobot.web.session", sessionName);
        syncRouteModeSelect();

        renderSessionHistory(nextHistory);
        renderSessionList(UI_STATE.sessions);
        updateSessionSidebarSummary();
        void roleHooks.syncRolePanelForCurrentSession();
        if (appendedMessages.length > 0) {
            void handleAppendedMessages(appendedMessages);
        }
    }

    function renderSessionHistory(history) {
        clearMessages();

        const messageHistory = normalizeHistory(history);
        if (messageHistory.length === 0) {
            addSystemMessage("当前会话还没有消息，开始聊吧。");
            return;
        }

        messageHistory.forEach((message) => {
            const renderedMessage = resolveHistoryMessage(message);
            addMessage(
                renderedMessage.kind,
                message.content,
                renderedMessage.label,
                renderedMessage.options,
            );
        });
    }

    function resolveHistoryMessage(message) {
        if (message.role === "user") {
            return {
                kind: "user",
                label: message.name || "你",
                options: { renderMode: "plain" },
            };
        }
        if (message.role === "assistant") {
            return {
                kind: "assistant",
                label: message.name || "Echo",
                options: {},
            };
        }
        if (message.role === "system") {
            return {
                kind: "system",
                label: message.name || "系统",
                options: { renderMode: "plain" },
            };
        }
        return {
            kind: "system",
            label: message.name || message.role || "记录",
            options: { renderMode: "plain" },
        };
    }

    function shouldAnnounceNewMessages(options, sessionName) {
        return Boolean(options && options.announceNewMessages)
            && UI_STATE.currentSessionName === sessionName
            && Array.isArray(UI_STATE.currentSessionHistory)
            && UI_STATE.currentSessionHistory.length > 0;
    }

    function normalizeHistory(history) {
        if (!Array.isArray(history)) {
            return [];
        }
        return history.map((message) => ({
            role: String((message && message.role) || ""),
            content: normalizeMessageContent(message && message.content),
            name: message && message.name ? String(message.name) : null,
            tool_call_id: message && message.tool_call_id ? String(message.tool_call_id) : null,
        }));
    }

    function findAppendedMessages(previousHistory, nextHistory) {
        if (!Array.isArray(previousHistory) || previousHistory.length === 0) {
            return [];
        }
        if (!Array.isArray(nextHistory) || nextHistory.length <= previousHistory.length) {
            return [];
        }

        for (let index = 0; index < previousHistory.length; index += 1) {
            if (!isSameHistoryMessage(previousHistory[index], nextHistory[index])) {
                return [];
            }
        }

        return nextHistory.slice(previousHistory.length);
    }

    function isSameHistoryMessage(left, right) {
        return (
            String((left && left.role) || "") === String((right && right.role) || "")
            && messageContentEquals(left && left.content, right && right.content)
            && String((left && left.name) || "") === String((right && right.name) || "")
            && String((left && left.tool_call_id) || "") === String((right && right.tool_call_id) || "")
        );
    }

    async function handleAppendedMessages(messages) {
        const assistantMessages = messages.filter((message) => message.role === "assistant");
        if (assistantMessages.length === 0) {
            return;
        }

        setRunStatus("收到新的会话消息");
        const spokenText = assistantMessages
            .map((message) => messageContentToText(message.content, { includeImageMarker: false }).trim())
            .filter(Boolean)
            .join("\n\n");
        if (!spokenText || !UI_STATE.ttsEnabled) {
            return;
        }

        try {
            await speakText(spokenText);
        } catch (error) {
            console.error("Failed to speak synced session messages", error);
        }
    }

    function routeModeLabel(routeMode) {
        if (routeMode === "chat_only") {
            return "纯聊天";
        }
        if (routeMode === "force_agent") {
            return "强制 Agent";
        }
        return "自动决策";
    }

    async function handleRouteModeChange() {
        if (
            !DOM.routeModeSelect
            || UI_STATE.chatBusy
            || UI_STATE.sessionLoading
            || UI_STATE.activeChatJobId
        ) {
            syncRouteModeSelect();
            return;
        }

        const nextRouteMode = normalizeRouteMode(DOM.routeModeSelect.value);
        const currentRouteMode = normalizeRouteMode(UI_STATE.currentRouteMode);
        if (nextRouteMode === currentRouteMode) {
            syncRouteModeSelect();
            return;
        }

        const sessionName = normalizeSessionName(
            UI_STATE.currentSessionName || DEFAULT_SESSION_NAME,
        );
        DOM.routeModeSelect.disabled = true;
        setRunStatus("正在切换路由模式...");

        try {
            const sessionDetail = await requestJson(
                `/api/sessions/${encodeURIComponent(sessionName)}/route-mode`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ route_mode: nextRouteMode }),
                },
            );
            applySessionDetail(sessionDetail);
            setRunStatus(`已切换路由模式：${routeModeLabel(nextRouteMode)}`);
        } catch (error) {
            console.error(error);
            syncRouteModeSelect();
            addMessage("system", `切换路由模式失败：${error.message || error}`, "状态");
            setRunStatus(error.message || "切换路由模式失败");
        } finally {
            DOM.routeModeSelect.disabled = (
                UI_STATE.chatBusy
                || UI_STATE.sessionLoading
                || Boolean(UI_STATE.activeChatJobId)
            );
        }
    }

    return {
        bindRoleHooks: bindRoleHooks,
        initializeSessionPanel: initializeSessionPanel,
        requestSessionSummaries: requestSessionSummaries,
        requestSessionDetail: requestSessionDetail,
        applySessionSummaries: applySessionSummaries,
        refreshSessionList: refreshSessionList,
        syncCurrentSessionFromServer: syncCurrentSessionFromServer,
        handleSessionListClick: handleSessionListClick,
        handleCreateSession: handleCreateSession,
        handleRouteModeChange: handleRouteModeChange,
        renderSessionList: renderSessionList,
        applySessionDetail: applySessionDetail,
    };
}
