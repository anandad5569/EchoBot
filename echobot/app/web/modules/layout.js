import { CRON_POLL_INTERVAL_MS, DOM, UI_STATE } from "./state.js";

export function createLayoutModule(deps) {
    const {
        formatTimestamp,
        requestJson,
    } = deps;

    function ensureSidebarToggleButtons() {
        const sessionToggle = DOM.sessionSidebarToggle;
        if (!sessionToggle) {
            return;
        }

        let actions = sessionToggle.parentElement;
        if (!actions || !actions.classList.contains("panel-header-actions")) {
            actions = document.createElement("div");
            actions.className = "panel-header-actions";
            sessionToggle.insertAdjacentElement("afterend", actions);
            actions.appendChild(sessionToggle);
        }

        let roleToggle = DOM.roleSidebarToggle || document.getElementById("role-sidebar-toggle");
        if (!roleToggle) {
            roleToggle = document.createElement("button");
            roleToggle.id = "role-sidebar-toggle";
            roleToggle.type = "button";
            roleToggle.className = "ghost-button ghost-button-compact";
            roleToggle.textContent = "角色卡";
            actions.appendChild(roleToggle);
        }
        DOM.roleSidebarToggle = roleToggle;
    }

    function stopSummaryButtonToggle(event) {
        if (!event) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
    }

    function isSettingsPanelOpen() {
        return !DOM.settingsPanel || DOM.settingsPanel.open;
    }

    function restoreSettingsPanelState() {
        if (!DOM.settingsPanel) {
            return;
        }

        DOM.settingsPanel.open = window.localStorage.getItem("echobot.web.settings_panel_open") === "true";
    }

    function handleSettingsPanelToggle() {
        if (DOM.settingsPanel) {
            window.localStorage.setItem(
                "echobot.web.settings_panel_open",
                String(DOM.settingsPanel.open),
            );
        }
        handleCronPanelToggle();
        handleHeartbeatPanelToggle();
    }

    function restoreSessionSidebarState() {
        const isOpen = window.localStorage.getItem("echobot.web.session_sidebar_open") === "true";
        setSessionSidebarOpen(isOpen);
    }

    function restoreRoleSidebarState() {
        const isOpen = window.localStorage.getItem("echobot.web.role_sidebar_open") === "true";
        setRoleSidebarOpen(isOpen);
    }

    function setSessionSidebarOpen(isOpen, options = {}) {
        UI_STATE.sessionSidebarOpen = Boolean(isOpen);
        if (
            UI_STATE.sessionSidebarOpen
            && options.closeOther !== false
            && UI_STATE.roleSidebarOpen
        ) {
            setRoleSidebarOpen(false, { closeOther: false });
        }

        if (DOM.chatPanel) {
            DOM.chatPanel.classList.toggle("sessions-open", UI_STATE.sessionSidebarOpen);
        }
        if (DOM.sessionSidebar) {
            DOM.sessionSidebar.setAttribute("aria-hidden", String(!UI_STATE.sessionSidebarOpen));
        }
        if (DOM.sessionSidebarBackdrop) {
            DOM.sessionSidebarBackdrop.hidden = !UI_STATE.sessionSidebarOpen;
        }
        if (DOM.sessionSidebarToggle) {
            DOM.sessionSidebarToggle.textContent = UI_STATE.sessionSidebarOpen ? "隐藏会话" : "会话列表";
            DOM.sessionSidebarToggle.setAttribute("aria-expanded", String(UI_STATE.sessionSidebarOpen));
        }

        window.localStorage.setItem(
            "echobot.web.session_sidebar_open",
            String(UI_STATE.sessionSidebarOpen),
        );
    }

    function setRoleSidebarOpen(isOpen, options = {}) {
        UI_STATE.roleSidebarOpen = Boolean(isOpen);
        if (
            UI_STATE.roleSidebarOpen
            && options.closeOther !== false
            && UI_STATE.sessionSidebarOpen
        ) {
            setSessionSidebarOpen(false, { closeOther: false });
        }

        if (DOM.chatPanel) {
            DOM.chatPanel.classList.toggle("roles-open", UI_STATE.roleSidebarOpen);
        }
        if (DOM.roleSidebar) {
            DOM.roleSidebar.setAttribute("aria-hidden", String(!UI_STATE.roleSidebarOpen));
        }
        if (DOM.roleSidebarBackdrop) {
            DOM.roleSidebarBackdrop.hidden = !UI_STATE.roleSidebarOpen;
        }
        if (DOM.roleSidebarToggle) {
            DOM.roleSidebarToggle.textContent = UI_STATE.roleSidebarOpen ? "隐藏角色卡" : "角色卡";
            DOM.roleSidebarToggle.setAttribute("aria-expanded", String(UI_STATE.roleSidebarOpen));
        }

        window.localStorage.setItem(
            "echobot.web.role_sidebar_open",
            String(UI_STATE.roleSidebarOpen),
        );
    }

    function restoreCronPanelState() {
        if (!DOM.cronPanel) {
            return;
        }

        DOM.cronPanel.open = window.localStorage.getItem("echobot.web.cron_panel_open") === "true";
    }

    function restoreHeartbeatPanelState() {
        if (!DOM.heartbeatPanel) {
            return;
        }

        DOM.heartbeatPanel.open = window.localStorage.getItem("echobot.web.heartbeat_panel_open") === "true";
    }

    function restoreStageBackgroundPanelState() {
        if (!DOM.stageBackgroundPanel) {
            return;
        }

        const savedState = window.localStorage.getItem("echobot.web.stage_background_panel_open");
        DOM.stageBackgroundPanel.open = savedState === null ? true : savedState === "true";
    }

    function restoreLive2DPanelState() {
        if (!DOM.live2dPanel) {
            return;
        }

        const savedState = window.localStorage.getItem("echobot.web.live2d_panel_open");
        DOM.live2dPanel.open = savedState === null ? true : savedState === "true";
    }

    function restoreStageEffectsPanelState() {
        if (!DOM.stageEffectsPanel) {
            return;
        }

        const savedState = window.localStorage.getItem("echobot.web.stage_effects_panel_open");
        DOM.stageEffectsPanel.open = savedState === null ? true : savedState === "true";
    }

    function handleCronPanelToggle() {
        if (!DOM.cronPanel || !DOM.cronSummaryText) {
            return;
        }

        const isExpanded = DOM.cronPanel.open;
        const settingsPanelOpen = isSettingsPanelOpen();
        window.localStorage.setItem("echobot.web.cron_panel_open", String(isExpanded));

        if (!isExpanded || !settingsPanelOpen) {
            stopCronPolling();
            DOM.cronSummaryText.textContent = isExpanded ? "已展开" : "已隐藏";
            if (DOM.cronStatus) {
                DOM.cronStatus.textContent = settingsPanelOpen
                    ? "展开后加载 CRON 定时任务"
                    : "展开设置面板后查看 CRON 定时任务";
            }
            return;
        }

        DOM.cronSummaryText.textContent = "正在加载…";
        void refreshCronPanel();
        startCronPolling();
    }

    function handleStageEffectsPanelToggle() {
        if (!DOM.stageEffectsPanel) {
            return;
        }

        window.localStorage.setItem(
            "echobot.web.stage_effects_panel_open",
            String(DOM.stageEffectsPanel.open),
        );
    }

    function handleStageBackgroundPanelToggle() {
        if (!DOM.stageBackgroundPanel) {
            return;
        }

        window.localStorage.setItem(
            "echobot.web.stage_background_panel_open",
            String(DOM.stageBackgroundPanel.open),
        );
    }

    function handleLive2DPanelToggle() {
        if (!DOM.live2dPanel) {
            return;
        }

        window.localStorage.setItem(
            "echobot.web.live2d_panel_open",
            String(DOM.live2dPanel.open),
        );
    }

    function startCronPolling() {
        stopCronPolling();
        UI_STATE.cronPollTimerId = window.setInterval(() => {
            if (!DOM.cronPanel || !DOM.cronPanel.open || !isSettingsPanelOpen()) {
                return;
            }
            void refreshCronPanel();
        }, CRON_POLL_INTERVAL_MS);
    }

    function stopCronPolling() {
        if (!UI_STATE.cronPollTimerId) {
            return;
        }

        window.clearInterval(UI_STATE.cronPollTimerId);
        UI_STATE.cronPollTimerId = 0;
    }

    async function refreshCronPanel() {
        if (!DOM.cronPanel || !DOM.cronPanel.open || !isSettingsPanelOpen() || UI_STATE.cronLoading) {
            return;
        }

        UI_STATE.cronLoading = true;
        if (DOM.cronStatus) {
            DOM.cronStatus.textContent = "正在加载 CRON 定时任务…";
        }
        if (DOM.cronRefreshButton) {
            DOM.cronRefreshButton.disabled = true;
        }

        try {
            const [statusPayload, jobsPayload] = await Promise.all([
                requestJson("/api/cron/status"),
                requestJson("/api/cron/jobs?include_disabled=true"),
            ]);
            renderCronPanel(statusPayload, jobsPayload.jobs || []);
        } catch (error) {
            console.error(error);
            if (DOM.cronSummaryText) {
                DOM.cronSummaryText.textContent = "加载失败";
            }
            if (DOM.cronStatus) {
                DOM.cronStatus.textContent = error.message || "CRON 加载失败";
            }
        } finally {
            UI_STATE.cronLoading = false;
            if (DOM.cronRefreshButton) {
                DOM.cronRefreshButton.disabled = false;
            }
        }
    }

    function renderCronPanel(statusPayload, jobs) {
        if (DOM.cronSummaryText) {
            DOM.cronSummaryText.textContent = buildCronSummaryText(statusPayload, jobs);
        }
        if (DOM.cronStatus) {
            DOM.cronStatus.textContent = buildCronStatusText(statusPayload, jobs);
        }
        renderCronJobs(jobs);
    }

    function buildCronSummaryText(statusPayload, jobs) {
        if (!statusPayload.enabled) {
            return "调度器未运行";
        }
        if (!jobs || jobs.length === 0) {
            return "没有任务";
        }
        return `${jobs.length} 个任务`;
    }

    function buildCronStatusText(statusPayload, jobs) {
        const statusText = statusPayload.enabled ? "调度器运行中" : "调度器未运行";
        if (!jobs || jobs.length === 0) {
            return `${statusText} · 当前没有 CRON 定时任务`;
        }

        const nextRunText = formatTimestamp(statusPayload.next_run_at);
        if (!nextRunText) {
            return `${statusText} · 共 ${jobs.length} 个任务`;
        }
        return `${statusText} · 共 ${jobs.length} 个任务 · 下次执行 ${nextRunText}`;
    }

    function renderCronJobs(jobs) {
        if (!DOM.cronJobs) {
            return;
        }

        DOM.cronJobs.innerHTML = "";
        if (!jobs || jobs.length === 0) {
            const empty = document.createElement("p");
            empty.className = "cron-empty";
            empty.textContent = "当前没有 CRON 定时任务。";
            DOM.cronJobs.appendChild(empty);
            return;
        }

        jobs.forEach((job) => {
            DOM.cronJobs.appendChild(buildCronJobCard(job));
        });
    }

    function buildCronJobCard(job) {
        const container = document.createElement("article");
        container.className = "cron-job";

        const header = document.createElement("div");
        header.className = "cron-job-header";

        const title = document.createElement("h3");
        title.className = "cron-job-title";
        title.textContent = job.name || "未命名任务";

        const idText = document.createElement("span");
        idText.className = "cron-job-id";
        idText.textContent = `#${job.id || "-"}`;

        header.appendChild(title);
        header.appendChild(idText);

        const meta = document.createElement("div");
        meta.className = "cron-job-meta";
        meta.appendChild(buildCronBadge(job.enabled ? "已启用" : "已停用", job.enabled ? "enabled" : "disabled"));
        meta.appendChild(buildCronBadge(buildCronLastStatusLabel(job.last_status), cronStatusClassName(job.last_status)));
        meta.appendChild(buildCronMetaText(`计划: ${job.schedule || "-"}`));
        meta.appendChild(buildCronMetaText(`会话: ${job.session_name || "-"}`));
        meta.appendChild(buildCronMetaText(`类型: ${job.payload_kind || "-"}`));

        const times = document.createElement("div");
        times.className = "cron-job-times";
        times.appendChild(buildCronMetaText(`下次: ${formatTimestamp(job.next_run_at) || "—"}`));
        times.appendChild(buildCronMetaText(`上次: ${formatTimestamp(job.last_run_at) || "—"}`));

        container.appendChild(header);
        container.appendChild(meta);
        container.appendChild(times);

        if (job.last_error) {
            const error = document.createElement("div");
            error.className = "cron-job-error";
            error.textContent = `错误: ${job.last_error}`;
            container.appendChild(error);
        }

        return container;
    }

    function buildCronBadge(text, kind) {
        const badge = document.createElement("span");
        badge.className = `cron-badge cron-badge-${kind}`;
        badge.textContent = text;
        return badge;
    }

    function buildCronMetaText(text) {
        const item = document.createElement("span");
        item.textContent = text;
        return item;
    }

    function buildCronLastStatusLabel(status) {
        if (status === "ok") {
            return "最近成功";
        }
        if (status === "error") {
            return "最近失败";
        }
        if (status === "running") {
            return "运行中";
        }
        if (status === "skipped") {
            return "已跳过";
        }
        return "暂无状态";
    }

    function cronStatusClassName(status) {
        if (status === "ok") {
            return "ok";
        }
        if (status === "error") {
            return "error";
        }
        if (status === "running") {
            return "running";
        }
        return "idle";
    }

    function handleHeartbeatPanelToggle() {
        if (!DOM.heartbeatPanel || !DOM.heartbeatSummaryText) {
            return;
        }

        const isExpanded = DOM.heartbeatPanel.open;
        const settingsPanelOpen = isSettingsPanelOpen();
        window.localStorage.setItem("echobot.web.heartbeat_panel_open", String(isExpanded));

        if (!isExpanded) {
            DOM.heartbeatSummaryText.textContent = UI_STATE.heartbeatDirty
                ? "有未保存修改"
                : "已隐藏";
            renderHeartbeatState();
            return;
        }

        if (!settingsPanelOpen) {
            DOM.heartbeatSummaryText.textContent = UI_STATE.heartbeatDirty
                ? "有未保存修改"
                : "已展开";
            renderHeartbeatState();
            return;
        }

        if (UI_STATE.heartbeatLoaded || UI_STATE.heartbeatDirty) {
            renderHeartbeatState();
            return;
        }

        DOM.heartbeatSummaryText.textContent = "正在加载…";
        void refreshHeartbeatPanel();
    }

    async function refreshHeartbeatPanel(options = {}) {
        if (
            !DOM.heartbeatPanel
            || !DOM.heartbeatPanel.open
            || !isSettingsPanelOpen()
            || UI_STATE.heartbeatLoading
            || UI_STATE.heartbeatSaving
        ) {
            return;
        }
        if (!options.force && UI_STATE.heartbeatDirty) {
            renderHeartbeatState();
            return;
        }

        UI_STATE.heartbeatLoading = true;
        updateHeartbeatControls();
        if (DOM.heartbeatStatus) {
            DOM.heartbeatStatus.textContent = "正在加载 HEARTBEAT 周期任务…";
        }

        try {
            const payload = await requestJson("/api/heartbeat");
            renderHeartbeatPanel(payload);
        } catch (error) {
            console.error(error);
            if (DOM.heartbeatSummaryText) {
                DOM.heartbeatSummaryText.textContent = "加载失败";
            }
            if (DOM.heartbeatStatus) {
                DOM.heartbeatStatus.textContent = error.message || "HEARTBEAT 加载失败";
            }
        } finally {
            UI_STATE.heartbeatLoading = false;
            updateHeartbeatControls();
        }
    }

    async function saveHeartbeat() {
        if (!DOM.heartbeatInput || UI_STATE.heartbeatLoading || UI_STATE.heartbeatSaving) {
            return;
        }

        UI_STATE.heartbeatSaving = true;
        updateHeartbeatControls();
        if (DOM.heartbeatStatus) {
            DOM.heartbeatStatus.textContent = "正在保存 HEARTBEAT 周期任务…";
        }

        try {
            const payload = await requestJson("/api/heartbeat", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    content: DOM.heartbeatInput.value,
                }),
            });
            renderHeartbeatPanel(payload);
        } catch (error) {
            console.error(error);
            if (DOM.heartbeatSummaryText) {
                DOM.heartbeatSummaryText.textContent = "保存失败";
            }
            if (DOM.heartbeatStatus) {
                DOM.heartbeatStatus.textContent = error.message || "HEARTBEAT 保存失败";
            }
        } finally {
            UI_STATE.heartbeatSaving = false;
            updateHeartbeatControls();
        }
    }

    function handleHeartbeatInputChange() {
        if (!DOM.heartbeatInput) {
            return;
        }

        UI_STATE.heartbeatDirty = DOM.heartbeatInput.value !== UI_STATE.heartbeatSavedContent;
        renderHeartbeatState();
    }

    function renderHeartbeatPanel(payload) {
        UI_STATE.heartbeatData = payload || null;
        UI_STATE.heartbeatLoaded = true;
        UI_STATE.heartbeatSavedContent = String((payload && payload.content) || "");
        UI_STATE.heartbeatDirty = false;

        if (DOM.heartbeatInput) {
            DOM.heartbeatInput.value = UI_STATE.heartbeatSavedContent;
        }

        renderHeartbeatState();
    }

    function renderHeartbeatState() {
        const payload = UI_STATE.heartbeatData;

        if (DOM.heartbeatSummaryText) {
            DOM.heartbeatSummaryText.textContent = buildHeartbeatSummaryText(payload);
        }
        if (DOM.heartbeatStatus) {
            DOM.heartbeatStatus.textContent = buildHeartbeatStatusText(payload);
        }
        if (DOM.heartbeatMeta) {
            DOM.heartbeatMeta.textContent = buildHeartbeatMetaText(payload);
        }

        updateHeartbeatControls();
    }

    function buildHeartbeatSummaryText(payload) {
        const isExpanded = Boolean(DOM.heartbeatPanel && DOM.heartbeatPanel.open);
        const settingsPanelOpen = isSettingsPanelOpen();

        if (UI_STATE.heartbeatDirty) {
            return "有未保存修改";
        }
        if (!isExpanded) {
            return "已隐藏";
        }
        if (!settingsPanelOpen) {
            return "已展开";
        }
        if (!payload) {
            return "展开后加载";
        }
        if (!payload.enabled) {
            return payload.has_meaningful_content ? "已配置但未启用" : "未启用";
        }
        if (!payload.has_meaningful_content) {
            return "当前无有效任务";
        }
        return `每 ${payload.interval_seconds || 0} 秒检查`;
    }

    function buildHeartbeatStatusText(payload) {
        if (!isSettingsPanelOpen()) {
            return "展开设置面板后查看 HEARTBEAT 周期任务";
        }
        if (!payload) {
            return "展开后加载 HEARTBEAT 周期任务";
        }
        if (UI_STATE.heartbeatDirty) {
            return "内容已修改，保存后会更新 HEARTBEAT 周期任务";
        }

        const stateText = payload.enabled ? "HEARTBEAT 运行中" : "HEARTBEAT 未启用";
        const contentText = payload.has_meaningful_content
            ? "文件中有有效任务"
            : "文件中暂无有效任务";
        return `${stateText} · ${contentText}`;
    }

    function buildHeartbeatMetaText(payload) {
        if (!payload) {
            return "间隔会在加载后显示";
        }
        return `间隔 ${payload.interval_seconds || 0} 秒`;
    }

    function updateHeartbeatControls() {
        const isBusy = UI_STATE.heartbeatLoading || UI_STATE.heartbeatSaving;

        if (DOM.heartbeatInput) {
            DOM.heartbeatInput.disabled = isBusy;
        }
        if (DOM.heartbeatRefreshButton) {
            DOM.heartbeatRefreshButton.disabled = isBusy;
        }
        if (DOM.heartbeatSaveButton) {
            DOM.heartbeatSaveButton.disabled = isBusy || !UI_STATE.heartbeatDirty;
        }
    }

    return {
        ensureSidebarToggleButtons: ensureSidebarToggleButtons,
        stopSummaryButtonToggle: stopSummaryButtonToggle,
        restoreSettingsPanelState: restoreSettingsPanelState,
        handleSettingsPanelToggle: handleSettingsPanelToggle,
        restoreSessionSidebarState: restoreSessionSidebarState,
        restoreRoleSidebarState: restoreRoleSidebarState,
        setSessionSidebarOpen: setSessionSidebarOpen,
        setRoleSidebarOpen: setRoleSidebarOpen,
        restoreCronPanelState: restoreCronPanelState,
        restoreHeartbeatPanelState: restoreHeartbeatPanelState,
        restoreLive2DPanelState: restoreLive2DPanelState,
        restoreStageBackgroundPanelState: restoreStageBackgroundPanelState,
        restoreStageEffectsPanelState: restoreStageEffectsPanelState,
        handleCronPanelToggle: handleCronPanelToggle,
        handleLive2DPanelToggle: handleLive2DPanelToggle,
        handleStageBackgroundPanelToggle: handleStageBackgroundPanelToggle,
        handleStageEffectsPanelToggle: handleStageEffectsPanelToggle,
        handleHeartbeatPanelToggle: handleHeartbeatPanelToggle,
        refreshCronPanel: refreshCronPanel,
        refreshHeartbeatPanel: refreshHeartbeatPanel,
        saveHeartbeat: saveHeartbeat,
        handleHeartbeatInputChange: handleHeartbeatInputChange,
    };
}
