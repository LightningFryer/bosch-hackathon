import os
import json
from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    genai = None

load_dotenv()

class DamageScorer:
    """
    Stage 3: Scientific Scoring Engine
    Deterministically computes damage, severity, and overall resilience score
    using the formal mathematical formula:
    
    severity = 100 * (0.35 * journey + 0.25 * errors + 0.20 * recovery + 0.20 * latency)
    
    Resilience Score = 100 - average(severity)
    """

    SEVERITY_WEIGHTS = {
        "journey": 0.35,
        "errors": 0.25,
        "recovery": 0.20,
        "latency": 0.20
    }

    # Reference baseline measurements (Online Boutique under normal load)
    DEFAULT_BASELINE = {
        "error_rate": 0.005,    # 0.5% normal failure rate
        "p95_latency_ms": 92.0, # 92ms p95 baseline
        "p50_latency_ms": 45.0,
        "p99_latency_ms": 115.0,
        "throughput_rps": 240.0
    }

    def __init__(self, baseline=None):
        self.baseline = baseline or self.DEFAULT_BASELINE
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.model_name = 'gemini-2.5-flash'
            except Exception:
                self.client = None

    @classmethod
    def calculate_severity(cls, journey_impact, error_rate, recovery_seconds, latency_multiplier):
        """
        Calculates severity for a single experiment:
        - journey_impact: normalized 0-1 (Browse=0.3, Cart=0.2, Checkout=0.5; broken=full, degraded=half)
        - error_rate: normalized 0-1 (% failed requests)
        - recovery_seconds: recovery back to baseline in seconds, normalized as recovery / 120s (capped at 1.0)
        - latency_multiplier: (fault p95 / baseline p95), normalized as latency_multiplier / 10 (capped at 1.0)
        """
        norm_journey = min(1.0, max(0.0, float(journey_impact)))
        norm_errors = min(1.0, max(0.0, float(error_rate)))
        norm_recovery = min(1.0, max(0.0, float(recovery_seconds) / 120.0))
        norm_latency = min(1.0, max(0.0, float(latency_multiplier) / 10.0))

        raw_score = (
            cls.SEVERITY_WEIGHTS["journey"] * norm_journey +
            cls.SEVERITY_WEIGHTS["errors"] * norm_errors +
            cls.SEVERITY_WEIGHTS["recovery"] * norm_recovery +
            cls.SEVERITY_WEIGHTS["latency"] * norm_latency
        )
        
        # Standard round-half-up to match hackathon example (0.745 -> 75)
        severity_score = int(raw_score * 100 + 0.5)
        
        if severity_score >= 70:
            band = "Critical"
        elif severity_score >= 40:
            band = "High"
        elif severity_score >= 15:
            band = "Medium"
        else:
            band = "Low"

        return {
            "score": severity_score,
            "severity_band": band,
            "norm_journey": norm_journey,
            "norm_errors": norm_errors,
            "norm_recovery": norm_recovery,
            "norm_latency": norm_latency
        }

    @classmethod
    def get_canonical_results(cls):
        """
        Returns the worked benchmark experiments matching the specification:
        1. Crash productcatalogservice
        2. CPU saturation frontend
        3. Crash cartservice
        4. 2s latency checkoutservice
        5. 30% packet loss recommendationservice
        """
        experiments = [
            {
                "experiment": "Crash productcatalogservice",
                "target": "productcatalogservice",
                "fault": "Container Crash (SIGKILL)",
                "journey_desc": "1.0 (all broken)",
                "journey_raw": 1.0,
                "errors_desc": "90%",
                "errors_raw": 0.90,
                "recovery_desc": "30 s → 0.25",
                "recovery_raw": 30,
                "latency_desc": "6x → 0.6",
                "latency_raw": 6.0,
                "planner_predicted_rank": 1
            },
            {
                "experiment": "CPU saturation frontend",
                "target": "frontend",
                "fault": "CPU Saturation",
                "journey_desc": "0.5 (all degraded)",
                "journey_raw": 0.5,
                "errors_desc": "25%",
                "errors_raw": 0.25,
                "recovery_desc": "45 s → 0.38",
                "recovery_raw": 45,
                "latency_desc": "≥10x → 1.0",
                "latency_raw": 10.0,
                "planner_predicted_rank": 2
            },
            {
                "experiment": "Crash cartservice",
                "target": "cartservice",
                "fault": "Container Crash (SIGKILL)",
                "journey_desc": "0.7 (cart + checkout)",
                "journey_raw": 0.7,
                "errors_desc": "35%",
                "errors_raw": 0.35,
                "recovery_desc": "40 s → 0.33",
                "recovery_raw": 40,
                "latency_desc": "1.2x → 0.12",
                "latency_raw": 1.2,
                "planner_predicted_rank": 3
            },
            {
                "experiment": "2s latency checkoutservice",
                "target": "checkoutservice",
                "fault": "Network Latency (+2s)",
                "journey_desc": "0.25 (checkout degraded)",
                "journey_raw": 0.25,
                "errors_desc": "20%",
                "errors_raw": 0.20,
                "recovery_desc": "10 s → 0.08",
                "recovery_raw": 10,
                "latency_desc": "8x → 0.83",
                "latency_raw": 8.3,
                "planner_predicted_rank": 4
            },
            {
                "experiment": "30% packet loss recommendationservice",
                "target": "recommendationservice",
                "fault": "Packet Loss (30%)",
                "journey_desc": "0.08 (non-critical degraded)",
                "journey_raw": 0.08,
                "errors_desc": "3%",
                "errors_raw": 0.03,
                "recovery_desc": "5 s → 0.04",
                "recovery_raw": 5,
                "latency_desc": "3x → 0.3",
                "latency_raw": 3.0,
                "planner_predicted_rank": 5
            }
        ]

        scored = []
        for exp in experiments:
            metrics = cls.calculate_severity(
                journey_impact=exp["journey_raw"],
                error_rate=exp["errors_raw"],
                recovery_seconds=exp["recovery_raw"],
                latency_multiplier=exp["latency_raw"]
            )
            item = dict(exp)
            item["score"] = metrics["score"]
            item["severity"] = metrics["severity_band"]
            item["norm_journey"] = metrics["norm_journey"]
            item["norm_errors"] = metrics["norm_errors"]
            item["norm_recovery"] = metrics["norm_recovery"]
            item["norm_latency"] = metrics["norm_latency"]
            scored.append(item)

        # Sort by damage score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    @classmethod
    def calculate_resilience_score(cls, scored_results):
        if not scored_results:
            return 100
        avg_severity = sum(r["score"] for r in scored_results) / len(scored_results)
        resilience = max(0, min(100, round(100 - avg_severity)))
        return resilience, round(avg_severity, 1)

    def generate_ai_analysis(self, scored_results, resilience_score, avg_severity):
        """Uses Gemini to explain rankings, suggest fixes, and compare predictions vs reality."""
        if not self.client:
            return self._fallback_ai_analysis(scored_results, resilience_score)

        prompt = f"""
You are an expert SRE and Chaos Engineering Evaluator judging a Kubernetes microservices resilience suite (Google Online Boutique).
The benchmark experiments and measured damage scores (computed deterministically via mathematical formula) are:

{json.dumps(scored_results, indent=2)}

Overall Resilience Score: {resilience_score}/100 (Average Severity: {avg_severity}).

Please generate the final Day 2 AI Ranked Post-Mortem Report covering:
1. Executive Summary & Resilience Health Verdict
2. Plain-Language Explanation of Findings (Explain why each finding ranked where it did, from #1 to #5)
3. Confirmation of Severity Labels
4. Planner Predictions vs Measured Reality (Highlight any nuances, e.g., CPU latency saturation vs immediate container crashes)
5. Actionable Architectural Fixes (Provide concrete engineering solutions with Istio VirtualService / DestinationRule and Kubernetes configurations)

Format with rich Markdown headings and bullet points. Do not include markdown wrapper blocks.
"""
        for model in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return response.text.strip()
            except Exception:
                continue

        return self._fallback_ai_analysis(scored_results, resilience_score)

    def _fallback_ai_analysis(self, scored_results, resilience_score):
        """Generates a dynamic post-mortem from scored_results without an LLM."""
        status_verdict = (
            "CRITICAL VULNERABILITY (Severe Cascade Risks)" if resilience_score < 60
            else "MODERATE RESILIENCE (Contains Isolated Failures)" if resilience_score < 80
            else "HIGHLY RESILIENT (Autonomous Self-Healing Active)"
        )

        findings_md = []
        for rank, r in enumerate(scored_results, 1):
            exp_name = r.get("experiment", r.get("target", f"Experiment #{rank}"))
            score = r.get("score", 0)
            sev = r.get("severity", "Medium")
            j_desc = r.get("journey_desc", f"{r.get('journey_raw', 0)}")
            e_desc = r.get("errors_desc", f"{r.get('errors_raw', 0):.1%}")
            rec_desc = r.get("recovery_desc", f"{r.get('recovery_raw', 0)}s")
            lat_desc = r.get("latency_desc", f"{r.get('latency_raw', 1.0)}x")
            findings_md.append(
                f"{rank}. **#{rank} {sev} — {exp_name} (Score: {score}/100)**\n"
                f"   - Journey: {j_desc} | Errors: {e_desc} | Recovery: {rec_desc} | Latency: {lat_desc}"
            )
        findings_text = "\n".join(findings_md)

        # Dynamic prediction vs reality: compare planner_predicted_rank vs actual rank
        pred_mismatches = []
        for actual_rank, r in enumerate(scored_results, 1):
            predicted = r.get("planner_predicted_rank", actual_rank)
            if predicted != actual_rank:
                pred_mismatches.append(
                    f"  - `{r.get('target', r.get('experiment', '?'))}`: predicted #{predicted}, measured #{actual_rank}"
                )
        pred_text = (
            "\n".join(pred_mismatches)
            if pred_mismatches
            else "  - All 5 experiments ranked exactly as predicted — confirms the AI planner's dependency-graph analysis was accurate."
        )

        return f"""### 📋 SRE Architectural Post-Mortem & Remediation (Deterministic Analysis)

#### 1. Executive Summary & Resilience Health Verdict
- **System Resilience Score**: **{resilience_score} / 100**
- **Evaluation Status**: **{status_verdict}**
- The automated chaos run evaluated the microservice dependency graph under fault injection, quantifying blast radii and cascade vulnerabilities across customer user journeys.

#### 2. Plain-Language Analysis of Ranked Findings
{findings_text}

#### 3. Prediction vs Reality Comparison
- **Planner Prediction**: Ranked experiments by fan-in × journey weight heuristic before any faults were run.
- **Measured Outcome**:
{pred_text}

#### 4. Actionable Architectural Fixes

```yaml
# 1. Istio DestinationRule: Circuit Breaking & Outlier Detection for Product Catalog
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: productcatalogservice-circuit-breaker
spec:
  host: productcatalogservice
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 10
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutive5xxErrors: 3
      interval: 5s
      baseEjectionTime: 30s
      maxEjectionPercent: 100
---
# 2. Horizontal Pod Autoscaler (HPA) for Frontend Ingress
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 65
---
# 3. PodDisruptionBudget for cartservice (prevents total loss during node drain)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: cartservice-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: cartservice
```
"""


class ResilienceAnalyzer:
    """
    Backwards-compatible Milestone 1 analyzer API.

    Milestone 2 introduced DamageScorer for ranked multi-experiment analysis.
    The original workflow still needs a single-experiment report generator and
    recommendation hook, so this wrapper preserves that contract.
    """

    def __init__(self, baseline_metrics, fault_metrics):
        self.baseline = baseline_metrics or {}
        self.fault = fault_metrics or {}
        self.scorer = DamageScorer()

    def generate_report(self, plan):
        baseline_error = float(self.baseline.get("error_rate", 0.0))
        fault_error = float(self.fault.get("error_rate", 0.0))
        baseline_p99 = float(self.baseline.get("p99", self.baseline.get("p99_latency_ms", 0.0)))
        fault_p99 = float(self.fault.get("p99", self.fault.get("p99_latency_ms", 0.0)))

        availability_retention = max(0.0, 100.0 * (1.0 - fault_error))
        abort_criteria = plan.get("safety_abort_criteria", {})
        error_limit = float(abort_criteria.get("max_error_rate", 0.15))
        latency_limit = float(abort_criteria.get("max_latency_multiplier", 3.0))
        latency_multiplier = (fault_p99 / baseline_p99) if baseline_p99 > 0 else 1.0

        mttr_score = 100
        if fault_error > error_limit or latency_multiplier > latency_limit:
            mttr_score = 50

        score = (availability_retention * 0.7) + (mttr_score * 0.3)
        if score > 90:
            system_health = "HEALTHY"
        elif score >= 70:
            system_health = "DEGRADED"
        else:
            system_health = "CRITICAL"

        target_service = plan.get("target_service", "unknown")
        fault_type = plan.get("fault_type", "unknown")
        hypothesis = plan.get("hypothesis", "No hypothesis provided.")

        return f"""# Executive Post-Mortem: Resilience Experiment

## Experiment Details
- **Target Service**: {target_service}
- **Fault Type**: {fault_type}
- **Hypothesis**: {hypothesis}

## Telemetry Comparison
| Metric | Baseline | During Fault |
|--------|----------|--------------|
| Error Rate | {baseline_error:.2%} | {fault_error:.2%} |
| Latency p99 | {baseline_p99:.4f}s | {fault_p99:.4f}s |
| Total Requests | {self.baseline.get('total', 0)} | {self.fault.get('total', 0)} |

## System Resilience Score: {score:.1f}/100
- **System Health**: {system_health}
- Availability Retention: {availability_retention:.1f}%
- Kill-Switch Error Threshold: {error_limit:.2%}
- Kill-Switch Latency Threshold: {latency_limit:.1f}x baseline
"""

    def generate_ai_recommendations(self, report_content):
        if not self.scorer.client:
            return """## AI Recommendations for Fixes

*Skipped Gemini call: no usable `GEMINI_API_KEY` / `google-genai` client was available.*

1. Add Kubernetes readiness and liveness probes for the target deployment.
2. Configure upstream request timeouts and retries with bounded budgets.
3. Run at least two replicas for customer-critical services.
4. Add a PodDisruptionBudget for services on cart and checkout paths.
5. Capture SLO dashboards for error rate, p95/p99 latency, and recovery time.
"""

        prompt = f"""
You are an expert Cloud-Native SRE. I have just run a Chaos Engineering experiment on Kubernetes microservices.
Below is the post-mortem report:

{report_content}

Please provide 3-5 concrete, actionable engineering recommendations to improve the resilience of this system.
Format your output entirely in Markdown as a section starting with "## AI Recommendations for Fixes".
Do not include markdown codeblock tags.
"""
        for model in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
            try:
                response = self.scorer.client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return response.text.strip()
            except Exception:
                continue

        return """## AI Recommendations for Fixes

Gemini was unavailable during recommendation generation. Apply the baseline resilience controls:

1. Increase replicas for critical path services.
2. Add timeouts, retries, and circuit breakers.
3. Use readiness probes to avoid routing to unhealthy pods.
4. Add PodDisruptionBudgets and autoscaling for ingress-facing services.
"""

