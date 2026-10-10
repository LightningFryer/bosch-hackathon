import time
import logging
import json
import os
import sys

from topology import discover_topology
from load_harness import LoadHarness
from chaos_engine import ChaosEngine
from planner import AIDrivenPlanner
from scoring import ResilienceAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Milestone1")

def main():
    # Setup paths - expecting to be run from Bosch-Hackathon root or chaos_system dir
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base_dir, "microservices-demo", "release", "kubernetes-manifests.yaml")
    
    if not os.path.exists(manifest_path):
        logger.error(f"Cannot find manifest at {manifest_path}. Have you cloned the microservices-demo repo?")
        sys.exit(1)

    logger.info("=== STEP 1: Topology Discovery ===")
    graph = discover_topology(manifest_path)
    logger.info(f"Discovered {len(graph)} services.")
    print(json.dumps(graph, indent=2))
    
    logger.info("=== STEP 2: Establish Baseline Load ===")
    # Note: Assumes frontend is port-forwarded to localhost:8080 or available there
    target_url = os.environ.get("FRONTEND_URL", "http://localhost:8080")
    logger.info(f"Starting load harness targeting {target_url}...")
    
    harness = LoadHarness(target_url)
    harness.start(concurrency=3)
    
    # Warmup and baseline collection
    logger.info("Warming up for 10 seconds to establish baseline...")
    time.sleep(10)
    baseline_metrics = harness.get_metrics()
    logger.info(f"Baseline Metrics: {baseline_metrics}")
    
    logger.info("=== STEP 3: Planning Experiment ===")
    planner = AIDrivenPlanner(graph)
    plan = planner.generate_experiment_plan()
    
    # Force target to cartservice for milestone 1 as requested
    plan["target_service"] = "cartservice"
    logger.info(f"Experiment Plan: {json.dumps(plan, indent=2)}")

    logger.info("=== STEP 4: Chaos Injection Engine with Kill-Switch ===")
    engine = ChaosEngine(harness)
    
    # This will block and run the experiment, triggering kill switch if needed
    engine.inject_container_kill(
        service_name=plan["target_service"],
        duration_seconds=plan["duration_seconds"],
        error_threshold=plan["safety_abort_criteria"]["max_error_rate"],
        latency_multiplier=plan["safety_abort_criteria"]["max_latency_multiplier"]
    )
    
    fault_metrics = harness.get_metrics()
    logger.info(f"Fault Metrics: {fault_metrics}")
    
    logger.info("Stopping load harness...")
    harness.stop()
    
    logger.info("=== STEP 5: Resilience Analysis & Scoring ===")
    analyzer = ResilienceAnalyzer(baseline_metrics, fault_metrics)
    report = analyzer.generate_report(plan)
    
    report_path = "executive_post_mortem.md"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Generated Executive Post-Mortem at {report_path}")
    print("\n" + report)

    logger.info("=== STEP 6: AI-Driven Recommendations ===")
    logger.info("Consulting Gemini for fixes...")
    recs = analyzer.generate_ai_recommendations(report)
    
    recs_path = "ai_recommendations.md"
    with open(recs_path, "w") as f:
        f.write(recs)
    logger.info(f"Generated AI Recommendations at {recs_path}")
    print("\n" + recs)

if __name__ == "__main__":
    main()
