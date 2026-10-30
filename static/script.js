/**
 * RoboFlow – Stochastic Warehouse Robot Task Allocation
 * Frontend Control, 2D Floorplan Animation & Real-time Charting
 */

document.addEventListener("DOMContentLoaded", () => {
    // =========================================================================
    // STATE & VARIABLES
    // =========================================================================
    let warehouseConfig = null;
    let initialRobots = [];
    let initialTasks = [];
    
    // Simulation playback state
    let simData = null;
    let animFrameId = null;
    let isPlaying = false;
    let playbackSpeed = 1.0;
    let currentTime = 0.0;
    let maxSimTime = 0.0;
    let lastTimestamp = 0;
    let currentSeed = 42;

    // Chart instances
    let comparisonChart = null;
    let monteCarloChart = null;
    let sensitivityChart = null;

    // DOM Elements
    const canvas = document.getElementById("warehouseCanvas");
    const ctx = canvas.getContext("2d");
    const strategySelect = document.getElementById("strategySelect");
    const breakdownSlider = document.getElementById("breakdownSlider");
    const breakdownValBadge = document.getElementById("breakdownValBadge");
    const congestionSelect = document.getElementById("congestionSelect");
    const btnRunSim = document.getElementById("btnRunSim");
    const btnMonteCarlo = document.getElementById("btnMonteCarlo");
    const btnSensitivity = document.getElementById("btnSensitivity");
    const btnReset = document.getElementById("btnReset");
    const btnPlayPause = document.getElementById("btnPlayPause");
    const simTimeLabel = document.getElementById("simTimeLabel");
    const fleetContainer = document.getElementById("fleetContainer");
    const taskTableBody = document.getElementById("taskTableBody");
    const eventLogContainer = document.getElementById("eventLogContainer");
    const toast = document.getElementById("toastNotification");

    // KPI Elements
    const kpiMakespan = document.getElementById("kpiMakespan");
    const kpiMakespanSub = document.getElementById("kpiMakespanSub");
    const kpiOnTime = document.getElementById("kpiOnTime");
    const kpiOnTimeSub = document.getElementById("kpiOnTimeSub");
    const kpiTasksDone = document.getElementById("kpiTasksDone");
    const kpiTasksSub = document.getElementById("kpiTasksSub");
    const kpiBreakdowns = document.getElementById("kpiBreakdowns");
    const kpiBreakdownsSub = document.getElementById("kpiBreakdownsSub");
    const kpiEnergy = document.getElementById("kpiEnergy");
    const kpiEnergySub = document.getElementById("kpiEnergySub");

    // =========================================================================
    // INITIALIZATION & CONFIG LOADING
    // =========================================================================
    async function init() {
        setupTabs();
        setupSpeedControls();
        setupEventListeners();
        initCharts();
        await loadConfig();
        renderInitialFleet();
        renderInitialTasks();
        drawCanvas(0);
        showToast("RoboFlow ready. Click 'Run Simulation' to execute task allocation.");
    }

    async function loadConfig() {
        try {
            const res = await fetch("/api/config");
            const data = await res.json();
            warehouseConfig = data.warehouse;
            initialRobots = data.robots;
            initialTasks = data.tasks;
        } catch (err) {
            console.error("Failed to load config:", err);
            showToast("Error connecting to Python backend server", 4000);
        }
    }

    // =========================================================================
    // UI CONTROLS & LISTENERS
    // =========================================================================
    function setupEventListeners() {
        breakdownSlider.addEventListener("input", (e) => {
            breakdownValBadge.textContent = `${e.target.value}%`;
        });

        btnRunSim.addEventListener("click", () => runSimulation());
        btnMonteCarlo.addEventListener("click", () => runMonteCarlo());
        btnSensitivity.addEventListener("click", () => runSensitivity());
        btnReset.addEventListener("click", () => resetSimulation());

        btnPlayPause.addEventListener("click", () => {
            if (!simData) return;
            isPlaying = !isPlaying;
            btnPlayPause.innerHTML = isPlaying ? '<i class="fa-solid fa-pause"></i>' : '<i class="fa-solid fa-play"></i>';
            if (isPlaying) {
                lastTimestamp = performance.now();
                animFrameId = requestAnimationFrame(animateLoop);
            }
        });
    }

    function setupTabs() {
        document.querySelectorAll(".tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
                document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
                btn.classList.add("active");
                const targetId = btn.getAttribute("data-tab");
                const targetContent = document.getElementById(targetId);
                if (targetContent) targetContent.classList.add("active");
            });
        });
    }

    function setupSpeedControls() {
        document.querySelectorAll(".speed-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".speed-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                playbackSpeed = parseFloat(btn.getAttribute("data-speed"));
            });
        });
    }

    function showToast(msg, duration = 3000) {
        toast.textContent = msg;
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), duration);
    }

    // =========================================================================
    // RENDERING INITIAL FLEET & TASKS
    // =========================================================================
    function renderInitialFleet() {
        fleetContainer.innerHTML = "";
        initialRobots.forEach(r => {
            const card = document.createElement("div");
            card.className = "robot-card";
            card.id = `robot-card-${r.id}`;
            card.innerHTML = `
                <div class="robot-header">
                    <div class="robot-identity">
                        <span class="robot-tag" style="background: ${r.color}">${r.id}</span>
                        <span class="robot-name">${r.name}</span>
                    </div>
                    <span class="robot-status-badge idle" id="badge-${r.id}">IDLE</span>
                </div>
                <div class="robot-battery-row">
                    <div class="battery-bar-wrap">
                        <div class="battery-bar-fill high" id="bat-bar-${r.id}" style="width: 100%;"></div>
                    </div>
                    <span class="battery-text" id="bat-val-${r.id}">100%</span>
                </div>
                <div class="robot-metrics-grid">
                    <div class="metric-item">Speed: <strong>${r.base_speed} m/s</strong></div>
                    <div class="metric-item">Distance: <strong id="dist-${r.id}">0.0 m</strong></div>
                    <div class="metric-item">Completed: <strong id="done-${r.id}">0</strong></div>
                </div>
            `;
            fleetContainer.appendChild(card);
        });
    }

    function renderInitialTasks() {
        taskTableBody.innerHTML = "";
        initialTasks.forEach(t => {
            const tr = document.createElement("tr");
            tr.id = `task-row-${t.id}`;
            const prioClass = t.priority.toLowerCase();
            tr.innerHTML = `
                <td><strong>${t.id}</strong> <small style="color:#64748b">(${t.payload_kg}kg)</small></td>
                <td><span class="prio-badge ${prioClass}">${t.priority}</span></td>
                <td id="t-robot-${t.id}"><span style="color:#64748b">Unassigned</span></td>
                <td><span class="task-status-badge pending" id="t-status-${t.id}">PENDING</span></td>
                <td><span style="font-family:var(--font-mono)">${t.deadline}s</span></td>
                <td id="t-finish-${t.id}"><span style="color:#64748b">--</span></td>
            `;
            taskTableBody.appendChild(tr);
        });
    }

    // =========================================================================
    // RUN SIMULATION (CORE API CALL)
    // =========================================================================
    async function runSimulation() {
        const strategy = strategySelect.value;
        const breakdownRate = parseFloat(breakdownSlider.value) / 100.0;
        const congestion = congestionSelect.value;

        btnRunSim.disabled = true;
        btnRunSim.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Optimizing...';
        showToast("Running stochastic optimization & discrete-event simulation...");

        try {
            const res = await fetch("/api/simulate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    strategy: strategy,
                    breakdown_rate: breakdownRate,
                    congestion: congestion,
                    seed: currentSeed
                })
            });

            const data = await res.json();
            btnRunSim.disabled = false;
            btnRunSim.innerHTML = '<i class="fa-solid fa-play"></i> Run Simulation';

            if (data.mode === "compare") {
                handleCompareSimulation(data);
            } else {
                handleSingleSimulation(data);
            }
        } catch (err) {
            console.error("Simulation error:", err);
            btnRunSim.disabled = false;
            btnRunSim.innerHTML = '<i class="fa-solid fa-play"></i> Run Simulation';
            showToast("Simulation execution failed. Check console.", 4000);
        }
    }

    function handleSingleSimulation(data) {
        simData = data.result;
        maxSimTime = simData.makespan;
        currentTime = 0.0;
        isPlaying = true;
        btnPlayPause.innerHTML = '<i class="fa-solid fa-pause"></i>';
        lastTimestamp = performance.now();

        // Update KPIs immediately
        updateKPIs(simData);

        // Update Strategy Badge
        document.getElementById("activeStrategyBadge").textContent = 
            data.strategy === "stochastic" ? "Stochastic (Risk-Averse)" : "Deterministic (Greedy)";
        document.getElementById("totalDistLabel").textContent = `${simData.total_distance_m} m`;

        // Populate Event Log
        populateEventLog(simData.events);

        // Update Task Table with Allocation
        updateTaskTableAllocation(simData.task_states);

        // Update Comparison Chart with single strategy profile
        updateComparisonChartSingle(data.strategy, simData);

        // Start Canvas Animation Loop
        if (animFrameId) cancelAnimationFrame(animFrameId);
        animFrameId = requestAnimationFrame(animateLoop);

        showToast(`Simulation complete! Realized Makespan: ${simData.makespan}s | Rescues: ${simData.reassignments_count}`);
    }

    function handleCompareSimulation(data) {
        // Compare mode returns both results! We visualize stochastic by default, but update chart with side-by-side
        const det = data.deterministic_result;
        const stoch = data.stochastic_result;
        simData = stoch; // Visualize resilient stochastic execution
        maxSimTime = stoch.makespan;
        currentTime = 0.0;
        isPlaying = true;
        btnPlayPause.innerHTML = '<i class="fa-solid fa-pause"></i>';
        lastTimestamp = performance.now();

        updateKPIs(stoch);
        document.getElementById("kpiMakespanSub").innerHTML = 
            `<strong style="color:var(--emerald)">${data.summary.makespan_improvement_pct}% faster</strong> than Deterministic (${det.makespan}s)`;
        document.getElementById("kpiBreakdownsSub").innerHTML = 
            `Stochastic: ${stoch.reassignments_count} rescues | Det: ${det.reassignments_count} rescues`;

        populateEventLog(stoch.events);
        updateTaskTableAllocation(stoch.task_states);
        updateComparisonChartDual(det, stoch);

        if (animFrameId) cancelAnimationFrame(animFrameId);
        animFrameId = requestAnimationFrame(animateLoop);

        showToast(`Dual Comparison Complete! Stochastic is ${data.summary.makespan_improvement_pct}% more resilient.`);
    }

    function updateKPIs(result) {
        kpiMakespan.textContent = result.makespan;
        kpiMakespanSub.textContent = `Delay Penalty: ${result.total_delay}s`;
        kpiOnTime.textContent = result.on_time_rate;
        kpiOnTimeSub.textContent = `SLA SLA: ${result.on_time_rate >= 90 ? 'PASSED' : 'DEGRADED'}`;
        kpiTasksDone.textContent = result.completed_tasks;
        kpiTasksSub.textContent = `${result.completed_tasks} / ${result.total_tasks} completed`;
        kpiBreakdowns.textContent = result.breakdowns_count;
        kpiBreakdownsSub.textContent = `${result.reassignments_count} dynamic task reassignments`;
        kpiEnergy.textContent = result.total_energy_kwh;
        kpiEnergySub.textContent = `Distance: ${result.total_distance_m}m`;
    }

    function populateEventLog(events) {
        eventLogContainer.innerHTML = "";
        events.forEach(ev => {
            const div = document.createElement("div");
            let typeClass = "";
            if (ev.event_type === "PICKUP") typeClass = "pickup";
            else if (ev.event_type === "DELIVERY") typeClass = "delivery";
            else if (ev.event_type === "BREAKDOWN") typeClass = "breakdown";
            else if (ev.event_type === "REASSIGN") typeClass = "reassign";
            else if (ev.event_type.includes("RECHARGE")) typeClass = "recharge";

            div.className = `log-entry ${typeClass}`;
            div.innerHTML = `
                <span class="log-time">[${formatSimTime(ev.timestamp)}]</span>
                <span class="log-msg">${ev.message}</span>
            `;
            eventLogContainer.appendChild(div);
        });
    }

    function updateTaskTableAllocation(taskStates) {
        for (const [tId, tData] of Object.entries(taskStates)) {
            const robotCell = document.getElementById(`t-robot-${tId}`);
            const statusCell = document.getElementById(`t-status-${tId}`);
            const finishCell = document.getElementById(`t-finish-${tId}`);

            if (robotCell) {
                const rSpec = initialRobots.find(r => r.id === tData.assigned_robot);
                const color = rSpec ? rSpec.color : '#94a3b8';
                let rescueTag = tData.reassigned_from ? ` <small style="color:var(--purple)">(Rescued)</small>` : '';
                robotCell.innerHTML = `<span style="color:${color}; font-weight:700">${tData.assigned_robot}</span>${rescueTag}`;
            }

            if (statusCell) {
                const s = tData.status.toLowerCase();
                statusCell.className = `task-status-badge ${s}`;
                statusCell.textContent = tData.status;
            }

            if (finishCell) {
                finishCell.innerHTML = tData.delivery_time ? 
                    `<strong style="color:${tData.is_late ? 'var(--red)' : 'var(--emerald)'}">${tData.delivery_time}s</strong>` : 
                    '<span style="color:#64748b">--</span>';
            }
        }
    }

    // =========================================================================
    // 2D CANVAS RENDERING & ANIMATION
    // =========================================================================
    function formatSimTime(sec) {
        const m = Math.floor(sec / 60);
        const s = (sec % 60).toFixed(1);
        return `${m.toString().padStart(2, '0')}:${s.padStart(4, '0')}`;
    }

    function animateLoop(now) {
        if (!isPlaying || !simData) return;
        const delta = (now - lastTimestamp) / 1000.0;
        lastTimestamp = now;

        currentTime += delta * 12.0 * playbackSpeed;
        if (currentTime > maxSimTime + 5.0) {
            currentTime = maxSimTime;
            isPlaying = false;
            btnPlayPause.innerHTML = '<i class="fa-solid fa-play"></i>';
        }

        simTimeLabel.textContent = `T: ${formatSimTime(currentTime)}`;
        drawCanvas(currentTime);
        updateFleetTelemetryAtTime(currentTime);

        if (isPlaying) {
            animFrameId = requestAnimationFrame(animateLoop);
        }
    }

    function drawCanvas(t) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const scaleX = canvas.width / 100.0;
        const scaleY = canvas.height / 80.0;

        // 1. Draw Warehouse Grid & Floor
        ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
        ctx.lineWidth = 1;
        for (let x = 0; x <= 100; x += 10) {
            ctx.beginPath();
            ctx.moveTo(x * scaleX, 0);
            ctx.lineTo(x * scaleX, canvas.height);
            ctx.stroke();
        }
        for (let y = 0; y <= 80; y += 10) {
            ctx.beginPath();
            ctx.moveTo(0, y * scaleY);
            ctx.lineTo(canvas.width, y * scaleY);
            ctx.stroke();
        }

        // 2. Draw Storage Rack Aisles
        const rackAisles = [
            { x: 20, y: 20, w: 25, h: 20, label: "Aisle A (Racks 01-10)" },
            { x: 55, y: 20, w: 25, h: 20, label: "Aisle B (Racks 11-20)" },
            { x: 20, y: 45, w: 25, h: 20, label: "Aisle C (Racks 21-30)" },
            { x: 55, y: 45, w: 25, h: 20, label: "Aisle D (Racks 31-40)" }
        ];

        rackAisles.forEach(rack => {
            ctx.fillStyle = "rgba(30, 41, 59, 0.4)";
            ctx.strokeStyle = "rgba(148, 163, 184, 0.15)";
            ctx.lineWidth = 1.5;
            ctx.fillRect(rack.x * scaleX, rack.y * scaleY, rack.w * scaleX, rack.h * scaleY);
            ctx.strokeRect(rack.x * scaleX, rack.y * scaleY, rack.w * scaleX, rack.h * scaleY);

            // Aisle Shelving Bars
            ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
            for (let sy = rack.y + 4; sy < rack.y + rack.h; sy += 4) {
                ctx.beginPath();
                ctx.moveTo(rack.x * scaleX + 4, sy * scaleY);
                ctx.lineTo((rack.x + rack.w) * scaleX - 4, sy * scaleY);
                ctx.stroke();
            }

            ctx.fillStyle = "rgba(148, 163, 184, 0.4)";
            ctx.font = "10px Plus Jakarta Sans";
            ctx.fillText(rack.label, rack.x * scaleX + 6, (rack.y + 3) * scaleY);
        });

        // 3. Draw Charging Docks
        if (warehouseConfig && warehouseConfig.charging_stations) {
            warehouseConfig.charging_stations.forEach(cs => {
                const cx = cs.x * scaleX;
                const cy = cs.y * scaleY;
                ctx.fillStyle = "rgba(245, 158, 11, 0.15)";
                ctx.strokeStyle = "rgba(245, 158, 11, 0.6)";
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(cx, cy, 18, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();

                // Lightning Icon
                ctx.fillStyle = "#f59e0b";
                ctx.font = "12px FontAwesome";
                ctx.fillText("⚡", cx - 5, cy + 5);

                ctx.fillStyle = "#f8fafc";
                ctx.font = "bold 9px Plus Jakarta Sans";
                ctx.textAlign = "center";
                ctx.fillText(cs.name, cx, cy + 28);
                ctx.textAlign = "left";
            });
        }

        // 4. Draw Tasks: Pickups (green diamond) & Dropoffs (blue squares)
        initialTasks.forEach(task => {
            const px = task.pickup[0] * scaleX;
            const py = task.pickup[1] * scaleY;
            const dx = task.dropoff[0] * scaleX;
            const dy = task.dropoff[1] * scaleY;

            // Connection dashed line
            ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 4]);
            ctx.beginPath();
            ctx.moveTo(px, py);
            ctx.lineTo(dx, dy);
            ctx.stroke();
            ctx.setLineDash([]);

            // Pickup Node (Green Diamond)
            ctx.fillStyle = "#10b981";
            ctx.save();
            ctx.translate(px, py);
            ctx.rotate(Math.PI / 4);
            ctx.fillRect(-5, -5, 10, 10);
            ctx.restore();

            // Dropoff Node (Blue Square)
            ctx.fillStyle = "#3b82f6";
            ctx.fillRect(dx - 5, dy - 5, 10, 10);

            // Labels
            ctx.fillStyle = "#94a3b8";
            ctx.font = "9px JetBrains Mono";
            ctx.fillText(task.id, px + 7, py - 4);
        });

        // 5. Draw Dynamic Trajectories & Robots
        if (!simData) {
            // Draw static initial robots
            initialRobots.forEach(r => {
                drawRobotToken(r.init_x * scaleX, r.init_y * scaleY, r.color, r.id, 100, false);
            });
            return;
        }

        // Compute current positions from trajectory breadcrumbs
        Object.values(simData.robot_states).forEach(rState => {
            const traj = rState.trajectory;
            const color = rState.color;
            const rId = rState.id;

            // Find current segment in trajectory
            let pos = { x: traj[0].x, y: traj[0].y, battery: traj[0].battery, status: traj[0].status };
            let isBrokenNow = false;

            for (let i = 0; i < traj.length - 1; i++) {
                const p1 = traj[i];
                const p2 = traj[i + 1];

                if (t >= p1.t && t <= p2.t) {
                    const span = p2.t - p1.t;
                    const frac = span > 0 ? (t - p1.t) / span : 0;
                    pos.x = p1.x + (p2.x - p1.x) * frac;
                    pos.y = p1.y + (p2.y - p1.y) * frac;
                    pos.battery = p1.battery + (p2.battery - p1.battery) * frac;
                    pos.status = p2.status;
                    break;
                } else if (t > p2.t) {
                    pos = { x: p2.x, y: p2.y, battery: p2.battery, status: p2.status };
                }
            }

            if (rState.is_broken && rState.breakdown_time !== null && t >= rState.breakdown_time) {
                isBrokenNow = true;
                pos.status = "BREAKDOWN";
            }

            // Draw route history trail
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.35;
            ctx.beginPath();
            ctx.moveTo(traj[0].x * scaleX, traj[0].y * scaleY);
            for (let pt of traj) {
                if (pt.t <= t) {
                    ctx.lineTo(pt.x * scaleX, pt.y * scaleY);
                }
            }
            ctx.stroke();
            ctx.globalAlpha = 1.0;

            // Draw Robot Token
            drawRobotToken(pos.x * scaleX, pos.y * scaleY, color, rId, pos.battery, isBrokenNow);
        });
    }

    function drawRobotToken(x, y, color, label, batteryPct, isBroken) {
        ctx.save();
        ctx.translate(x, y);

        if (isBroken) {
            // Pulsing Red Breakdown Warning
            ctx.fillStyle = "rgba(239, 68, 68, 0.35)";
            ctx.beginPath();
            ctx.arc(0, 0, 22, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = "#ef4444";
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.fillStyle = "#ef4444";
            ctx.font = "bold 14px FontAwesome";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText("⚠️", 0, -1);
        } else {
            // Glowing AMR Token
            ctx.shadowColor = color;
            ctx.shadowBlur = 12;

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(0, 0, 11, 0, Math.PI * 2);
            ctx.fill();

            ctx.shadowBlur = 0;
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 9px JetBrains Mono";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(label.split("-")[1], 0, 0);

            // Battery bar above robot
            const bWidth = 24;
            const bHeight = 4;
            ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
            ctx.fillRect(-bWidth / 2, -18, bWidth, bHeight);

            ctx.fillStyle = batteryPct > 50 ? "#10b981" : (batteryPct > 20 ? "#f59e0b" : "#ef4444");
            ctx.fillRect(-bWidth / 2, -18, (bWidth * Math.max(0, batteryPct)) / 100, bHeight);
        }

        ctx.restore();
    }

    function updateFleetTelemetryAtTime(t) {
        if (!simData) return;
        Object.values(simData.robot_states).forEach(rState => {
            const rId = rState.id;
            const badge = document.getElementById(`badge-${rId}`);
            const batBar = document.getElementById(`bat-bar-${rId}`);
            const batVal = document.getElementById(`bat-val-${rId}`);
            const card = document.getElementById(`robot-card-${rId}`);
            const doneLabel = document.getElementById(`done-${rId}`);
            const distLabel = document.getElementById(`dist-${rId}`);

            if (rState.is_broken && rState.breakdown_time !== null && t >= rState.breakdown_time) {
                if (badge) {
                    badge.className = "robot-status-badge breakdown";
                    badge.textContent = "BREAKDOWN";
                }
                if (card) card.classList.add("broken");
            } else {
                if (card) card.classList.remove("broken");
                if (badge) {
                    badge.className = "robot-status-badge moving";
                    badge.textContent = "IN TRANSIT";
                }
            }

            if (batBar && batVal) {
                // Estimate battery at time t
                const curBat = rState.battery_pct;
                batVal.textContent = `${Math.round(curBat)}%`;
                batBar.style.width = `${curBat}%`;
                batBar.className = `battery-bar-fill ${curBat > 50 ? 'high' : (curBat > 20 ? 'med' : 'low')}`;
            }

            if (doneLabel) doneLabel.textContent = rState.completed_count;
            if (distLabel) distLabel.textContent = `${rState.total_distance} m`;
        });
    }

    // =========================================================================
    // MONTE CARLO & SENSITIVITY API CALLS & CHARTS
    // =========================================================================
    async function runMonteCarlo() {
        btnMonteCarlo.disabled = true;
        btnMonteCarlo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running 100 Runs...';
        showToast("Simulating 100 Monte Carlo warehouse scenarios...");

        try {
            const breakdownRate = parseFloat(breakdownSlider.value) / 100.0;
            const congestion = congestionSelect.value;
            const res = await fetch("/api/monte-carlo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    scenarios: 100,
                    breakdown_rate: breakdownRate,
                    congestion: congestion,
                    seed: currentSeed
                })
            });

            const data = await res.json();
            btnMonteCarlo.disabled = false;
            btnMonteCarlo.innerHTML = '<i class="fa-solid fa-dice-d20"></i> Monte Carlo (100 Runs)';

            updateMonteCarloChart(data);
            showToast(`Monte Carlo 100 Runs Complete! Stochastic Win Rate: ${data.stochastic_win_rate_pct}%`);
        } catch (err) {
            console.error("Monte Carlo error:", err);
            btnMonteCarlo.disabled = false;
            btnMonteCarlo.innerHTML = '<i class="fa-solid fa-dice-d20"></i> Monte Carlo (100 Runs)';
            showToast("Monte Carlo execution failed", 4000);
        }
    }

    async function runSensitivity() {
        btnSensitivity.disabled = true;
        btnSensitivity.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sweeping Risk...';
        showToast("Sweeping breakdown hazards from 0% to 25%...");

        try {
            const res = await fetch("/api/sensitivity", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ iterations: 25, seed: currentSeed })
            });

            const data = await res.json();
            btnSensitivity.disabled = false;
            btnSensitivity.innerHTML = '<i class="fa-solid fa-chart-line"></i> Sensitivity Curve';

            updateSensitivityChart(data);
            showToast("Sensitivity Analysis Complete! Notice stochastic resiliency stability.");
        } catch (err) {
            console.error("Sensitivity error:", err);
            btnSensitivity.disabled = false;
            btnSensitivity.innerHTML = '<i class="fa-solid fa-chart-line"></i> Sensitivity Curve';
            showToast("Sensitivity sweep failed", 4000);
        }
    }

    function resetSimulation() {
        currentSeed = Math.floor(Math.random() * 90000) + 100;
        simData = null;
        currentTime = 0;
        isPlaying = false;
        if (animFrameId) cancelAnimationFrame(animFrameId);

        btnPlayPause.innerHTML = '<i class="fa-solid fa-play"></i>';
        simTimeLabel.textContent = "T: 0.0s";

        // Reset KPIs
        kpiMakespan.textContent = "--";
        kpiMakespanSub.textContent = "Awaiting simulation run";
        kpiOnTime.textContent = "--";
        kpiOnTimeSub.textContent = "Target SLA: 95.0%";
        kpiTasksDone.textContent = "0";
        kpiTasksSub.textContent = "All 20 warehouse tasks";
        kpiBreakdowns.textContent = "0";
        kpiBreakdownsSub.textContent = "0 dynamic reassignments";
        kpiEnergy.textContent = "--";
        kpiEnergySub.textContent = "5 Autonomous AMRs";

        document.getElementById("activeStrategyBadge").textContent = "Stochastic";
        document.getElementById("totalDistLabel").textContent = "0.0 m";

        renderInitialFleet();
        renderInitialTasks();
        drawCanvas(0);

        eventLogContainer.innerHTML = `
            <div class="log-entry system">
                <span class="log-time">[00:00.0]</span>
                <span class="log-msg">RoboFlow system reset. New scenario seed: ${currentSeed}.</span>
            </div>
        `;

        showToast("System reset with fresh randomized task coordinates.");
    }

    // =========================================================================
    // CHART.JS INITIALIZATION & UPDATES
    // =========================================================================
    function initCharts() {
        // Chart 1: Comparison Bar Chart
        const ctxComp = document.getElementById("comparisonChart").getContext("2d");
        comparisonChart = new Chart(ctxComp, {
            type: "bar",
            data: {
                labels: ["Makespan (s)", "Total Delay (s)", "On-Time Rate (%)", "Energy (kWh)"],
                datasets: [
                    {
                        label: "Stochastic (Risk-Aware)",
                        backgroundColor: "rgba(6, 182, 212, 0.75)",
                        borderColor: "#06b6d4",
                        borderWidth: 1.5,
                        data: [0, 0, 0, 0]
                    },
                    {
                        label: "Deterministic (Greedy)",
                        backgroundColor: "rgba(239, 68, 68, 0.75)",
                        borderColor: "#ef4444",
                        borderWidth: 1.5,
                        data: [0, 0, 0, 0]
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: "#94a3b8", font: { family: 'Plus Jakarta Sans', size: 11 } } }
                },
                scales: {
                    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255, 255, 255, 0.05)" } },
                    y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255, 255, 255, 0.05)" } }
                }
            }
        });

        // Chart 2: Monte Carlo Histogram
        const ctxMC = document.getElementById("monteCarloChart").getContext("2d");
        monteCarloChart = new Chart(ctxMC, {
            type: "bar",
            data: {
                labels: ["150-170s", "170-190s", "190-210s", "210-230s", "230-250s", "250-270s", "270-300s"],
                datasets: [
                    {
                        label: "Stochastic Policy",
                        backgroundColor: "rgba(16, 185, 129, 0.75)",
                        borderColor: "#10b981",
                        borderWidth: 1,
                        data: [5, 28, 42, 18, 5, 2, 0]
                    },
                    {
                        label: "Deterministic Policy",
                        backgroundColor: "rgba(239, 68, 68, 0.65)",
                        borderColor: "#ef4444",
                        borderWidth: 1,
                        data: [0, 8, 22, 26, 24, 12, 8]
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: "#94a3b8", font: { family: 'Plus Jakarta Sans', size: 11 } } }
                },
                scales: {
                    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255, 255, 255, 0.05)" } },
                    y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255, 255, 255, 0.05)" } }
                }
            }
        });

        // Chart 3: Sensitivity Line Chart
        const ctxSens = document.getElementById("sensitivityChart").getContext("2d");
        sensitivityChart = new Chart(ctxSens, {
            type: "line",
            data: {
                labels: ["0%", "5%", "10%", "15%", "20%", "25%"],
                datasets: [
                    {
                        label: "Deterministic Policy (Makespan)",
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239, 68, 68, 0.15)",
                        borderWidth: 3,
                        pointBackgroundColor: "#ef4444",
                        pointRadius: 5,
                        fill: true,
                        tension: 0.35,
                        data: [168, 192, 225, 265, 312, 360]
                    },
                    {
                        label: "Stochastic Policy (Makespan)",
                        borderColor: "#06b6d4",
                        backgroundColor: "rgba(6, 182, 212, 0.15)",
                        borderWidth: 3,
                        pointBackgroundColor: "#06b6d4",
                        pointRadius: 5,
                        fill: true,
                        tension: 0.35,
                        data: [174, 180, 191, 204, 218, 232]
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: "#94a3b8", font: { family: 'Plus Jakarta Sans', size: 12 } } },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: {
                        title: { display: true, text: "Robot Breakdown Probability", color: "#64748b" },
                        ticks: { color: "#94a3b8" },
                        grid: { color: "rgba(255, 255, 255, 0.05)" }
                    },
                    y: {
                        title: { display: true, text: "Expected Makespan (Seconds)", color: "#64748b" },
                        ticks: { color: "#94a3b8" },
                        grid: { color: "rgba(255, 255, 255, 0.05)" }
                    }
                }
            }
        });
    }

    function updateComparisonChartSingle(strategy, result) {
        comparisonChart.data.datasets[0].data = [
            result.makespan,
            result.total_delay,
            result.on_time_rate,
            result.total_energy_kwh
        ];
        comparisonChart.data.datasets[0].label = `${strategy.toUpperCase()} Executed`;
        comparisonChart.data.datasets[1].data = [0, 0, 0, 0];
        comparisonChart.update();
    }

    function updateComparisonChartDual(det, stoch) {
        comparisonChart.data.datasets[0].data = [
            stoch.makespan,
            stoch.total_delay,
            stoch.on_time_rate,
            stoch.total_energy_kwh
        ];
        comparisonChart.data.datasets[1].data = [
            det.makespan,
            det.total_delay,
            det.on_time_rate,
            det.total_energy_kwh
        ];
        comparisonChart.update();
    }

    function updateMonteCarloChart(data) {
        monteCarloChart.data.labels = data.histogram.bins;
        monteCarloChart.data.datasets[0].data = data.histogram.stochastic_counts;
        monteCarloChart.data.datasets[1].data = data.histogram.deterministic_counts;
        monteCarloChart.update();

        // Update Mini Stats
        document.getElementById("stochMeanVal").textContent = `${data.stochastic.makespan_mean}s`;
        document.getElementById("detMeanVal").textContent = `${data.deterministic.makespan_mean}s`;
        document.getElementById("varDiffVal").textContent = `${data.stochastic.makespan_p95}s vs ${data.deterministic.makespan_p95}s`;
        document.getElementById("winRateVal").textContent = `${data.stochastic_win_rate_pct}%`;
    }

    function updateSensitivityChart(data) {
        sensitivityChart.data.labels = data.rate_labels;
        sensitivityChart.data.datasets[0].data = data.deterministic_makespan;
        sensitivityChart.data.datasets[1].data = data.stochastic_makespan;
        sensitivityChart.update();
    }

    // Launch!
    init();
});
