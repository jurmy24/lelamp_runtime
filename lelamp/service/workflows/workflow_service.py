
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
        Get the current step with full context.
        Returns the intent, preferred actions, AND relevant state variables.
        """
        if self.workflow_graph is None:
            return "Error: No workflow graph found. Please select a workflow first."

        if self.workflow_complete:
            return "Workflow is complete. There are no more steps."

        # If no current node, start from the beginning
        if self.current_node is None:
            starting_edge = self.workflow_graph.edges.get("START")
            if not starting_edge:
                return "Error: No starting edge found. Please check the workflow graph."
            
            starting_node_id = starting_edge.target
            self.current_node = self.workflow_graph.nodes[starting_node_id]
            print(f"[WORKFLOW] Starting workflow at node: {starting_node_id}")
            
        # Build comprehensive step information
        print(f"[WORKFLOW] Current node: {self.current_node.id}")
        print(f"[WORKFLOW] Current state: {self.state}")
        
        step_info = f"═══ CURRENT STEP ═══\n"
        step_info += f"Node ID: {self.current_node.id}\n"
        step_info += f"Intent: {self.current_node.intent}\n"
        
        if self.current_node.preferred_actions:
            step_info += f"\n⚠️ REQUIRED ACTIONS:\n"
            for action in self.current_node.preferred_actions:
                step_info += f"  • You MUST call: {action}\n"
        
        # Show state info more clearly
        if self.workflow_graph.state_schema:
            step_info += f"\nState variables (update via complete_step if needed):\n"
            for key, var in self.workflow_graph.state_schema.items():
                current_value = self.state.get(key)
                step_info += f"  • {key}: {current_value} (type: {var.type})\n"
        
        step_info += "═══════════════════\n"
        
        return step_info
    
    def complete_step(self, state_updates: dict = None) -> str:
        """
        Complete the current step and advance to the next node.
        Optionally update state variables before advancing.
        
        Args:
            state_updates: Dict of state variable updates, e.g. {"user_response_detected": True}
        
        Returns:
            Info about the next step or workflow completion message.
        """
        print(f"\n[WORKFLOW] ========== COMPLETING STEP ==========")
        print(f"[WORKFLOW] Current node: {self.current_node.id if self.current_node else 'None'}")
        print(f"[WORKFLOW] State updates received: {state_updates}")
        print(f"[WORKFLOW] Current state before updates: {self.state}")
        
        if self.workflow_graph is None:
            return "Error: No active workflow"
        
        if self.current_node is None:
            return "Error: No current node"
        
        if self.workflow_complete:
            return "Workflow already complete"
        
        # Apply any state updates first
        if state_updates:
            for key, value in state_updates.items():
                if key not in self.workflow_graph.state_schema:
                    error_msg = f"Error: State variable '{key}' not found in workflow schema. Available: {list(self.workflow_graph.state_schema.keys())}"
                    print(f"[WORKFLOW] ❌ {error_msg}")
                    return error_msg
                self.state[key] = value
                print(f"[WORKFLOW] ✓ Updated state: {key} = {value}")
        
        print(f"[WORKFLOW] State after updates: {self.state}")
        
        # Get outgoing edge from current node
        edge = self.workflow_graph.edges.get(self.current_node.id)
        
        if not edge:
            self.workflow_complete = True
            print(f"[WORKFLOW] ✓ Workflow complete - no outgoing edges")
            return "Workflow complete! No more steps."
        
        print(f"[WORKFLOW] Edge type: {edge.type}")
        
        # Resolve the target based on edge type
        next_node_id = self._resolve_edge_target(edge)
        print(f"[WORKFLOW] Resolved next node: {next_node_id}")
        
        if next_node_id == "END":
            self.workflow_complete = True
            print(f"[WORKFLOW] ✓ Workflow complete - reached END")
            return "Workflow complete! Reached END state."
        
        # Move to next node
        prev_node_id = self.current_node.id
        self.current_node = self.workflow_graph.nodes[next_node_id]
        
        print(f"[WORKFLOW] ✓ Transitioned: {prev_node_id} → {next_node_id}")
        print(f"[WORKFLOW] Next node intent: {self.current_node.intent}")
        print(f"[WORKFLOW] Next node preferred actions: {self.current_node.preferred_actions}")
        print(f"[WORKFLOW] ========================================\n")
        
        # Return the next step info immediately
        next_step_info = f"✓ Advanced from '{prev_node_id}' to '{next_node_id}'\n\n"
        next_step_info += f"═══ NEXT STEP ═══\n"
        next_step_info += f"Node ID: {self.current_node.id}\n"
        next_step_info += f"Intent: {self.current_node.intent}\n"
        
        if self.current_node.preferred_actions:
            next_step_info += f"\n⚠️ REQUIRED ACTIONS:\n"
            for action in self.current_node.preferred_actions:
                next_step_info += f"  • You MUST call: {action}\n"
            next_step_info += "\nExecute these actions NOW before doing anything else.\n"
        
        next_step_info += "═══════════════════"
        
        return next_step_info
    
    def _resolve_edge_target(self, edge: Edge) -> str:
        """Resolve the target node ID based on edge type and current state"""
        if edge.type == EdgeType.NORMAL:
            return edge.target
        
        # TODO: These checks could be done within the Workflow class
        # Conditional edge
        if not isinstance(edge.target, dict):
            raise ValueError(f"Conditional edge {edge.id} target must be a dict")
        
        if not edge.state_key:
            raise ValueError(f"Conditional edge {edge.id} missing state_key")
        
        # Get state value and convert to target key
        state_value = self.state.get(edge.state_key)
        
        # For booleans: convert to "true"/"false" string
        # For literals: use the value directly as string
        target_key = "true" if state_value is True else "false" if state_value is False else str(state_value)
        
        if target_key not in edge.target:
            raise ValueError(
                f"Edge {edge.id}: state '{edge.state_key}'={state_value} -> '{target_key}' "
                f"not in targets {list(edge.target.keys())}"
            )
        
        return edge.target[target_key]

        