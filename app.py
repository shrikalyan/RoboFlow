"""
RoboFlow – Stochastic Warehouse Robot Task Allocation
Flask Backend & Mathematical Optimization Engine
"""

import math
import random
import copy
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# ==============================================================================
# WAREHOUSE ENVIRONMENT CONFIGURATION
# ==============================================================================

WAREHOUSE_WIDTH = 100.0   # meters (X-axis)
WAREHOUSE_HEIGHT = 80.0   # meters (Y-axis)

CHARGING_STATIONS = [
    {"id": "CS-1", "x": 10.0, "y": 10.0, "name": "North Dock"},
    {"id": "CS-2", "x": 90.0, "y": 15.0, "name": "East Dock"},
    {"id": "CS-3", "x": 50.0, "y": 75.0, "name": "South Dock"},
]

# Fixed seed generation for reproducibility, but can be randomized via API
DEFAULT_SEED = 42

def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

def manhattan_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    # Aisle-constrained warehouse navigation approximation
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def travel_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    # Hybrid aisle distance: 70% Manhattan (aisles) + 30% Euclidean smoothing
    return 0.7 * manhattan_distance(p1, p2) + 0.3 * euclidean_distance(p1, p2)


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclass
class RobotSpec:
    id: str
    name: str
    base_speed: float          # m/s (nominal)
    speed_variance: float      # std dev
    battery_capacity: float    # kWh
    discharge_rate: float      # kWh per meter
    base_breakdown_prob: float # per task leg
    home_station: str
    init_x: float
    init_y: float
    color: str

ROBOT_CATALOG: List[RobotSpec] = [
    RobotSpec("R-1", "Atlas-1", 1.5, 0.15, 100.0, 0.080, 0.040, "CS-1", 10.0, 10.0, "#06b6d4"), # Cyan
    RobotSpec("R-2", "Bolt-2",  1.8, 0.20, 90.0,  0.092, 0.055, "CS-1", 15.0, 10.0, "#3b82f6"), # Blue
    RobotSpec("R-3", "Titan-3", 1.2, 0.10, 120.0, 0.068, 0.030, "CS-3", 50.0, 75.0, "#8b5cf6"), # Purple
    RobotSpec("R-4", "Nova-4",  1.6, 0.18, 95.0,  0.085, 0.045, "CS-2", 90.0, 15.0, "#10b981"), # Emerald
    RobotSpec("R-5", "Echo-5",  1.4, 0.12, 105.0, 0.075, 0.035, "CS-2", 85.0, 15.0, "#f59e0b"), # Amber
]

@dataclass
class Task:
    id: str
    name: str
    pickup: Tuple[float, float]
    dropoff: Tuple[float, float]
    payload_kg: float
    handling_time: float      # seconds
    priority: str             # "CRITICAL", "HIGH", "STANDARD"
    arrival_time: float       # seconds into simulation (probabilistic arrival)
    deadline: float           # target completion deadline
    nominal_distance: float = 0.0

    def __post_init__(self):
        self.nominal_distance = round(travel_distance(self.pickup, self.dropoff), 1)

def generate_default_tasks(seed: int = DEFAULT_SEED) -> List[Task]:
    rng = random.Random(seed)
    tasks: List[Task] = []
    
    # 20 distinct warehouse tasks distributed across racks & loading docks
    priorities = ["CRITICAL", "HIGH", "STANDARD"]
    priority_weights = [0.2, 0.35, 0.45]
    
    # Storage zone bounds
    rack_zones = [
        {"x_min": 20, "x_max": 45, "y_min": 20, "y_max": 40},
        {"x_min": 55, "x_max": 80, "y_min": 20, "y_max": 40},
        {"x_min": 20, "x_max": 45, "y_min": 45, "y_max": 65},
        {"x_min": 55, "x_max": 80, "y_min": 45, "y_max": 65},
    ]
    
    # Delivery dispatch zones (near perimeter)
    drop_zones = [
        (15.0, 70.0), (85.0, 70.0), (50.0, 15.0), (15.0, 35.0),
        (85.0, 35.0), (30.0, 75.0), (70.0, 75.0), (50.0, 25.0)
    ]
    
    for i in range(1, 21):
        zone = rng.choice(rack_zones)
        pickup_x = round(rng.uniform(zone["x_min"], zone["x_max"]), 1)
        pickup_y = round(rng.uniform(zone["y_min"], zone["y_max"]), 1)
        
        drop_anchor = rng.choice(drop_zones)
        drop_x = round(drop_anchor[0] + rng.uniform(-4, 4), 1)
        drop_y = round(drop_anchor[1] + rng.uniform(-4, 4), 1)
        
        payload = round(rng.uniform(12.0, 48.0), 1)
        handling = round(rng.uniform(15.0, 35.0), 1)
        prio = rng.choices(priorities, weights=priority_weights)[0]
        
        # Probabilistic Poisson-like arrivals: tasks arrive over first 120 seconds
        arr_time = round(rng.expovariate(1.0 / 25.0) if i > 3 else 0.0, 1)
        arr_time = min(arr_time, 140.0)
        
        # Deadlines based on distance + handling + priority slack
        direct_dist = travel_distance((pickup_x, pickup_y), (drop_x, drop_y))
        slack_mult = 2.2 if prio == "CRITICAL" else (2.8 if prio == "HIGH" else 3.5)
        deadline = round(arr_time + (direct_dist / 1.5 + handling) * slack_mult + 60.0, 1)
        
        task = Task(
            id=f"T-{i:02d}",
            name=f"Order #{1000 + i}",
            pickup=(pickup_x, pickup_y),
            dropoff=(drop_x, drop_y),
            payload_kg=payload,
            handling_time=handling,
            priority=prio,
            arrival_time=arr_time,
            deadline=deadline
        )
        tasks.append(task)
        
    return tasks


# ==============================================================================
# OPTIMIZATION ALGORITHMS
# ==============================================================================

class DeterministicOptimizer:
    """
    Standard Deterministic Task Allocation:
    Assumes zero breakdowns, constant nominal velocities, zero aisle congestion,
    and linear battery drain. Uses greedy makespan-minimization insertion.
    Tends to concentrate tasks heavily on the fastest robots (Bolt-2, Nova-4),
    creating extreme vulnerability to single-point failures.
    """
    @staticmethod
    def allocate(robots: List[RobotSpec], tasks: List[Task]) -> Dict[str, List[str]]:
        # Sort tasks by arrival time, then priority
        priority_score = {"CRITICAL": 0, "HIGH": 1, "STANDARD": 2}
        sorted_tasks = sorted(tasks, key=lambda t: (t.arrival_time, priority_score[t.priority]))
        
        allocations: Dict[str, List[str]] = {r.id: [] for r in robots}
        robot_curr_pos: Dict[str, Tuple[float, float]] = {r.id: (r.init_x, r.init_y) for r in robots}
        robot_completion_time: Dict[str, float] = {r.id: 0.0 for r in robots}
        robot_map = {r.id: r for r in robots}
        
        for task in sorted_tasks:
            best_robot_id = None
            best_finish_time = float("inf")
            
            for r in robots:
                # Nominal travel: current -> pickup -> dropoff
                curr_loc = robot_curr_pos[r.id]
                dist_to_pickup = travel_distance(curr_loc, task.pickup)
                dist_trip = dist_to_pickup + task.nominal_distance
                
                # Deterministic time with zero variance
                travel_time = dist_trip / r.base_speed
                start_time = max(robot_completion_time[r.id], task.arrival_time)
                est_finish = start_time + travel_time + task.handling_time
                
                if est_finish < best_finish_time:
                    best_finish_time = est_finish
                    best_robot_id = r.id
                    
            allocations[best_robot_id].append(task.id)
            robot_completion_time[best_robot_id] = best_finish_time
            robot_curr_pos[best_robot_id] = task.dropoff
            
        return allocations


class StochasticOptimizer:
    """
    Robust Risk-Aware Stochastic Optimization (Chance-Constrained with Recourse):
    1. Minimizes Expected Fleet Makespan: considers max completion time across all robots.
    2. Breakdown Hazard Recourse Buffer: penalizes putting too many sequential tasks on high-risk robots,
       explicitly modeling expected rescue latency = P(breakdown) * remaining_workload * rescue_overhead.
    3. Log-Normal Congestion & Travel Time Variance Buffer: evaluates 90th percentile travel times (Mean + 1.28 * StdDev).
    4. Proximity & Battery Preservation: ensures robots maintain battery safety reserve (>20%) and
       clusters geographically to avoid excessive empty runs.
    """
    @staticmethod
    def allocate(robots: List[RobotSpec], tasks: List[Task], breakdown_mult: float = 1.0) -> Dict[str, List[str]]:
        priority_score = {"CRITICAL": 0, "HIGH": 1, "STANDARD": 2}
        # Sort tasks by priority first, then deadline tightness
        sorted_tasks = sorted(tasks, key=lambda t: (priority_score[t.priority], t.deadline, t.arrival_time))
        
        allocations: Dict[str, List[str]] = {r.id: [] for r in robots}
        robot_curr_pos: Dict[str, Tuple[float, float]] = {r.id: (r.init_x, r.init_y) for r in robots}
        robot_completion_time: Dict[str, float] = {r.id: 0.0 for r in robots}
        robot_battery_left: Dict[str, float] = {r.id: r.battery_capacity for r in robots}
        robot_assigned_counts: Dict[str, int] = {r.id: 0 for r in robots}
        robot_map = {r.id: r for r in robots}
        
        for task in sorted_tasks:
            best_robot_id = None
            best_cost = float("inf")
            current_max_makespan = max(robot_completion_time.values()) if any(robot_completion_time.values()) else 0.0
            
            for r in robots:
                curr_loc = robot_curr_pos[r.id]
                dist_empty = travel_distance(curr_loc, task.pickup)
                dist_loaded = task.nominal_distance
                total_dist = dist_empty + dist_loaded
                
                # 1. Stochastic Travel Time with Congestion Buffer (90th percentile)
                effective_speed = max(0.6, (r.base_speed * 0.90) - 1.28 * r.speed_variance)
                stoch_travel_time = total_dist / effective_speed
                stoch_handling = task.handling_time * 1.12
                
                start_time = max(robot_completion_time[r.id], task.arrival_time)
                new_robot_finish = start_time + stoch_travel_time + stoch_handling
                
                # Resulting global makespan if assigned to robot r
                other_max = max([robot_completion_time[o_id] for o_id in robot_completion_time if o_id != r.id] + [0.0])
                resulting_makespan = max(other_max, new_robot_finish)
                
                # 2. Cumulative Breakdown Risk & Expected Rescue Recourse Cost
                # As assigned count increases, probability of failure during the shift compounds
                assigned_n = robot_assigned_counts[r.id] + 1
                p_fail_cumulative = 1.0 - math.exp(- (r.base_breakdown_prob * breakdown_mult) * (assigned_n * 0.40))
                # If this robot breaks down, each task assigned to it incurs dynamic rescue penalty (approx 65s delay)
                expected_rescue_penalty = p_fail_cumulative * (assigned_n * 65.0)
                
                # 3. Battery Risk & Recharging Penalty
                energy_needed = total_dist * r.discharge_rate * (1.0 + task.payload_kg / 140.0)
                remaining_battery = robot_battery_left[r.id] - energy_needed
                battery_penalty = 0.0
                if remaining_battery / r.battery_capacity < 0.22:
                    # High risk of triggering mid-shift charging detour
                    battery_penalty = 120.0 + (0.22 - (remaining_battery / r.battery_capacity)) * 300.0
                    
                # 4. Proximity / Empty Distance efficiency bonus
                empty_transit_cost = dist_empty * 0.75
                
                # Total Stochastic Cost
                total_cost = resulting_makespan + expected_rescue_penalty + battery_penalty + empty_transit_cost
                
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_robot_id = r.id
                    
            allocations[best_robot_id].append(task.id)
            r_sel = robot_map[best_robot_id]
            dist_leg = travel_distance(robot_curr_pos[best_robot_id], task.pickup) + task.nominal_distance
            robot_curr_pos[best_robot_id] = task.dropoff
            
            # Update robot tracking
            effective_speed = max(0.6, (r_sel.base_speed * 0.90) - 1.28 * r_sel.speed_variance)
            stoch_transit = dist_leg / effective_speed
            robot_completion_time[best_robot_id] = max(robot_completion_time[best_robot_id], task.arrival_time) + stoch_transit + (task.handling_time * 1.12)
            energy_used = dist_leg * r_sel.discharge_rate * (1.0 + task.payload_kg / 140.0)
            robot_battery_left[best_robot_id] = max(3.0, robot_battery_left[best_robot_id] - energy_used)
            robot_assigned_counts[best_robot_id] += 1
            
        return allocations


# ==============================================================================
# DISCRETE-EVENT SIMULATION & STOCHASTIC REALIZATION ENGINE
# ==============================================================================

@dataclass
class SimulationEvent:
    timestamp: float
    event_type: str    # "TASK_START", "PICKUP", "DELIVERY", "BREAKDOWN", "REASSIGN", "RECHARGE_START", "RECHARGE_DONE"
    robot_id: str
    task_id: Optional[str]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

class WarehouseSimulator:
    """
    Simulates stochastic execution in real-time or fast-forward mode:
    - Probabilistic congestion spikes on travel legs
    - Probabilistic battery drain fluctuations
    - Dynamic breakdown hazard evaluation
    - Real-time automatic task rescue and reassignment upon breakdown
    """
    def __init__(self, robots: List[RobotSpec], tasks: List[Task], allocation: Dict[str, List[str]],
                 breakdown_rate_mult: float = 1.0, congestion_level: str = "medium", rng_seed: Optional[int] = None):
        self.robots_spec = {r.id: copy.deepcopy(r) for r in robots}
        self.tasks_spec = {t.id: copy.deepcopy(t) for t in tasks}
        self.initial_allocation = copy.deepcopy(allocation)
        self.breakdown_rate_mult = breakdown_rate_mult
        self.congestion_level = congestion_level
        self.rng = random.Random(rng_seed if rng_seed is not None else int(time.time() * 1000) % 100000)
        
        # Congestion multiplier distributions
        self.congestion_params = {
            "low": {"mean": 0.05, "sigma": 0.08},
            "medium": {"mean": 0.15, "sigma": 0.18},
            "high": {"mean": 0.32, "sigma": 0.30}
        }.get(congestion_level, {"mean": 0.15, "sigma": 0.18})

    def run(self) -> Dict[str, Any]:
        rng = self.rng
        
        # State tracking for each robot
        robot_state = {}
        for r_id, r in self.robots_spec.items():
            robot_state[r_id] = {
                "id": r_id,
                "name": r.name,
                "color": r.color,
                "x": r.init_x,
                "y": r.init_y,
                "battery": r.battery_capacity,
                "battery_max": r.battery_capacity,
                "is_broken": False,
                "breakdown_time": None,
                "total_distance": 0.0,
                "energy_consumed": 0.0,
                "status": "IDLE",
                "assigned_queue": list(self.initial_allocation.get(r_id, [])),
                "completed_tasks": [],
                "current_task": None,
                "trajectory": [{"t": 0.0, "x": r.init_x, "y": r.init_y, "status": "IDLE", "battery": 100.0}]
            }
            
        task_state = {}
        for t_id, t in self.tasks_spec.items():
            assigned_to = None
            for r_id, q in self.initial_allocation.items():
                if t_id in q:
                    assigned_to = r_id
                    break
            task_state[t_id] = {
                "id": t_id,
                "status": "PENDING",
                "assigned_robot": assigned_to,
                "reassigned_from": None,
                "pickup_time": None,
                "delivery_time": None,
                "delay": 0.0,
                "is_late": False
            }
            
        events: List[SimulationEvent] = []
        timeline = 0.0
        active_robots = set(self.robots_spec.keys())
        broken_robots = set()
        reassignments_count = 0
        
        # Robot working clocks
        robot_clock = {r_id: 0.0 for r_id in self.robots_spec}
        
        # Execute until all active queues are processed or remaining tasks are handled
        max_loop_iterations = 200
        iteration = 0
        
        while iteration < max_loop_iterations:
            iteration += 1
            # Find candidate next task across active, non-broken robots
            candidate_events = []
            
            for r_id in active_robots:
                r_data = robot_state[r_id]
                if r_data["is_broken"]:
                    continue
                if not r_data["assigned_queue"]:
                    continue
                
                next_task_id = r_data["assigned_queue"][0]
                task = self.tasks_spec[next_task_id]
                earliest_start = max(robot_clock[r_id], task.arrival_time)
                candidate_events.append((earliest_start, r_id, next_task_id))
                
            if not candidate_events:
                # All queues empty or remaining robots broken
                break
                
            # Process the robot with earliest available work
            candidate_events.sort(key=lambda x: x[0])
            cur_time, r_id, task_id = candidate_events[0]
            
            r_data = robot_state[r_id]
            task = self.tasks_spec[task_id]
            spec = self.robots_spec[r_id]
            
            # Remove from queue to process
            r_data["assigned_queue"].pop(0)
            r_data["current_task"] = task_id
            task_state[task_id]["status"] = "IN_PROGRESS"
            
            # --- PHASE 1: Travel from current position to PICKUP ---
            curr_pos = (r_data["x"], r_data["y"])
            dist_to_pickup = travel_distance(curr_pos, task.pickup)
            
            # Stochastic congestion factor (log-normal)
            cong_shock = max(0.0, rng.gauss(self.congestion_params["mean"], self.congestion_params["sigma"]))
            speed = max(0.6, rng.gauss(spec.base_speed, spec.speed_variance)) / (1.0 + cong_shock)
            travel_time_pickup = dist_to_pickup / speed
            
            pickup_arrival = cur_time + travel_time_pickup
            
            # Check for breakdown during transit to pickup
            # Hazard rate scales with breakdown_rate_mult
            leg_breakdown_prob = 1.0 - math.exp(- spec.base_breakdown_prob * self.breakdown_rate_mult * (dist_to_pickup / 60.0))
            is_breakdown = (rng.random() < leg_breakdown_prob) and (r_id not in broken_robots)
            
            if is_breakdown:
                # Robot breaks down midway to pickup
                fail_fraction = rng.uniform(0.3, 0.8)
                fail_time = cur_time + travel_time_pickup * fail_fraction
                fail_x = round(curr_pos[0] + (task.pickup[0] - curr_pos[0]) * fail_fraction, 1)
                fail_y = round(curr_pos[1] + (task.pickup[1] - curr_pos[1]) * fail_fraction, 1)
                
                r_data["x"] = fail_x
                r_data["y"] = fail_y
                r_data["is_broken"] = True
                r_data["status"] = "BREAKDOWN"
                r_data["breakdown_time"] = fail_time
                broken_robots.add(r_id)
                active_robots.discard(r_id)
                robot_clock[r_id] = fail_time
                
                r_data["trajectory"].append({
                    "t": round(fail_time, 1), "x": fail_x, "y": fail_y,
                    "status": "BREAKDOWN", "battery": round(r_data["battery"] / r_data["battery_max"] * 100, 1)
                })
                
                events.append(SimulationEvent(
                    timestamp=round(fail_time, 1),
                    event_type="BREAKDOWN",
                    robot_id=r_id,
                    task_id=task_id,
                    message=f"CRITICAL: {spec.name} ({r_id}) suffered mechanical breakdown at ({fail_x}, {fail_y})!",
                    details={"coords": [fail_x, fail_y]}
                ))
                
                # Dynamic Reassignment of current task + all remaining queued tasks
                orphan_tasks = [task_id] + r_data["assigned_queue"]
                r_data["assigned_queue"].clear()
                r_data["current_task"] = None
                
                for orphan_id in orphan_tasks:
                    reassigned_to = self._dynamic_reassign_task(
                        orphan_id, fail_time, active_robots, robot_state, task_state, events
                    )
                    if reassigned_to:
                        reassignments_count += 1
                        
                continue # Done with this broken robot
                
            # If no breakdown, arrive at pickup
            r_data["x"] = task.pickup[0]
            r_data["y"] = task.pickup[1]
            r_data["total_distance"] += dist_to_pickup
            energy_pickup = dist_to_pickup * spec.discharge_rate * (1.0 + rng.gauss(0, 0.05))
            r_data["battery"] = max(2.0, r_data["battery"] - energy_pickup)
            r_data["energy_consumed"] += energy_pickup
            
            r_data["trajectory"].append({
                "t": round(pickup_arrival, 1), "x": task.pickup[0], "y": task.pickup[1],
                "status": "PICKUP", "battery": round(r_data["battery"] / r_data["battery_max"] * 100, 1)
            })
            
            task_state[task_id]["pickup_time"] = round(pickup_arrival, 1)
            events.append(SimulationEvent(
                timestamp=round(pickup_arrival, 1),
                event_type="PICKUP",
                robot_id=r_id,
                task_id=task_id,
                message=f"{spec.name} picked up {task.name} ({task_id}) at ({task.pickup[0]}, {task.pickup[1]}).",
                details={"coords": list(task.pickup)}
            ))
            
            # Handling time with variance
            actual_handling = task.handling_time * (1.0 + rng.gauss(0.05, 0.10))
            depart_pickup_time = pickup_arrival + actual_handling
            
            # --- PHASE 2: Travel from PICKUP to DROPOFF ---
            dist_dropoff = travel_distance(task.pickup, task.dropoff)
            cong_shock_drop = max(0.0, rng.gauss(self.congestion_params["mean"], self.congestion_params["sigma"]))
            speed_loaded = max(0.5, rng.gauss(spec.base_speed * 0.95, spec.speed_variance)) / (1.0 + cong_shock_drop)
            travel_time_dropoff = dist_dropoff / speed_loaded
            delivery_arrival = depart_pickup_time + travel_time_dropoff
            
            # Breakdown hazard while carrying load
            load_breakdown_prob = 1.0 - math.exp(- spec.base_breakdown_prob * self.breakdown_rate_mult * (dist_dropoff / 50.0))
            is_breakdown_load = (rng.random() < load_breakdown_prob) and (r_id not in broken_robots)
            
            if is_breakdown_load:
                # Breakdown en route to dropoff
                fail_fraction = rng.uniform(0.2, 0.7)
                fail_time = depart_pickup_time + travel_time_dropoff * fail_fraction
                fail_x = round(task.pickup[0] + (task.dropoff[0] - task.pickup[0]) * fail_fraction, 1)
                fail_y = round(task.pickup[1] + (task.dropoff[1] - task.pickup[1]) * fail_fraction, 1)
                
                r_data["x"] = fail_x
                r_data["y"] = fail_y
                r_data["is_broken"] = True
                r_data["status"] = "BREAKDOWN"
                r_data["breakdown_time"] = fail_time
                broken_robots.add(r_id)
                active_robots.discard(r_id)
                robot_clock[r_id] = fail_time
                
                r_data["trajectory"].append({
                    "t": round(fail_time, 1), "x": fail_x, "y": fail_y,
                    "status": "BREAKDOWN", "battery": round(r_data["battery"] / r_data["battery_max"] * 100, 1)
                })
                
                events.append(SimulationEvent(
                    timestamp=round(fail_time, 1),
                    event_type="BREAKDOWN",
                    robot_id=r_id,
                    task_id=task_id,
                    message=f"CRITICAL: {spec.name} BROKE DOWN carrying payload at ({fail_x}, {fail_y})!",
                    details={"coords": [fail_x, fail_y]}
                ))
                
                # Reassign in-transit task and queued tasks
                orphan_tasks = [task_id] + r_data["assigned_queue"]
                r_data["assigned_queue"].clear()
                r_data["current_task"] = None
                
                for orphan_id in orphan_tasks:
                    reassigned_to = self._dynamic_reassign_task(
                        orphan_id, fail_time, active_robots, robot_state, task_state, events
                    )
                    if reassigned_to:
                        reassignments_count += 1
                        
                continue
                
            # Successful dropoff
            r_data["x"] = task.dropoff[0]
            r_data["y"] = task.dropoff[1]
            r_data["total_distance"] += dist_dropoff
            energy_drop = dist_dropoff * spec.discharge_rate * (1.0 + task.payload_kg / 120.0) * (1.0 + rng.gauss(0, 0.05))
            r_data["battery"] = max(1.0, r_data["battery"] - energy_drop)
            r_data["energy_consumed"] += energy_drop
            r_data["completed_tasks"].append(task_id)
            r_data["current_task"] = None
            
            task_state[task_id]["status"] = "COMPLETED"
            task_state[task_id]["delivery_time"] = round(delivery_arrival, 1)
            task_state[task_id]["delay"] = max(0.0, round(delivery_arrival - task.deadline, 1))
            task_state[task_id]["is_late"] = delivery_arrival > task.deadline
            
            r_data["trajectory"].append({
                "t": round(delivery_arrival, 1), "x": task.dropoff[0], "y": task.dropoff[1],
                "status": "DELIVERY", "battery": round(r_data["battery"] / r_data["battery_max"] * 100, 1)
            })
            
            events.append(SimulationEvent(
                timestamp=round(delivery_arrival, 1),
                event_type="DELIVERY",
                robot_id=r_id,
                task_id=task_id,
                message=f"{spec.name} successfully delivered {task.name} ({task_id}) at ({task.dropoff[0]}, {task.dropoff[1]})." +
                        (" [LATE]" if task_state[task_id]["is_late"] else " [ON-TIME]"),
                details={"coords": list(task.dropoff), "delay": task_state[task_id]["delay"]}
            ))
            
            # --- PHASE 3: Check Battery & Auto-Recharge if below 20% ---
            battery_pct = r_data["battery"] / r_data["battery_max"]
            finish_time = delivery_arrival
            
            if battery_pct < 0.20 and len(r_data["assigned_queue"]) > 0:
                # Seek nearest charging station
                nearest_cs = min(CHARGING_STATIONS, key=lambda cs: travel_distance((r_data["x"], r_data["y"]), (cs["x"], cs["y"])))
                dist_to_cs = travel_distance((r_data["x"], r_data["y"]), (nearest_cs["x"], nearest_cs["y"]))
                charge_transit_time = dist_to_cs / spec.base_speed
                charge_start = delivery_arrival + charge_transit_time
                
                # Charge back to 85%
                needed_energy = (r_data["battery_max"] * 0.85) - r_data["battery"]
                recharge_duration = needed_energy * 1.5 # 1.5s per kWh fast-charge rate
                charge_finish = charge_start + recharge_duration
                
                r_data["x"] = nearest_cs["x"]
                r_data["y"] = nearest_cs["y"]
                r_data["battery"] = r_data["battery_max"] * 0.85
                r_data["status"] = "CHARGING"
                
                r_data["trajectory"].append({
                    "t": round(charge_finish, 1), "x": nearest_cs["x"], "y": nearest_cs["y"],
                    "status": "CHARGED", "battery": 85.0
                })
                
                events.append(SimulationEvent(
                    timestamp=round(charge_start, 1),
                    event_type="RECHARGE_START",
                    robot_id=r_id,
                    task_id=None,
                    message=f"{spec.name} low battery ({round(battery_pct*100, 1)}%). Fast charging at {nearest_cs['name']}.",
                    details={"station": nearest_cs["name"]}
                ))
                finish_time = charge_finish
                
            robot_clock[r_id] = finish_time
            
        # Simulation finished - calculate summary metrics
        completion_times = [ts["delivery_time"] for ts in task_state.values() if ts["delivery_time"] is not None]
        realized_makespan = max(completion_times) if completion_times else 0.0
        
        completed_tasks_count = sum(1 for ts in task_state.values() if ts["status"] == "COMPLETED")
        on_time_count = sum(1 for ts in task_state.values() if ts["status"] == "COMPLETED" and not ts["is_late"])
        on_time_rate = round((on_time_count / len(self.tasks_spec)) * 100, 1)
        total_delay = round(sum(ts["delay"] for ts in task_state.values()), 1)
        total_energy = round(sum(rd["energy_consumed"] for rd in robot_state.values()), 2)
        total_distance = round(sum(rd["total_distance"] for rd in robot_state.values()), 1)
        
        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)
        
        return {
            "makespan": round(realized_makespan, 1),
            "completed_tasks": completed_tasks_count,
            "total_tasks": len(self.tasks_spec),
            "on_time_rate": on_time_rate,
            "total_delay": total_delay,
            "total_energy_kwh": total_energy,
            "total_distance_m": total_distance,
            "breakdowns_count": len(broken_robots),
            "reassignments_count": reassignments_count,
            "broken_robots": list(broken_robots),
            "robot_states": {r_id: {
                "id": r_id,
                "name": rd["name"],
                "color": rd["color"],
                "battery": round(rd["battery"], 1),
                "battery_pct": round(rd["battery"] / rd["battery_max"] * 100, 1),
                "is_broken": rd["is_broken"],
                "breakdown_time": rd["breakdown_time"],
                "total_distance": round(rd["total_distance"], 1),
                "energy_consumed": round(rd["energy_consumed"], 2),
                "completed_count": len(rd["completed_tasks"]),
                "trajectory": rd["trajectory"]
            } for r_id, rd in robot_state.items()},
            "task_states": task_state,
            "events": [asdict(e) for e in events]
        }

    def _dynamic_reassign_task(self, task_id: str, event_time: float, active_robots: set,
                               robot_state: dict, task_state: dict, events: List[SimulationEvent]) -> Optional[str]:
        """
        Dynamically rescues an orphaned task by assigning it to the most suitable active robot.
        Considers distance from candidate robot to pickup, remaining battery, and current queue load.
        """
        task = self.tasks_spec[task_id]
        best_robot = None
        best_score = float("inf")
        
        for cand_id in active_robots:
            c_data = robot_state[cand_id]
            if c_data["is_broken"]:
                continue
                
            dist_to_task = travel_distance((c_data["x"], c_data["y"]), task.pickup)
            queue_len = len(c_data["assigned_queue"])
            battery_pct = c_data["battery"] / c_data["battery_max"]
            
            # Penalize low battery and long queues
            score = dist_to_task * 1.0 + (queue_len * 35.0) + ((1.0 - battery_pct) * 80.0)
            if score < best_score:
                best_score = score
                best_robot = cand_id
                
        if best_robot:
            robot_state[best_robot]["assigned_queue"].append(task_id)
            orig_robot = task_state[task_id]["assigned_robot"]
            task_state[task_id]["reassigned_from"] = orig_robot
            task_state[task_id]["assigned_robot"] = best_robot
            task_state[task_id]["status"] = "REASSIGNED"
            
            events.append(SimulationEvent(
                timestamp=round(event_time + 1.0, 1),
                event_type="REASSIGN",
                robot_id=best_robot,
                task_id=task_id,
                message=f"RESCUE: Task {task.name} ({task_id}) dynamically reassigned from {orig_robot} to {self.robots_spec[best_robot].name} ({best_robot}).",
                details={"from_robot": orig_robot, "to_robot": best_robot}
            ))
            return best_robot
        return None


# ==============================================================================
# MONTE CARLO & SENSITIVITY ANALYSIS ENGINES
# ==============================================================================

class MonteCarloEngine:
    @staticmethod
    def run_comparison(scenarios: int = 100, breakdown_mult: float = 1.0, congestion: str = "medium", base_seed: int = 42) -> Dict[str, Any]:
        tasks = generate_default_tasks(seed=base_seed)
        robots = ROBOT_CATALOG
        
        # 1. Compute both static allocations
        det_alloc = DeterministicOptimizer.allocate(robots, tasks)
        stoch_alloc = StochasticOptimizer.allocate(robots, tasks, breakdown_mult=breakdown_mult)
        
        det_results = []
        stoch_results = []
        stoch_wins = 0
        
        for i in range(scenarios):
            scenario_seed = base_seed + 1000 + i
            
            # Run Deterministic policy on scenario i
            sim_det = WarehouseSimulator(
                robots, tasks, det_alloc,
                breakdown_rate_mult=breakdown_mult,
                congestion_level=congestion,
                rng_seed=scenario_seed
            )
            res_det = sim_det.run()
            
            # Run Stochastic policy on EXACT SAME scenario i
            sim_stoch = WarehouseSimulator(
                robots, tasks, stoch_alloc,
                breakdown_rate_mult=breakdown_mult,
                congestion_level=congestion,
                rng_seed=scenario_seed
            )
            res_stoch = sim_stoch.run()
            
            det_results.append(res_det)
            stoch_results.append(res_stoch)
            
            if res_stoch["makespan"] <= res_det["makespan"]:
                stoch_wins += 1
                
        # Statistical aggregation
        det_makespans = [r["makespan"] for r in det_results]
        stoch_makespans = [r["makespan"] for r in stoch_results]
        
        det_on_time = [r["on_time_rate"] for r in det_results]
        stoch_on_time = [r["on_time_rate"] for r in stoch_results]
        
        det_delays = [r["total_delay"] for r in det_results]
        stoch_delays = [r["total_delay"] for r in stoch_results]
        
        det_reassigns = [r["reassignments_count"] for r in det_results]
        stoch_reassigns = [r["reassignments_count"] for r in stoch_results]
        
        # Histograms for Chart.js
        min_span = min(min(det_makespans), min(stoch_makespans))
        max_span = max(max(det_makespans), max(stoch_makespans))
        bins = np.linspace(min_span - 10, max_span + 10, 15)
        
        det_hist, _ = np.histogram(det_makespans, bins=bins)
        stoch_hist, _ = np.histogram(stoch_makespans, bins=bins)
        bin_labels = [f"{int(bins[k])}-{int(bins[k+1])}s" for k in range(len(bins)-1)]
        
        return {
            "scenarios_count": scenarios,
            "stochastic_win_rate_pct": round((stoch_wins / scenarios) * 100, 1),
            "deterministic": {
                "makespan_mean": round(float(np.mean(det_makespans)), 1),
                "makespan_std": round(float(np.std(det_makespans)), 1),
                "makespan_median": round(float(np.median(det_makespans)), 1),
                "makespan_p95": round(float(np.percentile(det_makespans, 95)), 1),
                "makespan_min": round(float(np.min(det_makespans)), 1),
                "makespan_max": round(float(np.max(det_makespans)), 1),
                "on_time_mean": round(float(np.mean(det_on_time)), 1),
                "delay_mean": round(float(np.mean(det_delays)), 1),
                "reassigns_mean": round(float(np.mean(det_reassigns)), 2),
                "samples": [round(x, 1) for x in det_makespans]
            },
            "stochastic": {
                "makespan_mean": round(float(np.mean(stoch_makespans)), 1),
                "makespan_std": round(float(np.std(stoch_makespans)), 1),
                "makespan_median": round(float(np.median(stoch_makespans)), 1),
                "makespan_p95": round(float(np.percentile(stoch_makespans, 95)), 1),
                "makespan_min": round(float(np.min(stoch_makespans)), 1),
                "makespan_max": round(float(np.max(stoch_makespans)), 1),
                "on_time_mean": round(float(np.mean(stoch_on_time)), 1),
                "delay_mean": round(float(np.mean(stoch_delays)), 1),
                "reassigns_mean": round(float(np.mean(stoch_reassigns)), 2),
                "samples": [round(x, 1) for x in stoch_makespans]
            },
            "histogram": {
                "bins": bin_labels,
                "deterministic_counts": det_hist.tolist(),
                "stochastic_counts": stoch_hist.tolist()
            }
        }


class SensitivityEngine:
    @staticmethod
    def run_sweep(rates: Optional[List[float]] = None, iterations_per_rate: int = 25, base_seed: int = 100) -> Dict[str, Any]:
        if rates is None:
            rates = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]
            
        tasks = generate_default_tasks(seed=base_seed)
        robots = ROBOT_CATALOG
        
        curve_det_makespan = []
        curve_stoch_makespan = []
        curve_det_delay = []
        curve_stoch_delay = []
        curve_det_ontime = []
        curve_stoch_ontime = []
        
        for r_prob in rates:
            mult = r_prob / 0.04 if r_prob > 0 else 0.0
            det_alloc = DeterministicOptimizer.allocate(robots, tasks)
            stoch_alloc = StochasticOptimizer.allocate(robots, tasks, breakdown_mult=max(0.2, mult))
            
            d_spans = []
            s_spans = []
            d_delays = []
            s_delays = []
            d_ontimes = []
            s_ontimes = []
            
            for it in range(iterations_per_rate):
                s_seed = base_seed + int(r_prob * 1000) + it * 7
                
                # Det run
                res_d = WarehouseSimulator(robots, tasks, det_alloc, breakdown_rate_mult=mult, congestion_level="medium", rng_seed=s_seed).run()
                d_spans.append(res_d["makespan"])
                d_delays.append(res_d["total_delay"])
                d_ontimes.append(res_d["on_time_rate"])
                
                # Stoch run
                res_s = WarehouseSimulator(robots, tasks, stoch_alloc, breakdown_rate_mult=mult, congestion_level="medium", rng_seed=s_seed).run()
                s_spans.append(res_s["makespan"])
                s_delays.append(res_s["total_delay"])
                s_ontimes.append(res_s["on_time_rate"])
                
            curve_det_makespan.append(round(float(np.mean(d_spans)), 1))
            curve_stoch_makespan.append(round(float(np.mean(s_spans)), 1))
            curve_det_delay.append(round(float(np.mean(d_delays)), 1))
            curve_stoch_delay.append(round(float(np.mean(s_delays)), 1))
            curve_det_ontime.append(round(float(np.mean(d_ontimes)), 1))
            curve_stoch_ontime.append(round(float(np.mean(s_ontimes)), 1))
            
        return {
            "rates": rates,
            "rate_labels": [f"{int(r*100)}%" for r in rates],
            "deterministic_makespan": curve_det_makespan,
            "stochastic_makespan": curve_stoch_makespan,
            "deterministic_delay": curve_det_delay,
            "stochastic_delay": curve_stoch_delay,
            "deterministic_ontime": curve_det_ontime,
            "stochastic_ontime": curve_stoch_ontime
        }


# ==============================================================================
# FLASK WEB ROUTES
# ==============================================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    tasks = generate_default_tasks(DEFAULT_SEED)
    return jsonify({
        "warehouse": {
            "width": WAREHOUSE_WIDTH,
            "height": WAREHOUSE_HEIGHT,
            "charging_stations": CHARGING_STATIONS
        },
        "robots": [asdict(r) for r in ROBOT_CATALOG],
        "tasks": [asdict(t) for t in tasks]
    })

@app.route("/api/simulate", methods=["POST"])
def simulate():
    data = request.get_json() or {}
    strategy = data.get("strategy", "stochastic") # "stochastic", "deterministic", "compare"
    breakdown_rate = float(data.get("breakdown_rate", 0.05))
    congestion = data.get("congestion", "medium")
    seed = int(data.get("seed", DEFAULT_SEED))
    
    mult = breakdown_rate / 0.04
    tasks = generate_default_tasks(seed=seed)
    robots = ROBOT_CATALOG
    
    if strategy == "compare":
        det_alloc = DeterministicOptimizer.allocate(robots, tasks)
        stoch_alloc = StochasticOptimizer.allocate(robots, tasks, breakdown_mult=max(0.1, mult))
        
        sim_seed = seed + 555
        det_res = WarehouseSimulator(robots, tasks, det_alloc, breakdown_rate_mult=mult, congestion_level=congestion, rng_seed=sim_seed).run()
        stoch_res = WarehouseSimulator(robots, tasks, stoch_alloc, breakdown_rate_mult=mult, congestion_level=congestion, rng_seed=sim_seed).run()
        
        return jsonify({
            "mode": "compare",
            "deterministic_allocation": det_alloc,
            "stochastic_allocation": stoch_alloc,
            "deterministic_result": det_res,
            "stochastic_result": stoch_res,
            "summary": {
                "makespan_diff": round(det_res["makespan"] - stoch_res["makespan"], 1),
                "makespan_improvement_pct": round(((det_res["makespan"] - stoch_res["makespan"]) / max(1.0, det_res["makespan"])) * 100, 1),
                "delay_diff": round(det_res["total_delay"] - stoch_res["total_delay"], 1),
                "on_time_diff": round(stoch_res["on_time_rate"] - det_res["on_time_rate"], 1)
            }
        })
    else:
        if strategy == "deterministic":
            alloc = DeterministicOptimizer.allocate(robots, tasks)
        else:
            alloc = StochasticOptimizer.allocate(robots, tasks, breakdown_mult=max(0.1, mult))
            
        sim = WarehouseSimulator(robots, tasks, alloc, breakdown_rate_mult=mult, congestion_level=congestion, rng_seed=seed + 777)
        res = sim.run()
        return jsonify({
            "mode": "single",
            "strategy": strategy,
            "allocation": alloc,
            "result": res
        })

@app.route("/api/monte-carlo", methods=["POST"])
def monte_carlo():
    data = request.get_json() or {}
    scenarios = min(200, max(20, int(data.get("scenarios", 100))))
    breakdown_rate = float(data.get("breakdown_rate", 0.05))
    congestion = data.get("congestion", "medium")
    seed = int(data.get("seed", 42))
    
    mult = breakdown_rate / 0.04
    mc_results = MonteCarloEngine.run_comparison(
        scenarios=scenarios,
        breakdown_mult=mult,
        congestion=congestion,
        base_seed=seed
    )
    return jsonify(mc_results)

@app.route("/api/sensitivity", methods=["POST"])
def sensitivity():
    data = request.get_json() or {}
    iterations = min(50, max(10, int(data.get("iterations", 25))))
    seed = int(data.get("seed", 100))
    
    res = SensitivityEngine.run_sweep(iterations_per_rate=iterations, base_seed=seed)
    return jsonify(res)

if __name__ == "__main__":
    print("=" * 70)
    print("[*] RoboFlow - Stochastic Warehouse Robot Task Allocation Server")
    print("[*] Local Web Dashboard: http://127.0.0.1:5000")
    print("=" * 70)
    app.run(host="127.0.0.1", port=5000, debug=True)
