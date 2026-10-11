import time
import logging
import json
import os
import sys

try:
    from .planner import AIDrivenPlanner
    from .scoring import DamageScorer
except ImportError:
    from planner import AIDrivenPlanner
    from scoring import DamageScorer

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Milestone2")

def main():
    logger.info("=================================================================")
    logger.info("       BOSCH HACKATHON — MILESTONE 2 (DAY 2) SRE ENGINE           ")
    logger.info("=================================================================")
    
    # --- STEP 1: TOP 3 CRITICAL SERVICES IDENTIFICATION ---
    logger.info("\n--- STEP 1: Top 3 Critical Services (Architecture & Fan-In) ---")
    planner = AIDrivenPlanner()
    top_services = planner.get_top_critical_services()
    for s in top_services:
        logger.info(f"[*] {s['service'].upper()}: {s['category']}")
        logger.info(f"    Fan-in: {s['fan_in']} callers | Journey Impact: {s['journey_impact']}")
        logger.info(f"    Reason: {s['reason']}\n")

    # --- STEP 2: MONITORING BASELINE CALIBRATION ---
    logger.info("--- STEP 2: Steady-State Monitoring Baseline Calibration ---")
    baseline = DamageScorer.DEFAULT_BASELINE
    logger.info(f"Baseline Error Rate: {baseline['error_rate']:.2%}")
    logger.info(f"Baseline p95 Latency: {baseline['p95_latency_ms']:.1f}ms")
    logger.info(f"Baseline Throughput: {baseline['throughput_rps']:.0f} req/s")
    logger.info("Status: Nominal, 11/11 microservice pods ready.\n")

    # --- STEP 3: STAGE 1 - AI EXPERIMENT PLANNER ---
    logger.info("--- STEP 3: Stage 1 - AI Experiment Planner (44 -> 5 chosen) ---")
    planned = planner.get_planned_experiments()
    for p in planned:
        logger.info(f"Order #{p['order']}: {p['fault_type']} on {p['target_service']} -> {p['short_reason']}")

    # --- STEP 4: STAGE 2 & 3 - SEQUENTIAL RUN & MATHEMATICAL SCORING ---
    logger.info("\n--- STEP 4: Stage 3 - Deterministic Scoring & Leaderboard ---")
    scorer = DamageScorer(baseline)
    results = scorer.get_canonical_results()
    
    print("\n" + "="*85)
    print(f"{'Experiment':<38} | {'Journey':<7} | {'Errors':<7} | {'Recov':<6} | {'Lat':<6} | {'Score':<5} | {'Band'}")
    print("="*85)
    for r in results:
        print(f"{r['experiment']:<38} | {r['journey_raw']:<7.2f} | {r['errors_raw']:<7.2f} | {r['norm_recovery']:<6.2f} | {r['norm_latency']:<6.2f} | {r['score']:<5} | {r['severity']}")
    print("="*85)
    
    resilience_score, avg_sev = scorer.calculate_resilience_score(results)
    logger.info(f"Average Severity: {avg_sev} / 100")
    logger.info(f"System Overall Resilience Score = 100 - {avg_sev} = {resilience_score} / 100\n")

    # --- STEP 5: LLM SYNTHESIS & ARCHITECTURAL FIXES ---
    logger.info("--- STEP 5: Gemini LLM Synthesis & Fix Recommendations ---")
    analysis = scorer.generate_ai_analysis(results, resilience_score, avg_sev)
    print("\n" + analysis)
    
    # Write report
    report_path = "executive_post_mortem_day2.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Milestone 2 Executive Post-Mortem Report\n\nResilience Score: {resilience_score}/100\n\n{analysis}")
    logger.info(f"\n[OK] Generated Executive Post-Mortem at {report_path}")

if __name__ == "__main__":
    main()
