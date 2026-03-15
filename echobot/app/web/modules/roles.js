import {
    DEFAULT_SESSION_NAME,
    DOM,
    UI_STATE,
} from "./state.js";

export function createRolesModule(deps) {
    const {
        addMessage,
        normalizeSessionName,
        requestJson,
        setRunStatus,
    } = deps;

    let sessionHooks = {
        applySessionDetail() {},
    };

    function bindSessionHooks(hooks) {
        sessionHooks = {
            ...sessionHooks,
            ...(hooks || {}),
        };
    }

    async function initializeRolePanel() {
        await refreshRolePanel({ silent: true });
    }

    async function syncRolePanelForCurrentSession() {
        const roleSummaries = Array.isArray(UI_STATE.roles) ? UI_STATE.roles : [];
        const hasCurrentRole = roleSummaries.some(
            (item) => item && item.name === UI_STATE.currentRoleName,
        );

        if (hasCurrentRole) {
            renderRoleSelectOptions();
        } else if (!UI_STATE.roleLoading) {
            await refreshRoleList({ silent: true });
        }
        await refreshCurrentRoleCard({ silent: true });
    }

    async function refreshRolePanel(options = {}) {
        await refreshRoleList(options);
        await refreshCurrentRoleCard(options);
    }

    async function refreshRoleList(options = {}) {
        if (UI_STATE.roleLoading) {
            return;
        }

        setRoleControlsBusy(true, options.silent ? null : "正在加载角色卡…");
        try {
            const payload = await requestJson("/api/roles");
            UI_STATE.roles = Array.isArray(payload) ? payload : [];
            renderRoleSelectOptions();
            if (!options.silent) {
                setRoleStatus("");
            }
        } catch (error) {
            console.error(error);
            renderRoleSelectOptions();
            if (!options.silent) {
                setRoleStatus(error.message || "角色卡加载失败");
                addMessage("system", `角色卡加载失败：${error.message || error}`, "状态");
            }
        } finally {
            setRoleControlsBusy(false);
        }
    }

    async function refreshCurrentRoleCard(options = {}) {
        const roleName = UI_STATE.currentRoleName || "default";
        if (!roleName) {
            UI_STATE.currentRoleCard = null;
            renderCurrentRoleCard();
            return;
        }

        try {
            UI_STATE.currentRoleCard = await requestJson(
                `/api/roles/${encodeURIComponent(roleName)}`,
            );
        } catch (error) {
            console.error(error);
            UI_STATE.currentRoleCard = null;
            if (!options.silent) {
                setRoleStatus(error.message || "角色卡详情加载失败");
                addMessage("system", `角色卡详情加载失败：${error.message || error}`, "状态");
            }
        }

        renderCurrentRoleCard();
    }

    function renderRoleSelectOptions() {
        if (!DOM.roleSelect) {
            return;
        }

        DOM.roleSelect.innerHTML = "";
        const roleSummaries = Array.isArray(UI_STATE.roles) ? UI_STATE.roles : [];
        if (roleSummaries.length === 0) {
            const option = document.createElement("option");
            option.value = "default";
            option.textContent = "default";
            DOM.roleSelect.appendChild(option);
            DOM.roleSelect.disabled = true;
            return;
        }

        const availableNames = new Set(roleSummaries.map((item) => item.name));
        if (!availableNames.has(UI_STATE.currentRoleName)) {
            UI_STATE.currentRoleName = availableNames.has("default")
                ? "default"
                : roleSummaries[0].name;
        }

        roleSummaries.forEach((roleSummary) => {
            const option = document.createElement("option");
            option.value = roleSummary.name;
            option.textContent = buildRoleOptionLabel(roleSummary);
            DOM.roleSelect.appendChild(option);
        });
        DOM.roleSelect.value = UI_STATE.currentRoleName;
        updateRoleActionState();
    }

    function buildRoleOptionLabel(roleSummary) {
        const name = String((roleSummary && roleSummary.name) || "default");
        if (name === "default") {
            return `${name}（默认）`;
        }
        return name;
    }

    function renderCurrentRoleCard() {
        const roleCard = UI_STATE.currentRoleCard;

        if (DOM.rolePromptPreview) {
            DOM.rolePromptPreview.textContent = roleCard && roleCard.prompt
                ? roleCard.prompt
                : "暂无角色卡内容。";
        }

        if (DOM.roleStatus) {
            if (!roleCard) {
                DOM.roleStatus.textContent = "暂无角色卡详情。";
            } else if (!roleCard.editable) {
                DOM.roleStatus.textContent = `当前角色：${roleCard.name}（只读）`;
            } else {
                DOM.roleStatus.textContent = `当前角色：${roleCard.name}`;
            }
        }

        updateRoleActionState();
    }

    function setRoleControlsBusy(isBusy, statusText = null) {
        UI_STATE.roleLoading = isBusy;
        if (typeof statusText === "string") {
            setRoleStatus(statusText);
        }
        updateRoleActionState();
    }

    function setRoleStatus(text) {
        if (!DOM.roleStatus) {
            return;
        }
        DOM.roleStatus.textContent = String(text || "").trim();
    }

    function updateRoleActionState() {
        const roleCard = UI_STATE.currentRoleCard;
        const isBusy = UI_STATE.chatBusy || UI_STATE.roleLoading;
        const editorOpen = UI_STATE.roleEditorMode !== "closed";
        const controlsLocked = isBusy || editorOpen;

        if (DOM.roleSelect) {
            DOM.roleSelect.disabled = controlsLocked || !UI_STATE.roles || UI_STATE.roles.length === 0;
        }
        if (DOM.roleRefreshButton) {
            DOM.roleRefreshButton.disabled = controlsLocked;
        }
        if (DOM.roleNewButton) {
            DOM.roleNewButton.disabled = controlsLocked;
        }
        if (DOM.roleEditButton) {
            DOM.roleEditButton.disabled = controlsLocked || !roleCard || !roleCard.editable;
        }
        if (DOM.roleDeleteButton) {
            DOM.roleDeleteButton.disabled = controlsLocked || !roleCard || !roleCard.deletable;
        }
        if (DOM.roleSaveButton) {
            DOM.roleSaveButton.disabled = isBusy || !editorOpen;
        }
        if (DOM.roleCancelButton) {
            DOM.roleCancelButton.disabled = UI_STATE.roleLoading;
        }
        if (DOM.rolePreview) {
            DOM.rolePreview.hidden = editorOpen;
        }
        if (DOM.roleEditor) {
            DOM.roleEditor.hidden = !editorOpen;
        }
        if (DOM.roleNameInput) {
            DOM.roleNameInput.disabled = UI_STATE.roleLoading || UI_STATE.roleEditorMode !== "create";
            DOM.roleNameInput.readOnly = UI_STATE.roleEditorMode !== "create";
        }
        if (DOM.rolePromptInput) {
            DOM.rolePromptInput.disabled = UI_STATE.roleLoading || !editorOpen;
        }
    }

    async function handleRoleSelectionChange() {
        if (!DOM.roleSelect) {
            return;
        }

        const nextRoleName = String(DOM.roleSelect.value || "").trim();
        if (
            !nextRoleName
            || nextRoleName === UI_STATE.currentRoleName
            || UI_STATE.chatBusy
            || UI_STATE.roleLoading
        ) {
            renderRoleSelectOptions();
            return;
        }

        closeRoleEditor();
        setRoleControlsBusy(true, "正在切换角色卡…");
        try {
            await setCurrentSessionRole(nextRoleName, { silent: true });
            await refreshCurrentRoleCard({ silent: true });
            setRunStatus(`已切换角色卡：${UI_STATE.currentRoleName}`);
            setRoleStatus("");
        } catch (error) {
            console.error(error);
            renderRoleSelectOptions();
            setRoleStatus(error.message || "切换角色卡失败");
            addMessage("system", `切换角色卡失败：${error.message || error}`, "状态");
        } finally {
            setRoleControlsBusy(false);
        }
    }

    async function setCurrentSessionRole(roleName, options = {}) {
        const sessionName = normalizeSessionName(
            UI_STATE.currentSessionName || DEFAULT_SESSION_NAME,
        );
        const sessionDetail = await requestJson(
            `/api/sessions/${encodeURIComponent(sessionName)}/role`,
            {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ role_name: roleName }),
            },
        );
        sessionHooks.applySessionDetail(sessionDetail);
        if (!options.silent) {
            setRunStatus(`已切换角色卡：${sessionDetail.role_name || roleName}`);
        }
        return sessionDetail;
    }

    function openRoleEditor(mode) {
        if (!DOM.roleEditor || !DOM.roleNameInput || !DOM.rolePromptInput || !DOM.roleEditorTitle) {
            return;
        }

        if (mode === "edit" && (!UI_STATE.currentRoleCard || !UI_STATE.currentRoleCard.editable)) {
            return;
        }

        UI_STATE.roleEditorMode = mode;
        DOM.roleEditor.hidden = false;
        if (mode === "create") {
            DOM.roleEditorTitle.textContent = "新建角色卡";
            DOM.roleNameInput.value = "";
            DOM.rolePromptInput.value = "";
            DOM.roleNameInput.focus();
        } else {
            DOM.roleEditorTitle.textContent = `编辑角色卡：${UI_STATE.currentRoleCard.name}`;
            DOM.roleNameInput.value = UI_STATE.currentRoleCard.name || "";
            DOM.rolePromptInput.value = UI_STATE.currentRoleCard.prompt || "";
            DOM.rolePromptInput.focus();
        }
        updateRoleActionState();
    }

    function closeRoleEditor() {
        UI_STATE.roleEditorMode = "closed";
        if (DOM.roleEditor) {
            DOM.roleEditor.hidden = true;
        }
        if (DOM.roleNameInput) {
            DOM.roleNameInput.value = "";
        }
        if (DOM.rolePromptInput) {
            DOM.rolePromptInput.value = "";
        }
        if (DOM.roleEditorTitle) {
            DOM.roleEditorTitle.textContent = "角色卡编辑";
        }
        updateRoleActionState();
    }

    async function handleEditRoleClick() {
        if (!UI_STATE.currentRoleCard || !UI_STATE.currentRoleCard.editable) {
            return;
        }
        await refreshCurrentRoleCard({ silent: true });
        openRoleEditor("edit");
    }

    async function handleSaveRoleClick() {
        if (
            UI_STATE.chatBusy
            || UI_STATE.roleLoading
            || UI_STATE.roleEditorMode === "closed"
        ) {
            return;
        }

        const roleName = DOM.roleNameInput ? DOM.roleNameInput.value.trim() : "";
        const prompt = DOM.rolePromptInput ? DOM.rolePromptInput.value.trim() : "";
        const isCreateMode = UI_STATE.roleEditorMode === "create";
        let shouldRefreshRoleList = false;
        if (!prompt) {
            setRoleStatus("角色卡内容不能为空。");
            return;
        }
        if (isCreateMode && !roleName) {
            setRoleStatus("角色名不能为空。");
            return;
        }

        setRoleControlsBusy(
            true,
            isCreateMode ? "正在创建角色卡…" : "正在保存角色卡…",
        );
        try {
            let roleDetail;
            if (isCreateMode) {
                roleDetail = await requestJson("/api/roles", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        name: roleName,
                        prompt: prompt,
                    }),
                });
                await setCurrentSessionRole(roleDetail.name, { silent: true });
                shouldRefreshRoleList = true;
            } else {
                roleDetail = await requestJson(
                    `/api/roles/${encodeURIComponent(UI_STATE.currentRoleName)}`,
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            prompt: prompt,
                        }),
                    },
                );
            }

            UI_STATE.currentRoleName = roleDetail.name || UI_STATE.currentRoleName;
            UI_STATE.currentRoleCard = roleDetail;
            renderCurrentRoleCard();
            closeRoleEditor();
            await refreshCurrentRoleCard({ silent: true });
            setRoleStatus("");
            setRunStatus(
                isCreateMode
                    ? `已创建角色卡：${roleDetail.name}`
                    : `已保存角色卡：${roleDetail.name}`,
            );
        } catch (error) {
            console.error(error);
            setRoleStatus(error.message || "保存角色卡失败");
            addMessage("system", `保存角色卡失败：${error.message || error}`, "状态");
        } finally {
            setRoleControlsBusy(false);
        }

        if (shouldRefreshRoleList) {
            await refreshRoleList({ silent: true });
        }
    }

    async function handleDeleteRoleClick() {
        const roleCard = UI_STATE.currentRoleCard;
        if (
            !roleCard
            || !roleCard.deletable
            || UI_STATE.chatBusy
            || UI_STATE.roleLoading
        ) {
            return;
        }
        if (!window.confirm(`确定删除角色卡“${roleCard.name}”吗？`)) {
            return;
        }

        let shouldRefreshRoleList = false;
        setRoleControlsBusy(true, "正在删除角色卡…");
        try {
            await requestJson(`/api/roles/${encodeURIComponent(roleCard.name)}`, {
                method: "DELETE",
            });
            shouldRefreshRoleList = true;
            closeRoleEditor();
            const sessionDetail = await requestJson("/api/sessions/current");
            sessionHooks.applySessionDetail(sessionDetail);
            await refreshCurrentRoleCard({ silent: true });
            setRoleStatus("");
            setRunStatus(`已删除角色卡：${roleCard.name}`);
        } catch (error) {
            console.error(error);
            setRoleStatus(error.message || "删除角色卡失败");
            addMessage("system", `删除角色卡失败：${error.message || error}`, "状态");
        } finally {
            setRoleControlsBusy(false);
        }

        if (shouldRefreshRoleList) {
            await refreshRoleList({ silent: true });
        }
    }

    return {
        bindSessionHooks: bindSessionHooks,
        initializeRolePanel: initializeRolePanel,
        syncRolePanelForCurrentSession: syncRolePanelForCurrentSession,
        refreshRolePanel: refreshRolePanel,
        handleRoleSelectionChange: handleRoleSelectionChange,
        handleEditRoleClick: handleEditRoleClick,
        handleSaveRoleClick: handleSaveRoleClick,
        handleDeleteRoleClick: handleDeleteRoleClick,
        openRoleEditor: openRoleEditor,
        closeRoleEditor: closeRoleEditor,
        updateRoleActionState: updateRoleActionState,
    };
}
