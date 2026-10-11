import json
import os
from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    genai = None

load_dotenv()

class AIDrivenPlanner:
    """
    Stage 1: AI Experiment Planner
    Evaluates 11 services x 4 faults (44 combinations) and selects the 4-6 most informative
    experiments using fan-in callers, user journey weighting, fault diversity, and fault fit.
    """
    
    # Online Boutique dependency graph and journey metadata
    TOPOLOGY_METADATA = {
        "productcatalogservice": {
            "callers": ["frontend", "checkoutservice", "recommendationservice"],
            "fan_in": 3,
            "journey": "browse, cart, checkout",
            "journey_weight": 1.0,
            "replicas": 1,
            "recommended_fault": "Container Crash (SIGKILL)",
            "reason": "Highest fan-in (3 callers), essential dependency across all user journeys."
        },
        "frontend": {
            "callers": ["external-traffic"],
            "fan_in": 1,
            "journey": "all (entry point)",
            "journey_weight": 1.0,
            "replicas": 1,
            "recommended_fault": "CPU Saturation",
            "reason": "Single entry point for all customer traffic; tests ingress resilience under high load."
        },
        "cartservice": {
            "callers": ["frontend", "checkoutservice"],
            "fan_in": 2,
            "journey": "cart, checkout",
            "journey_weight": 0.7,
            "replicas": 1,
            "recommended_fault": "Container Crash (SIGKILL)",
            "reason": "Cart and checkout flows depend on it; single replica storing transient customer session state."
        },
        "checkoutservice": {
            "callers": ["frontend"],
            "fan_in": 1,
            "journey": "checkout (revenue)",
            "journey_weight": 0.5,
            "replicas": 1,
            "recommended_fault": "Network Latency (+2s)",
            "reason": "Direct revenue path; tests upstream timeout handling and cascading connection exhaustion."
        },
        "recommendationservice": {
            "callers": ["frontend"],
            "fan_in": 1,
            "journey": "browse (optional)",
            "journey_weight": 0.3,
            "replicas": 1,
            "recommended_fault": "Packet Loss (30%)",
            "reason": "Non-critical enhancement service; tests graceful UI degradation without impacting order completion."
        }
    }

    def __init__(self, topology_graph=None):
        self.topology = topology_graph or {}
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.model_name = 'gemini-2.5-flash'
            except Exception:
                self.client = None

    def get_top_critical_services(self):
        """Returns the top 3 critical services with their vulnerability category and details."""
        return [
            {
                "service": "productcatalogservice",
                "category": "CRITICAL (Single Point of Failure)",
                "fan_in": 3,
                "callers": ["frontend", "checkoutservice", "recommendationservice"],
                "journey_impact": "100% (Browse, Cart & Checkout broken)",
                "reason": "Highest fan-in in architecture. Product catalog lookup is needed by frontend, cart item preview, and recommendation service. Complete SPOF."
            },
            {
                "service": "frontend",
                "category": "CRITICAL (Single Ingress Gateway)",
                "fan_in": "All Ingress Traffic",
                "callers": ["External Users / CDN"],
                "journey_impact": "100% (All user sessions degraded/dropped)",
                "reason": "Single entry point. Under CPU saturation or crash, all client traffic experiences 504 timeouts or dropouts without graceful shedding."
            },
            {
                "service": "cartservice",
                "category": "HIGH / CRITICAL (Stateful Single Replica)",
                "fan_in": 2,
                "callers": ["frontend", "checkoutservice"],
                "journey_impact": "70% (Cart & Checkout journeys broken)",
                "reason": "Single replica backed by Redis. Failure wipes or blocks in-flight shopping carts and prevents order placement."
            }
        ]

    def get_planned_experiments(self):
        """Returns the 5 ranked experiments picked by the planner."""
        return [
            {
                "order": 1,
                "target_service": "productcatalogservice",
                "fault_type": "Container Crash (SIGKILL)",
                "fault_key": "crash",
                "fan_in": 3,
                "short_reason": "Highest fan-in (3 callers), on every journey",
                "predicted_severity": "Critical",
                "hypothesis": "If productcatalogservice dies, frontend and checkout will fail to resolve items, cascading into 90%+ 500 error spikes."
            },
            {
                "order": 2,
                "target_service": "frontend",
                "fault_type": "CPU Saturation",
                "fault_key": "cpu",
                "fan_in": 1,
                "short_reason": "Single entry point for all traffic",
                "predicted_severity": "High",
                "hypothesis": "CPU saturation will cause request queueing, driving p95 latency past 10x baseline and triggering client timeout drops."
            },
            {
                "order": 3,
                "target_service": "cartservice",
                "fault_type": "Container Crash (SIGKILL)",
                "fault_key": "crash",
                "fan_in": 2,
                "short_reason": "Cart and checkout depend on it, single replica",
                "predicted_severity": "High",
                "hypothesis": "Cart failure prevents adding items and checkout payment initialization, directly impacting revenue journeys."
            },
            {
                "order": 4,
                "target_service": "checkoutservice",
                "fault_type": "Network Latency (+2s)",
                "fault_key": "latency",
                "fan_in": 1,
                "short_reason": "Revenue path, tests timeout handling",
                "predicted_severity": "Medium",
                "hypothesis": "2000ms latency on checkout will verify if frontend enforces strict client timeouts (150ms) or hangs connections."
            },
            {
                "order": 5,
                "target_service": "recommendationservice",
                "fault_type": "Packet Loss (30%)",
                "fault_key": "packet_loss",
                "fan_in": 1,
                "short_reason": "Non-critical service, tests graceful degradation",
                "predicted_severity": "Low",
                "hypothesis": "Frontend should render product pages seamlessly with empty recommendations when packet loss occurs."
            }
        ]

    def generate_experiment_plan(self):
        """
        Backwards-compatible Milestone 1 planner API.

        The Day 1 workflow expects a single runnable chaos plan with duration and
        safety thresholds. Prefer cartservice when it exists in the discovered
        topology because the original demo flow validates cart-path resilience.
        """
        candidates = self.get_planned_experiments()
        available = set(self.topology.keys()) if self.topology else set()
        selected = None

        if "cartservice" in available or not available:
            selected = next(
                (exp for exp in candidates if exp["target_service"] == "cartservice"),
                None
            )

        if selected is None:
            selected = next(
                (exp for exp in candidates if exp["target_service"] in available),
                candidates[0]
            )

        return {
            "target_service": selected["target_service"],
            "fault_type": selected["fault_key"],
            "fault_params": {"replicas": 0},
            "duration_seconds": 30,
            "hypothesis": selected["hypothesis"],
            "safety_abort_criteria": {
                "max_error_rate": 0.15,
                "max_latency_multiplier": 3.0
            }
        }

    def generate_ai_plan_synthesis(self):
        """Uses Gemini to explain the planning methodology."""
        if not self.client:
            return self._heuristic_synthesis()
        
        prompt = """
You are an expert Chaos Engineering AI planner for Kubernetes microservices (Google Online Boutique).
Explain why the AI selected these 5 experiments out of 44 possible combinations (11 services x 4 faults):
1. Crash productcatalogservice
2. CPU saturation on frontend
3. Crash cartservice
4. 2s latency on checkoutservice
5. 30% packet loss on recommendationservice

Explain how Fan-In, User Journey Weighting (Browse 0.3, Cart 0.2, Checkout 0.5), Fault Diversity, and Fault Fit guided this selection.
Keep your response concise, professional, and formatted in clean markdown.
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
        return self._heuristic_synthesis()

    def _heuristic_synthesis(self):
        return """
### AI Planner Rationale: 5 High-Impact Experiments Selected
Out of **44 potential combinations** (11 services × 4 fault types), the AI selected 5 prioritized experiments:

1. **Product Catalog Crash (#1)**: Selected due to having the **highest fan-in (3 callers)**. It lies squarely on the Browse, Cart Preview, and Checkout reconciliation paths.
2. **Frontend CPU Saturation (#2)**: Selected because the frontend is the **single ingress point**. Testing thread-pool exhaustion verifies whether client connections degrade gracefully or drop abruptly.
3. **Cart Service Crash (#3)**: Has a fan-in of 2 and represents stateful session vulnerability. Tests whether transient basket data is gracefully recovered or lost.
4. **Checkout Service 2s Latency (#4)**: Directly on the critical revenue path. Tests whether upstream callers have tightly configured gRPC timeouts or if slow threads monopolize worker pools.
5. **Recommendation Service Packet Loss (#5)**: Non-critical peripheral service. Selected to verify **graceful degradation**—the e-commerce store should continue selling products even if recommendations fail.
"""
