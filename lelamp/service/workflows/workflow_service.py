
import json

from lelamp.service.workflows.workflow import Workflow


class WorkflowService:
    def __init__(self):
        self.active_workflow = None
        self.state = None
        self.workflow_graph = None
        
    def generate_workflow(self, workflow_name: str):
        with open(f"lelamp/workflows/{workflow_name}.json", "r") as f:
            self.workflows[workflow_name] = json.load(f)
            self.workflow_graph = Workflow.from_json(self.workflows[workflow_name])
            
    def get_next_step(self):
        if self.workflow_graph is None:
            return "Error: No workflow graph found. Please select a workflow first."
        current_node = self.workflow_graph.get_current_node()
        return 