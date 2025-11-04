
import json


class WorkflowService:
    def __init__(self):
        self.active_workflow = None
        self.state = None
        

    def load_workflow(self, workflow_name: str):
        with open(f"lelamp/workflows/{workflow_name}.json", "r") as f:
            self.workflows[workflow_name] = json.load(f)
            
    def generate_workflow_graph(self, workflow_name: str):
        return self.workflows[workflow_name]

    def get_next_step(self):
        return self.workflows[workflow_name]["next_step"]