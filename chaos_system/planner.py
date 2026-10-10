import json
import random
import os
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class AIDrivenPlanner:
    def __init__(self, topology_graph):
        self.topology = topology_graph
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = 'gemini-3.8-flash'
        else:
            self.client = None

    def generate_experiment_plan(self):
        if not self.client:
            print("WARNING: No GEMINI_API_KEY found in .env. Falling back to heuristic planner.")
            return self._heuristic_plan()

        prompt = f"""
You are an expert Chaos Engineering AI. 
I have the following microservice topology graph:
{json.dumps(self.topology, indent=2)}

Please generate a chaos experiment plan targeting one of the critical services (e.g., cartservice, paymentservice).
Output exactly a JSON object in this format (and nothing else, no markdown code blocks):
{{
  "target_service": "...",
  "fault_type": "container_kill",
  "fault_params": {{"replicas": 0}},
  "duration_seconds": 30,
  "hypothesis": "...",
  "safety_abort_criteria": {{
    "max_error_rate": 0.15,
    "max_latency_multiplier": 3.0
  }}
}}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            # Clean up the output in case the LLM returned markdown code blocks
            text_response = response.text.strip()
            if text_response.startswith("```json"):
                text_response = text_response.split("```json")[1].strip()
            if text_response.endswith("```"):
                text_response = text_response.rsplit("```", 1)[0].strip()
                
            plan = json.loads(text_response)
            return plan
        except Exception as e:
            print(f"ERROR: Failed to generate plan using Gemini ({e}). Falling back to heuristic planner.")
            return self._heuristic_plan()

    def _heuristic_plan(self):
        # Heuristic fallback if API fails or key is missing
        critical_services = ["cartservice", "paymentservice", "checkoutservice"]
        available = [s for s in critical_services if s in self.topology]
        target = random.choice(available) if available else "cartservice"
        
        plan = {
            "target_service": target,
            "fault_type": "container_kill",
            "fault_params": {"replicas": 0},
            "duration_seconds": 30,
            "hypothesis": f"Verify whether frontend degrades gracefully if {target} is unavailable.",
            "safety_abort_criteria": {
                "max_error_rate": 0.15,
                "max_latency_multiplier": 3.0
            }
        }
        return plan
