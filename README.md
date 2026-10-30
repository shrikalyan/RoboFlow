# 🚀 RoboFlow – Stochastic Warehouse Robot Task Allocation

A production-grade, mathematically grounded simulation and optimization platform for Autonomous Mobile Robots (AMRs) operating in uncertain warehouse environments.

RoboFlow solves the **Multi-Robot Task Allocation (MRTA)** problem under multi-parameter stochasticity:
1. **Probabilistic Task Arrivals** (Poisson arrival processes)
2. **Stochastic Travel Times & Congestion** (Log-normal aisle traffic delay distributions)
3. **Dynamic Battery Drain & Depletion** (Payload-weighted power consumption with auto-docking)
4. **Mechanical Breakdowns & Dynamic Rescue Recourse** (Hazard rate evaluation with online reassignment)

---

## 📸 Key Features

* **5 Autonomous Mobile Robots (AMRs)**: Configured with heterogeneous physical properties (Atlas-1, Bolt-2, Titan-3, Nova-4, Echo-5) including unique speeds, variance profiles, battery capacities, discharge rates, and failure probabilities.
* **20 Realistic Warehouse Tasks**: Scattered across storage rack zones (Aisles A–D) and dispatch staging bays with randomized payloads (12–48 kg), handling times, release times, and priority classes.
* **Deterministic vs. Stochastic Optimization**:
  * **Deterministic Policy**: Traditional greedy makespan minimization assuming nominal conditions. Heavily overloads fast robots, creating catastrophic bottlenecks upon failure.
  * **Stochastic Policy (Chance-Constrained & Risk-Aware)**: Incorporates 95% service-level travel time buffers ($E[T] + z_{0.95} \sigma$), breakdown hazard penalties, battery safety margins, and spatial co-location bonuses for resilient rescue operations.
* **Online Dynamic Reassignment**: Instantaneous automated recovery when a robot suffers a breakdown midway through a task or transit. The orphan payload and pending queue are dynamically reassigned to surviving active robots with minimal marginal makespan inflation.
* **100-Scenario Monte Carlo Engine**: Compares both policies over 100 identical random warehouse realization seeds, generating empirical probability distributions, standard deviations, and 95th-percentile Value-at-Risk (VaR).
* **Breakdown Hazard Sensitivity Sweep**: Sweeps robot failure probabilities from 0% to 25% to demonstrate the exact resilience advantage of stochastic allocation over deterministic planning.
* **Cyber-Industrial Glassmorphic Dashboard**: Real-time 2D warehouse canvas floorplan (100m × 80m), live AMR trajectory tracking, interactive speed controls, animated battery gauges, event audit logs, and interactive Chart.js analytics.

---

## 🛠️ Architecture & File Structure

```
RoboFlow/
├── app.py                     # Flask server & stochastic optimization engine
├── requirements.txt           # Python package dependencies (Flask, NumPy)
├── README.md                  # Detailed documentation & setup guide
├── templates/
│   └── index.html             # Premium responsive dashboard layout
└── static/
    ├── style.css              # Cyber-industrial dark theme styling & glassmorphism
    └── script.js              # 2D Canvas rendering, simulation playback & Chart.js logic
```

---

## 🚀 Getting Started (VS Code & Local Execution)

### 1. Prerequisites
- Python 3.9+ installed.
- VS Code (or your preferred editor).

### 2. Installation
Open a terminal in the project directory:
```bash
pip install -r requirements.txt
```

### 3. Running the Server
Launch the local Flask server:
```bash
python app.py
```
You will see:
```
======================================================================
🚀 RoboFlow – Stochastic Warehouse Robot Task Allocation Server
📍 Local Web Dashboard: http://127.0.0.1:5000
======================================================================
```

### 4. Opening the Dashboard
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧠 Mathematical Formulation

### 1. Stochastic Travel Time Model
The realized travel time $T_{ij}^{k}$ for robot $k$ between coordinates $i$ and $j$ is given by:
$$T_{ij}^{k} = \frac{d(i, j)}{v_k} \cdot \left(1 + \delta_{\text{congestion}}\right)$$
where $d(i, j)$ is the aisle-constrained navigation distance, $v_k \sim \mathcal{N}(\mu_{v,k}, \sigma_{v,k}^2)$, and $\delta_{\text{congestion}} \sim \text{LogNormal}(\mu_{\text{cong}}, \sigma_{\text{cong}}^2)$.

### 2. Breakdown Hazard Model
The cumulative hazard of robot $k$ experiencing a mechanical fault over a transit distance $d$ is formulated via a Poisson survival process:
$$P(\text{Breakdown}) = 1 - \exp\left(-\lambda_k \cdot \kappa_{\text{hazard}} \cdot \frac{d}{d_0}\right)$$
where $\lambda_k$ is the robot's base breakdown rate and $\kappa_{\text{hazard}}$ is the operational stress multiplier.

### 3. Dynamic Recourse Function
When robot $R_{\text{broken}}$ fails at coordinate $(x_f, y_f)$ at time $t_f$, an orphaned task $T_j$ is dynamically reassigned to candidate surviving robot $R^*$ according to:
$$R^* = \arg\min_{R \in \mathcal{R}_{\text{active}}} \Big( \alpha \cdot d(loc(R), loc(T_j)) + \beta \cdot |\mathcal{Q}_R| + \gamma \cdot (1 - \text{SoC}_R) \Big)$$
where $\text{SoC}_R$ is the robot's battery state of charge.

---

## 📊 Analytics Included in Dashboard

1. **Deterministic vs. Stochastic Policy Comparison**: Side-by-side grouped metrics (Makespan, Total Delay, On-Time SLA %, Energy Consumed).
2. **100-Scenario Monte Carlo Distribution**: Dual histogram demonstrating tight variance in stochastic routing versus long-tail catastrophic delays in deterministic routing.
3. **Breakdown Sensitivity Curve**: Shows how deterministic makespan degrades exponentially as failure rates climb, while stochastic routing maintains steady performance.
4. **Robot Telemetry**: Real-time battery levels, operational states (Idle, In Transit, Charging, Breakdown), and completed task counters.

---

## 📄 License
MIT License. Built for industrial autonomous warehouse optimization and academic research.
