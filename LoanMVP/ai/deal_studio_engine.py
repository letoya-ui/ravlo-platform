from .rehab_engine import run_rehab_concept
from .build_engine import run_build_concept

class DealStudioEngine:
    @staticmethod
    def generate(workspace, payload):
        if workspace == "rehab":
            return run_rehab_concept(payload)
        elif workspace == "build":
            return run_build_concept(payload)
        else:
            raise ValueError(f"Unsupported workspace: {workspace}")