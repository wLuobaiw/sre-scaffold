// ── 步骤 1：组件选择校验 ──────────────────────────────────────

function validateSelect() {
    const errorDiv = document.getElementById("form-error");
    const checkboxes = document.querySelectorAll('input[name="components"]:checked');

    if (checkboxes.length === 0) {
        errorDiv.textContent = "请至少选择一个组件";
        errorDiv.style.display = "block";
        return false;
    }

    for (const cb of checkboxes) {
        const versionSelect = cb.closest(".comp-item-with-version")
            ?.querySelector(".version-select");
        if (versionSelect && !versionSelect.value) {
            errorDiv.textContent = `组件 "${cb.value}" 已勾选但未选择版本`;
            errorDiv.style.display = "block";
            versionSelect.focus();
            return false;
        }
    }

    errorDiv.style.display = "none";
    return true;
}


// ── 步骤 2：主机管理 ─────────────────────────────────────────

let hostCount = 0;

function downloadTemplate() {
    const content = "192.168.1.10|root|your_password|22\n192.168.1.11|root|your_password|22\n";
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hosts_template.txt";
    a.click();
    URL.revokeObjectURL(url);
}

function importHosts(input) {
    const file = input.files[0];
    if (!file) return;

    if (!confirm("导入将清空当前已配置的主机列表，是否继续？")) {
        input.value = "";
        return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
        document.getElementById("host-list").innerHTML = "";
        hostCount = 0;

        const lines = e.target.result.split(/\r?\n/);
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith("#")) continue;

            const parts = trimmed.split("|");
            if (parts.length < 3) continue;

            addHost();
            const idx = hostCount - 1;
            document.querySelector(`input[name="host_${idx}_ip"]`).value = parts[0].trim();
            document.querySelector(`input[name="host_${idx}_user"]`).value = parts[1].trim();
            document.querySelector(`input[name="host_${idx}_password"]`).value = parts[2].trim();
            if (parts.length >= 4) {
                document.querySelector(`input[name="host_${idx}_port"]`).value = parts[3].trim();
            }
        }
    };
    reader.readAsText(file);
    input.value = "";
}

function addHost() {
    const template = document.getElementById("host-template");
    const clone = template.content.cloneNode(true);
    const html = clone.firstElementChild.outerHTML.replace(/\{i\}/g, hostCount);
    document.getElementById("host-list").insertAdjacentHTML("beforeend", html);
    hostCount++;
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("host-list")) {
        const existingCards = document.querySelectorAll("#host-list .host-card");
        hostCount = existingCards.length > 0 ? existingCards.length : 0;
        if (hostCount === 0) addHost();
    }
    document.querySelectorAll(".config-section").forEach(section => {
        const id = section.id;
        if (id && id.startsWith("config-")) {
            updateFieldVisibility(id.replace("config-", ""));
        }
    });
});


// ── 主机连通性检测 ──────────────────────────────────────────

async function checkHost(index) {
    const ip = document.querySelector(`input[name="host_${index}_ip"]`)?.value;
    const user = document.querySelector(`input[name="host_${index}_user"]`)?.value || "root";
    const password = document.querySelector(`input[name="host_${index}_password"]`)?.value || "";
    const port = document.querySelector(`input[name="host_${index}_port"]`)?.value || "22";

    if (!ip) return;

    const resultDiv = document.getElementById(`check-result-${index}`);
    resultDiv.innerHTML = "检测中...";

    try {
        const resp = await fetch("/api/check-host", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip, ssh_user: user, ssh_password: password, ssh_port: port }),
        });
        const data = await resp.json();

        let html = "";
        for (const [name, check] of Object.entries(data.checks)) {
            const cls = check.status === "ok" ? "ok" : "fail";
            html += `<span class="${cls}">${name}: ${check.detail}</span><br>`;
        }
        resultDiv.innerHTML = html;
    } catch (e) {
        document.getElementById(`check-result-${index}`).innerHTML =
            '<span class="fail">检测失败</span>';
    }
}

function checkAllHosts() {
    document.querySelectorAll(".host-card").forEach(card => {
        checkHost(card.dataset.index);
    });
}


// ── 步骤 3：配置表单交互 ────────────────────────────────────

function toggleSection(btn, sectionId) {
    const body = document.getElementById("section-" + sectionId);
    if (!body) return;
    const isHidden = body.style.display === "none";
    body.style.display = isHidden ? "block" : "none";
    btn.textContent = isHidden ? "▾ " + btn.textContent.replace(/^[▸▾] /, "")
                               : "▸ " + btn.textContent.replace(/^[▸▾] /, "");
}

/**
 * 根据 show_when 条件控制字段/主机组可见性。
 * data-show-when-field 为空时不处理。
 */
function updateFieldVisibility(compKey) {
    const section = document.getElementById("config-" + compKey);
    if (!section) return;

    section.querySelectorAll("[data-show-when-field]").forEach(row => {
        const fieldName = row.dataset.showWhenField;
        const expectedVal = row.dataset.showWhenValue;
        if (!fieldName) return;

        // 查找触发器：可能是 var 输入或 hosts 输入
        const trigger = section.querySelector(
            `[name="var_${compKey}_${fieldName}"], [name="hosts_${compKey}_${fieldName}"]`
        );
        if (!trigger) return;

        let visible = false;
        if (trigger.type === "checkbox") {
            if (expectedVal === "true" || expectedVal === "True") {
                visible = trigger.checked;
            } else {
                visible = !trigger.checked;
            }
        } else {
            visible = String(trigger.value) === String(expectedVal);
        }

        row.style.display = visible ? "" : "none";
    });
}


// ── 步骤 4：部署执行 + 日志流 ──────────────────────────────

function startDeploy() {
    const btn = document.getElementById("btn-deploy");
    btn.disabled = true;
    btn.textContent = "⏳ 部署中...";

    const logOutput = document.getElementById("log-output");
    logOutput.innerHTML = "";
    logOutput.classList.remove("log-placeholder");

    const evtSource = new EventSource("/api/deploy/stream");

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);

        if (data.type === "status") {
            const statusEl = document.querySelector(`#status-${data.comp} .deploy-status`);
            if (statusEl) {
                statusEl.className = `deploy-status ${data.status}`;
                const labels = {download: "下载中...", installing: "安装中...", done: "已安装 ✓", error: "失败"};
                statusEl.textContent = labels[data.status] || data.status;
            }
        } else if (data.type === "log") {
            let cls = "";
            if (data.text.startsWith("ok:")) cls = "ok";
            else if (data.text.startsWith("changed:")) cls = "changed";
            else if (data.text.startsWith("TASK")) cls = "task";
            else if (data.text.startsWith("PLAY")) cls = "play";
            else if (data.text.startsWith("✓")) cls = "done";
            else if (data.text.startsWith("✗")) cls = "error";

            logOutput.insertAdjacentHTML("beforeend",
                `<div class="log-line ${cls}">${data.text}</div>`);
        } else if (data.type === "complete") {
            logOutput.insertAdjacentHTML("beforeend",
                '<div class="log-line done">── 部署完成 ──</div>');
            btn.textContent = "✓ 部署完成";
            btn.classList.remove("btn-danger");
            btn.classList.add("btn-primary");
            evtSource.close();
        }

        logOutput.scrollTop = logOutput.scrollHeight;
    };

    evtSource.onerror = function () {
        logOutput.insertAdjacentHTML("beforeend",
            '<div class="log-line error">日志连接中断</div>');
        evtSource.close();
    };
}
