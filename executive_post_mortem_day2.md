# Milestone 2 Executive Post-Mortem Report

Resilience Score: 58/100

### 📋 SRE Architectural Post-Mortem & Remediation (Deterministic Analysis)

#### 1. Executive Summary & Resilience Health Verdict
- **System Resilience Score**: **58 / 100**
- **Evaluation Status**: **CRITICAL VULNERABILITY (Severe Cascade Risks)**
- The automated chaos run evaluated the microservice dependency graph under fault injection, quantifying blast radii and cascade vulnerabilities across customer user journeys.

#### 2. Plain-Language Analysis of Ranked Findings
1. **#1 Critical — Crash productcatalogservice (Score: 75/100)**
   - Journey: 1.0 (all broken) | Errors: 90% | Recovery: 30 s → 0.25 | Latency: 6x → 0.6
2. **#2 High — CPU saturation frontend (Score: 51/100)**
   - Journey: 0.5 (all degraded) | Errors: 25% | Recovery: 45 s → 0.38 | Latency: ≥10x → 1.0
3. **#3 High — Crash cartservice (Score: 42/100)**
   - Journey: 0.7 (cart + checkout) | Errors: 35% | Recovery: 40 s → 0.33 | Latency: 1.2x → 0.12
4. **#4 Medium — 2s latency checkoutservice (Score: 32/100)**
   - Journey: 0.25 (checkout degraded) | Errors: 20% | Recovery: 10 s → 0.08 | Latency: 8x → 0.83
5. **#5 Low — 30% packet loss recommendationservice (Score: 10/100)**
   - Journey: 0.08 (non-critical degraded) | Errors: 3% | Recovery: 5 s → 0.04 | Latency: 3x → 0.3

#### 3. Prediction vs Reality Comparison
- **Planner Prediction**: Ranked experiments by fan-in × journey weight heuristic before any faults were run.
- **Measured Outcome**:
  - All 5 experiments ranked exactly as predicted — confirms the AI planner's dependency-graph analysis was accurate.

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
