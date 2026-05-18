// ── 步骤 1：组件选择校验 ──────────────────────────────────────

function validateSelect() {
    const errorDiv = document.getElementById("form-error");
    const checkboxes = document.querySelectorAll('input[name="components"]:checked');

    // 至少选择一个组件
    if (checkboxes.length === 0) {
        errorDiv.textContent = "请至少选择一个组件";
        errorDiv.style.display = "block";
        return false;
    }

    // 每个勾选的组件必须选择版本
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

let hostCount = 1;

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
        // 清空现有主机
        document.getElementById("host-list").innerHTML = "";
        hostCount = 1;

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
    input.value = "";  // 允许重复导入同一文件
}

function addHost() {
    const template = document.getElementById("host-template");
    const clone = template.content.cloneNode(true);
    const html = clone.firstElementChild.outerHTML.replace(/\{i\}/g, hostCount);
    document.getElementById("host-list").insertAdjacentHTML("beforeend", html);
    hostCount++;
}

// 页面加载初始化
document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("host-list")) {
        addHost();
    }
    // 触发所有组件的条件字段可见性
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
    const cards = document.querySelectorAll(".host-card");
    cards.forEach(card => {
        const idx = card.dataset.index;
        checkHost(idx);
    });
}

// ── 步骤 3：配置表单交互 ────────────────────────────────────

function toggleConfig(key) {
    const body = document.querySelector(`#config-${key} .config-body`);
    const legend = document.querySelector(`#config-${key} legend`);
    if (body) {
        const isHidden = body.style.display === "none";
        body.style.display = isHidden ? "block" : "none";
        if (legend) legend.classList.toggle("collapsed", !isHidden);
    }
}

function updateFieldVisibility(compKey) {
    const section = document.getElementById("config-" + compKey);
    if (!section) return;

    const mode = section.querySelector(`input[name="mode_${compKey}"]:checked`)?.value || "";

    section.querySelectorAll(".config-row[data-show-if]").forEach(row => {
        const field = row.dataset.showIf;
        const expected = row.dataset.showValue;
        // 查找触发字段的当前值（部署模式 / select / checkbox 等）
        const trigger = section.querySelector(`[name$="_${field}"]`) ||
                        section.querySelector(`input[name="mode_${compKey}"][value="${mode}"]`);
        let current = "";
        if (trigger) {
            if (trigger.type === "radio") {
                current = section.querySelector(`input[name="mode_${compKey}"]:checked`)?.value || "";
            } else if (trigger.type === "checkbox") {
                current = trigger.checked ? "yes" : "";
            } else {
                current = trigger.value;
            }
        }

        if (current === expected) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

function toggleHostSelect(compKey, mode) {
    const row = document.getElementById(`host-select-${compKey}`);
    if (!row) return;
    const checkboxes = row.querySelectorAll('input[type="radio"], input[type="checkbox"]');
    if (mode === "cluster") {
        // 集群模式：改为多选
        checkboxes.forEach(cb => { cb.type = "checkbox"; });
    } else {
        // 单机模式：改为单选
        checkboxes.forEach(cb => { cb.type = "radio"; });
    }
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

        if (data.type === "layer_start") {
            logOutput.insertAdjacentHTML("beforeend",
                `<div class="log-line play">=== ${data.layer} / ${data.item} ===</div>`);
        } else if (data.type === "log") {
            let cls = "";
            if (data.text.startsWith("ok:")) cls = "ok";
            else if (data.text.startsWith("changed:")) cls = "changed";
            else if (data.text.startsWith("TASK")) cls = "task";
            else if (data.text.startsWith("PLAY")) cls = "play";
            else if (data.text.startsWith("✓")) cls = "done";

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
