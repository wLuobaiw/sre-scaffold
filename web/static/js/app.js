// ── 步骤 2：主机管理 ─────────────────────────────────────────

let hostCount = 1;

function addHost() {
    const template = document.getElementById("host-template");
    const clone = template.content.cloneNode(true);
    const html = clone.firstElementChild.outerHTML.replace(/\{i\}/g, hostCount);
    document.getElementById("host-list").insertAdjacentHTML("beforeend", html);
    hostCount++;
}

// 页面加载时默认添加一台主机
document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("host-list")) {
        addHost();
    }
    // 步骤 1：组件勾选联动版本选择
    document.querySelectorAll("input[data-has-version]").forEach(cb => {
        cb.addEventListener("change", function () {
            const select = this.closest(".comp-item-with-version")
                .querySelector(".version-select");
            select.disabled = !this.checked;
            if (!this.checked) select.value = "";
        });
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
