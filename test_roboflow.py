"""
Test Suite for RoboFlow Warehouse Optimization Backend
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import (
    app, ROBOT_CATALOG, generate_default_tasks,
    DeterministicOptimizer, StochasticOptimizer,
    WarehouseSimulator, MonteCarloEngine, SensitivityEngine
)

def run_all_tests():
    print("=" * 60)
    print("[TEST] Running RoboFlow Backend Verification Suite")
    print("=" * 60)
    
    # Test 1: Task and Robot Generation
    tasks = generate_default_tasks(42)
    assert len(tasks) == 20, f"Expected 20 tasks, got {len(tasks)}"
    assert len(ROBOT_CATALOG) == 5, f"Expected 5 robots, got {len(ROBOT_CATALOG)}"
    print("[OK] Test 1 Passed: 5 Robots & 20 Tasks verified.")

    # Test 2: Deterministic Optimization
    det_alloc = DeterministicOptimizer.allocate(ROBOT_CATALOG, tasks)
    assigned_tasks = sum(len(q) for q in det_alloc.values())
    assert assigned_tasks == 20, f"Expected 20 assigned tasks, got {assigned_tasks}"
    print(f"[OK] Test 2 Passed: Deterministic Allocation assigned all 20 tasks across {len(det_alloc)} robots.")

    # Test 3: Stochastic Optimization
    stoch_alloc = StochasticOptimizer.allocate(ROBOT_CATALOG, tasks, breakdown_mult=1.0)
    assigned_tasks_stoch = sum(len(q) for q in stoch_alloc.values())
    assert assigned_tasks_stoch == 20, f"Expected 20 assigned tasks, got {assigned_tasks_stoch}"
    print(f"[OK] Test 3 Passed: Stochastic Allocation assigned all 20 tasks across {len(stoch_alloc)} robots.")

    # Test 4: Simulation Execution & Dynamic Reassignment
    sim = WarehouseSimulator(ROBOT_CATALOG, tasks, stoch_alloc, breakdown_rate_mult=2.5, congestion_level="high", rng_seed=999)
    res = sim.run()
    assert "makespan" in res and res["makespan"] > 0
    assert "robot_states" in res and len(res["robot_states"]) == 5
    assert "events" in res and len(res["events"]) > 0
    print(f"[OK] Test 4 Passed: Simulation finished. Makespan: {res['makespan']}s | Breakdowns: {res['breakdowns_count']} | Rescues: {res['reassignments_count']}")

    # Test 5: Monte Carlo 100 Scenarios
    print("[...] Running Test 5: Monte Carlo (100 scenarios)...")
    mc = MonteCarloEngine.run_comparison(scenarios=100, breakdown_mult=1.2, congestion="medium", base_seed=42)
    assert mc["scenarios_count"] == 100
    assert "deterministic" in mc and "stochastic" in mc
    assert "histogram" in mc
    print(f"[OK] Test 5 Passed: 100 Scenarios evaluated. Stochastic Win Rate: {mc['stochastic_win_rate_pct']}% | Stoch P95 VaR: {mc['stochastic']['makespan_p95']}s vs Det P95: {mc['deterministic']['makespan_p95']}s")

    # Test 6: Sensitivity Analysis Sweep
    print("[...] Running Test 6: Sensitivity Analysis Sweep (0% - 25%)...")
    sens = SensitivityEngine.run_sweep(rates=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25], iterations_per_rate=10, base_seed=42)
    assert len(sens["rates"]) == 6
    assert len(sens["deterministic_makespan"]) == 6
    assert len(sens["stochastic_makespan"]) == 6
    print(f"[OK] Test 6 Passed: Sensitivity curve generated across 6 risk rates.")

    # Test 7: Flask Test Client Endpoint Checks
    client = app.test_client()
    
    # 7a: GET /
    res_index = client.get("/")
    assert res_index.status_code == 200, f"Index returned {res_index.status_code}"
    
    # 7b: GET /api/config
    res_cfg = client.get("/api/config")
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.get_json()
    assert len(cfg_data["robots"]) == 5
    assert len(cfg_data["tasks"]) == 20
    
    # 7c: POST /api/simulate
    res_sim = client.post("/api/simulate", json={"strategy": "compare", "breakdown_rate": 0.05, "congestion": "medium", "seed": 42})
    assert res_sim.status_code == 200
    sim_data = res_sim.get_json()
    assert sim_data["mode"] == "compare"
    assert "summary" in sim_data
    
    print("[OK] Test 7 Passed: Flask REST Endpoints (/ , /api/config, /api/simulate) verified 100% OK.")
    print("=" * 60)
    print("[SUCCESS] ALL TESTS PASSED! BACKEND IS VERIFIED AND READY.")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
