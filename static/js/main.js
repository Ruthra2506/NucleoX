/* NucleoX - Client JavaScript Logic */

document.addEventListener('DOMContentLoaded', () => {
    initSplashScreen();
    initPcrMonitor();
    initStrPipeline();
    initChainVerifier();
});

/* --- 1. SPLASH SCREEN CONTROLLER --- */
function initSplashScreen() {
    const splash = document.getElementById('splash-screen');
    if (!splash) return;

    const hasSeenSplash = sessionStorage.getItem('nucleox_splash_shown');
    
    if (hasSeenSplash === 'true' && !splash.classList.contains('force-splash')) {
        splash.style.display = 'none';
    } else {
        sessionStorage.setItem('nucleox_splash_shown', 'true');
        setTimeout(() => {
            splash.classList.add('fade-out');
            setTimeout(() => {
                splash.style.display = 'none';
            }, 800);
        }, 1800);
    }
}

/* --- 2. LIVE PCR HARDWARE MONITORING & THERMAL CANVAS CHART --- */
let chartInterval = null;

function initPcrMonitor() {
    const deviceView = document.getElementById('device-monitor-view');
    if (!deviceView) return;

    const sampleSelect = document.getElementById('sample_select');
    const startPcrBtn = document.getElementById('start-pcr-btn');

    if (startPcrBtn) {
        startPcrBtn.addEventListener('click', async () => {
            const sampleId = sampleSelect ? sampleSelect.value : '';
            const portSelect = document.getElementById('port_select');
            const port = portSelect ? portSelect.value : 'COM3 (Simulated)';

            if (!sampleId) {
                alert('Please select a sample to start PCR thermal run.');
                return;
            }

            startPcrBtn.disabled = true;
            startPcrBtn.innerHTML = '<span class="status-dot"></span> Initiating PCR Thermal Cycle...';

            try {
                const resp = await fetch('/api/start_pcr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sample_ref_id: sampleId, port: port })
                });

                const res = await resp.json();
                if (res.success) {
                    startTelemetryPolling(sampleId);
                } else {
                    alert('Hardware Error: ' + res.message);
                    startPcrBtn.disabled = false;
                    startPcrBtn.innerHTML = '⚡ Start PCR Run';
                }
            } catch (err) {
                console.error('Failed to start PCR:', err);
                alert('Connection error starting PCR cycle.');
                startPcrBtn.disabled = false;
                startPcrBtn.innerHTML = '⚡ Start PCR Run';
            }
        });
    }

    if (sampleSelect && sampleSelect.value) {
        startTelemetryPolling(sampleSelect.value);
    }
}

function startTelemetryPolling(sampleId) {
    if (chartInterval) clearInterval(chartInterval);

    updateTelemetryData(sampleId);
    chartInterval = setInterval(() => {
        updateTelemetryData(sampleId);
    }, 1000);
}

async function updateTelemetryData(sampleId) {
    try {
        const resp = await fetch(`/api/pcr_data/${sampleId}`);
        const data = await resp.json();

        const latest = data.latest;
        const telemetry = data.telemetry || [];

        if (latest) {
            const tempVal = document.getElementById('metric-temp');
            const cycleVal = document.getElementById('metric-cycle');
            const progressVal = document.getElementById('metric-progress');
            const statusVal = document.getElementById('metric-status');
            const progressBar = document.getElementById('pcr-progress-fill');

            if (tempVal) tempVal.innerText = `${latest.temperature.toFixed(1)} °C`;
            if (cycleVal) cycleVal.innerText = `${latest.cycle_number} / 30`;
            if (progressVal) progressVal.innerText = `${latest.progress_percent.toFixed(1)}%`;
            if (statusVal) statusVal.innerText = latest.run_status;
            if (progressBar) progressBar.style.width = `${latest.progress_percent}%`;

            drawThermalChart(telemetry);

            if (latest.run_status.toLowerCase().includes('complete') || latest.cycle_number >= 30) {
                const btn = document.getElementById('start-pcr-btn');
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '✓ PCR Complete (Proceed to STR Profiling)';
                    btn.onclick = () => { window.location.href = `/profiles?sample_ref_id=${sampleId}`; };
                }
            }
        }
    } catch (err) {
        console.error('Error fetching PCR telemetry:', err);
    }
}

function drawThermalChart(telemetry) {
    const canvas = document.getElementById('thermalCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = canvas.parentElement.clientHeight;

    ctx.clearRect(0, 0, width, height);

    if (!telemetry || telemetry.length === 0) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Awaiting live thermal telemetry data from ESP32...', width / 2, height / 2);
        return;
    }

    // Grid lines
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.1)';
    ctx.lineWidth = 1;
    for (let y = 30; y < height; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    const minT = 20;
    const maxT = 100;
    const padding = 30;

    ctx.beginPath();
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 3;

    const stepX = (width - padding * 2) / Math.max(telemetry.length - 1, 1);

    telemetry.forEach((pt, idx) => {
        const x = padding + idx * stepX;
        const temp = Math.min(Math.max(pt.temperature, minT), maxT);
        const y = height - padding - ((temp - minT) / (maxT - minT)) * (height - padding * 2);

        if (idx === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();

    if (telemetry.length > 1) {
        const lastX = padding + (telemetry.length - 1) * stepX;
        ctx.lineTo(lastX, height - padding);
        ctx.lineTo(padding, height - padding);
        ctx.closePath();
        
        const grad = ctx.createLinearGradient(0, 0, 0, height);
        grad.addColorStop(0, 'rgba(6, 182, 212, 0.3)');
        grad.addColorStop(1, 'rgba(6, 182, 212, 0.0)');
        ctx.fillStyle = grad;
        ctx.fill();
    }
}

/* --- 3. 5-STAGE STR PROFILING PIPELINE ANIMATION --- */
function initStrPipeline() {
    const runBtn = document.getElementById('run-str-btn');
    if (!runBtn) return;

    runBtn.addEventListener('click', async () => {
        const sampleId = runBtn.getAttribute('data-sample-id');
        if (!sampleId) return;

        runBtn.disabled = true;
        runBtn.innerText = 'Executing 5-Stage STR Pipeline...';

        const stepItems = document.querySelectorAll('.pipeline-step-item');

        // Animate sequence step-by-step for live demonstration
        for (let i = 0; i < stepItems.length; i++) {
            const item = stepItems[i];
            const badge = item.querySelector('span:last-child');
            if (badge) {
                badge.style.color = 'var(--accent-amber)';
                badge.innerText = 'Processing...';
            }
            await new Promise(r => setTimeout(r, 400));
            if (badge) {
                badge.style.color = 'var(--accent-emerald)';
                badge.style.fontWeight = 'bold';
                badge.innerText = '✓ Complete';
            }
        }

        try {
            const resp = await fetch(`/api/run_str_pipeline/${sampleId}`, { method: 'POST' });
            const res = await resp.json();
            if (res.success) {
                window.location.href = `/profiles?sample_ref_id=${sampleId}`;
            } else {
                alert('Pipeline Error: ' + res.message);
                runBtn.disabled = false;
                runBtn.innerText = 'Execute 5-Stage STR Profiling Pipeline';
            }
        } catch (err) {
            console.error('STR Pipeline Execution Error:', err);
            runBtn.disabled = false;
            runBtn.innerText = 'Execute 5-Stage STR Profiling Pipeline';
        }
    });
}

/* --- 4. BLOCKCHAIN CHAIN INTEGRITY VERIFIER --- */
function initChainVerifier() {
    const verifyBtn = document.getElementById('verify-chain-btn');
    const resultBox = document.getElementById('verify-result-box');
    if (!verifyBtn || !resultBox) return;

    verifyBtn.addEventListener('click', async () => {
        verifyBtn.disabled = true;
        verifyBtn.innerHTML = '🔍 Computing Cryptographic Hashes...';

        try {
            const resp = await fetch('/api/verify_chain');
            const res = await resp.json();

            if (res.is_valid) {
                resultBox.style.background = 'rgba(16, 185, 129, 0.15)';
                resultBox.style.borderColor = 'rgba(16, 185, 129, 0.5)';
                resultBox.style.color = '#34d399';
                resultBox.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 0.6rem;">
                        <span style="font-size: 1.2rem;">✅</span>
                        <div>
                            <strong>Chain Integrity Verified!</strong><br>
                            <span>${res.message}</span>
                        </div>
                    </div>
                `;
            } else {
                resultBox.style.background = 'rgba(244, 63, 94, 0.18)';
                resultBox.style.borderColor = 'rgba(244, 63, 94, 0.6)';
                resultBox.style.color = '#fda4af';
                resultBox.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 0.6rem;">
                        <span style="font-size: 1.2rem;">🚨</span>
                        <div>
                            <strong>SECURITY ALERT — Chain Integrity Broken!</strong><br>
                            <span>${res.message}</span>
                        </div>
                    </div>
                `;
            }
        } catch (err) {
            console.error('Failed to verify chain:', err);
            alert('Verification request failed.');
        } finally {
            verifyBtn.disabled = false;
            verifyBtn.innerHTML = '🔍 Verify Chain Integrity';
        }
    });
}
