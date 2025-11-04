
import json
import os

from lelamp.service.workflows.workflow import Edge, EdgeType, Workflow


class WorkflowService:
    def __init__(self):
        self.active_workflow = None
        self.state = None
        self.workflow_graph: Workflow = None
        self.current_node = None
        self.workflows_dir = os.path.join(os.path.dirname(__file__), "..", "..", "workflows")
        self.workflow_complete = False
        
    def start_workflow(self, workflow_name: str):
        with open(f"lelamp/workflows/{workflow_name}.json", "r") as f:
            workflow_data = json.load(f)
            self.workflow_graph = Workflow.from_json(workflow_data)
            self.active_workflow = workflow_name
            # Initialize state with defaults from schema
            self.state = self.workflow_graph.state_schema.copy()
            self.state = {
                key: var.default for key, var in self.workflow_graph.state_schema.items()
            }
            self.current_node = None
            self.workflow_complete = False
            
    def get_available_workflows(self) -> list[str]:
        """Get list of workflow names available"""
        if not os.path.exists(self.workflows_dir):
            return []

        workflow_names = []
        suffix = f".json"

        for filename in os.listdir(self.workflows_dir):
            if filename.endswith(suffix):
                # Remove the suffix to get the workflow name
                workflow_name = filename[: -len(suffix)]
                workflow_names.append(workflow_name)

        return sorted(workflow_names)
            
    def get_next_step(self):
        """
        Get the current step to execute WITHOUT advancing.
        Returns the intent and preferred actions for the current node.
        """
        if self.workflow_graph is None:
            return "Error: No workflow graph found. Please select a workflow first."

        if self.workflow_complete:
            return "Workflow is complete. There are no more steps."

        # If no current node, start from the beginning
        if self.current_node is None:
            starting_edge = self.workflow_graph.edges.get("START", [])
            if not starting_edge:
                return "Error: No starting edge found. Please check the workflow graph."
            
            starting_node_id = starting_edge[0].target
            self.current_node = self.workflow_graph.nodes[starting_node_id]
            
        # Build the step information
        step_info = f"Step: {self.current_node.intent}"
        if self.current_node.preferred_actions:
            step_info += f"\nPreferred tools to use: {', '.join(self.current_node.preferred_actions)}"

        return step_info
    
    def update_workflow_state(self, key: str, value: any) -> str:
        """
        Update a workflow state variable.
        The LLM should call this after executing a node's intent to update conditions.
        """
        
        if self.workflow_graph is None:
            return "Error: No workflow graph found."
        
        if key not in self.workflow_graph.state_schema:
            return f"Error: State variable {key} not found in workflow schema. The workflow schema is: {self.workflow_graph.state_schema}"
        
        self.state[key] = value
        print(f"Updated workflow state: {key} = {value}")
        return f"Successfully updated {key} updated to {value}"
    
    def complete_step(self) -> str:
        """
        Mark the current step as complete and advance to the next node.
        Uses current state to evaluate conditional edges.
        Returns info about the transition.
        """
        if self.workflow_graph is None:
            return "Error: No active workflow"
        
        if self.current_node is None:
            return "Error: No current node"
        
        if self.workflow_complete:
            return "Workflow already complete"
        
        # Get outgoing edges from current node
        edges = self.workflow_graph.edges.get(self.current_node.id, [])
        
        if not edges:
            self.workflow_complete = True
            return "Workflow complete! No more steps."
        
        # Get the first edge (should only be one per node in your design)
        edge = edges[0]
        
        # Resolve the target based on edge type
        next_node_id = self._resolve_edge_target(edge)
        
        if next_node_id == "END":
            self.workflow_complete = True
            return "Workflow complete! Reached END state."
        
        # Move to next node
        prev_node_id = self.current_node.id
        self.current_node = self.workflow_graph.nodes[next_node_id]
        
        return f"Advanced from '{prev_node_id}' to '{next_node_id}'. Call get_next_step() for the new instruction."
    
    def _resolve_edge_target(self, edge: Edge) -> str:
        """Resolve the target node ID based on edge type and current state"""
        if edge.type == EdgeType.NORMAL:
            # Simple edge, just return the target
            return edge.target
        
        elif edge.type == EdgeType.CONDITION:
            # Conditional edge - need to evaluate based on state
            # The target is a dict like {"true": "node_a", "false": "node_b"}
            if not isinstance(edge.target, dict):
                raise ValueError(f"Conditional edge {edge.id} has invalid target: {edge.target}")
            
            # Determine which condition to use
            # For the "check_response_received" node, we check "user_response_detected"
            condition_result = self._evaluate_condition(edge)

            
            # Return the appropriate target
            return edge.target["true"] if condition_result else edge.target["false"]
        
        else:
            raise ValueError(f"Unknown edge type: {edge.type}")
    
    def _evaluate_condition(self, edge: Edge) -> bool:
        """
        Evaluate the condition for a conditional edge.
        This examines the state to determine true/false.
        
        For your workflow, conditional nodes typically check a boolean state variable.
        You could make this more sophisticated by:
        - Parsing the node's intent to extract the condition
        - Using a separate "condition" field in nodes
        - Having explicit condition expressions
        
        For now, we use a simple heuristic: 
        Look for boolean state variables and check if any are true.
        """
        # Simple heuristic: If the source node's intent is about checking something,
        # look for corresponding boolean state variables
        source_node = self.workflow_graph.nodes[edge.source]
        
        # For "check_response_received" node, check "user_response_detected"
        # This is a simple mapping - you could make it more sophisticated
        if "response" in source_node.intent.lower():
            return self.state.get("user_response_detected", False)
        
        # Default: check if any boolean state is true
        # (You might want to make this more explicit in your workflow JSON)
        for key, value in self.state.items():
            if isinstance(value, bool) and value:
                return True
        
        return False

        