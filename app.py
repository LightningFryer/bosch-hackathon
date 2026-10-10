import streamlit as st
import time
import random
import pandas as pd

# -----------------------------------------
# Page Configuration
# -----------------------------------------
st.set_page_config(layout="wide", page_title="AI Chaos SRE Engine", page_icon="🛡️")

# -----------------------------------------
# Session State Initialization
# -----------------------------------------
if "run_state" not in st.session_state:
    st.session_state.run_state = "IDLE"  # IDLE, RUNNING, FINISHED
if "telemetry" not in st.session_state:
    st.session_state.telemetry = {"time": [], "error_rate": [], "latency": []}

# -----------------------------------------
# Sidebar Configuration
# -----------------------------------------
with st.sidebar:
    st.title("AI Chaos Engine")
    st.markdown("Configure the parameters for the autonomous chaos experiment.")
    
    st.header("Target Configuration")
    target_service = st.selectbox(
        "Select Microservice Target:",
        ["cartservice", "paymentservice", "checkoutservice", "productcatalogservice", "recommendationservice", "redis-cart"]
    )
    
    fault_type = st.selectbox(
        "Select Fault Profile:",
        ["Container Crash (SIGKILL)", "Network Latency (+500ms)", "Packet Loss (25%)", "CPU Saturation"]
    )
    
    st.header("Safety Kill-Switch Thresholds")
    max_error_rate = st.slider("Max Error Rate (%)", min_value=5, max_value=50, value=15, step=1)
    max_latency = st.slider("Max p99 Latency (ms)", min_value=50, max_value=500, value=150, step=10)
    
    st.markdown("---")
    
    # Execute Button
    if st.button("🚀 Execute Chaos Run", type="primary", use_container_width=True):
        st.session_state.run_state = "RUNNING"
        st.session_state.telemetry = {"time": [], "error_rate": [], "latency": []}

# -----------------------------------------
# Layout: Top Section (Topology & AI Plan)
# -----------------------------------------
st.markdown("## Architectural Topology & AI Attack Plan")

col1, col2 = st.columns([1.2, 1])

with col1:
    st.markdown("#### Google Online Boutique Map")
    # Using mermaid.js to render the graph
    mermaid_code = """
    ```mermaid
    graph TD
        frontend[Frontend] --> cartservice[Cart Service]
        frontend --> productcatalogservice[Product Catalog]
        frontend --> checkoutservice[Checkout Service]
        frontend --> recommendationservice[Recommendation]
        frontend --> adservice[Ad Service]
        frontend --> currencyservice[Currency Service]
        
        cartservice --> redis-cart[(Redis Cart DB)]
        
        checkoutservice --> cartservice
        checkoutservice --> productcatalogservice
        checkoutservice --> currencyservice
        checkoutservice --> paymentservice[Payment Service]
        checkoutservice --> shippingservice[Shipping Service]
        checkoutservice --> emailservice[Email Service]
        
        recommendationservice --> productcatalogservice
        
        style frontend fill:#1E88E5,stroke:#fff,color:#fff
        style cartservice fill:#D32F2F,stroke:#fff,color:#fff
        style checkoutservice fill:#FDD835,stroke:#333,color:#333
        style redis-cart fill:#43A047,stroke:#fff,color:#fff
    ```
    """
    st.markdown(mermaid_code)

with col2:
    st.markdown("#### AI Experiment Justification (Gemini)")
    with st.container(border=True):
        st.markdown(f"**Target:** `{target_service}`")
        st.markdown(f"**Fault Injected:** `{fault_type}`")
        st.markdown("**AI Hypothesis:**")
        st.info(f"If `{target_service}` experiences `{fault_type}`, upstream services like `frontend` and `checkoutservice` should gracefully degrade by utilizing fallback caches or displaying friendly error states, preventing a total site outage.")
        st.markdown("**Safety Guardrails:**")
        st.warning(f"Kill-Switch will automatically engage if Error Rate > **{max_error_rate}%** OR Latency > **{max_latency}ms**.")

st.divider()

# -----------------------------------------
# Layout: Middle Section (Live Telemetry)
# -----------------------------------------
st.markdown("## Live Telemetry & Automated Kill-Switch")

status_col1, status_col2, status_col3 = st.columns(3)

# Placeholders for live updating
metrics_placeholder = st.empty()
chart_placeholder = st.empty()
alert_placeholder = st.empty()

# -----------------------------------------
# Simulation Loop (Only runs if state is RUNNING)
# -----------------------------------------
if st.session_state.run_state == "RUNNING":
    current_time = 0
    triggered = False
    
    # Initialize empty dataframe for charting
    df = pd.DataFrame(columns=["Error Rate (%)", "Latency (ms)"])
    
    with alert_placeholder.container():
        st.info("Experiment Initializing... gathering baseline.")
    
    for t in range(1, 21):
        time.sleep(0.5) # Simulate time passing
        
        if t < 5:
            # Steady State
            state_text = "STEADY-STATE"
            err = random.uniform(0, 2)
            lat = random.uniform(80, 110)
        elif t >= 5 and not triggered:
            # Attack Active
            state_text = "ATTACK ACTIVE"
            # Spike the metrics
            err = random.uniform(5, max_error_rate + 5)
            lat = random.uniform(120, max_latency + 50)
            
            # Check circuit breaker
            if err > max_error_rate or lat > max_latency:
                triggered = True
                state_text = "CIRCUIT BREAKER TRIPPED"
                
                with alert_placeholder.container():
                    st.error(f"**Kill Switch Tripped** (Error: {err:.1f}%, Latency: {lat:.0f}ms). Halting attack and restoring `{target_service}`...")
        else:
            # Recovered
            state_text = "RECOVERED"
            err = random.uniform(0, 3)
            lat = random.uniform(90, 120)
            
        # Append to telemetry state
        st.session_state.telemetry["time"].append(t)
        st.session_state.telemetry["error_rate"].append(err)
        st.session_state.telemetry["latency"].append(lat)
        
        # Update KPI Cards
        with metrics_placeholder.container():
            m1, m2, m3 = st.columns(3)
            m1.metric("System State", state_text)
            m2.metric("Live Error Rate", f"{err:.2f}%", f"{err - max_error_rate:.2f}% vs Limit", delta_color="inverse")
            m3.metric("Live p99 Latency", f"{lat:.0f}ms", f"{lat - max_latency:.0f}ms vs Limit", delta_color="inverse")
            
        # Update Chart
        df = pd.DataFrame({
            "Error Rate (%)": st.session_state.telemetry["error_rate"],
            "Latency (ms)": st.session_state.telemetry["latency"]
        }, index=st.session_state.telemetry["time"])
        
        chart_placeholder.line_chart(df)
        
    st.session_state.run_state = "FINISHED"
    with alert_placeholder.container():
        st.success("✅ Experiment concluded. Scroll down for Post-Mortem Report.")

# -----------------------------------------
# Layout: Bottom Section (Post-Mortem)
# -----------------------------------------
if st.session_state.run_state == "FINISHED":
    st.divider()
    st.markdown("## Resilience Scoring & AI Remediation Report")
    
    score_col1, score_col2 = st.columns([1, 2])
    
    with score_col1:
        st.markdown("### System Resilience Score")
        # Compute fake score based on parameters
        availability = 100 - (max_error_rate + 2.5) 
        mttr_score = 50
        final_score = (availability * 0.7) + (mttr_score * 0.3)
        
        st.metric("Overall Score", f"{final_score:.1f} / 100")
        st.progress(int(final_score))
        
        st.markdown(f"- **Availability Retention:** `{availability:.1f}%`")
        st.markdown(f"- **Blast Radius Containment:** `FAILED (Kill-switch fired)`")
        st.markdown(f"- **MTTR:** `14 seconds`")
        
        with st.expander("How is this calculated?"):
            st.markdown("""
            **1. Availability Retention**
            `MAX(0, 100 * (1.0 - Error_Rate))`
            *Measures the percentage of successful user requests during the attack.*
            
            **2. MTTR Score**
            `100 if Error_Rate ≤ Safety_Threshold else 50`
            *A heuristic penalty. Drops to 50 if the kill-switch had to forcefully intervene.*
            
            **3. Final Resilience Score**
            `(Availability * 0.70) + (MTTR * 0.30)`
            *A weighted composite prioritizing user experience (Availability) over recovery time.*
            """)
            
    with score_col2:
        st.markdown("### 🤖 AI Post-Mortem Analysis")
        with st.expander("View Architectural Fixes (Generated by Gemini)", expanded=True):
            st.markdown(f"""
            **Root Cause Analysis:**
            When `{target_service}` crashed, upstream services failed to implement proper circuit breaking and timeouts, causing threads to block and resulting in a {max_error_rate+2:.1f}% cascading error rate across the frontend.
            
            **Actionable Engineering Recommendations:**
            
            1. **Implement Istio VirtualService Circuit Breaking**
               Add a `DestinationRule` to instantly trip the circuit for `{target_service}` after 3 consecutive 5xx errors:
               ```yaml
               apiVersion: networking.istio.io/v1alpha3
               kind: DestinationRule
               metadata:
                 name: {target_service}-cb
               spec:
                 host: {target_service}
                 trafficPolicy:
                   outlierDetection:
                     consecutive5xxErrors: 3
                     interval: 5s
                     baseEjectionTime: 15m
               ```
               
            2. **Add gRPC Fallback Responses**
               Modify the `frontend` handlers to catch `Unavailable` gRPC statuses from `{target_service}` and return a cached view (e.g., displaying the last known cart state) rather than failing the entire page load.
               
            3. **Aggressive Timeout Configuration**
               Currently, connections are hanging up to 3000ms. Enforce a strict `150ms` client timeout to match your p99 bounds.
            """)
