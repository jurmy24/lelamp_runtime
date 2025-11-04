"""
LeLamp Workflow Engine - Interprets JSON workflow and converts it into a LangGraph executable
Loads and executes JSON workflow definitions with LangGraph
"""

import json
import asyncio
from typing import TypedDict, Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
from livekit.agents import Agent
import logging

logger = logging.getLogger(__name__)


# Workflow State
class WorkflowState(TypedDict):
    current_node_id: str
    workflow_data: Dict[str, Any]
    user_response_detected: bool
    context: Dict[str, Any]
    history: List[str]


@dataclass
class WorkflowNode:
    """Parsed workflow node"""

    id: str
    type: str
    label: str
    data: Dict[str, Any]
    position: Dict[str, float]


@dataclass
class WorkflowEdge:
    """Parsed workflow edge"""

    id: str
    source: str
    target: str
    label: str
    condition: Optional[str] = None


class WorkflowEngine:
    """
    Dynamic workflow engine that interprets JSON workflow definitions
    and executes them using LangGraph with LiveKit agent integration
    """

    def __init__(self, agent: Agent):
        """
        Initialize workflow engine with a LiveKit agent

        Args:
            agent: The LeLamp agent instance with tools
        """
        self.agent = agent
        self.workflows: Dict[str, Dict] = {}
        self.compiled_graphs: Dict[str, Any] = {}

    def load_workflow(self, workflow_path: str) -> str:
        """
        Load a workflow definition from JSON file

        Args:
            workflow_path: Path to workflow JSON file

        Returns:
            workflow_id: ID of the loaded workflow
        """
        with open(workflow_path, "r") as f:
            workflow_def = json.load(f)

        workflow_id = workflow_def.get("id")
        if not workflow_id:
            raise ValueError("Workflow must have an 'id' field")

        self.workflows[workflow_id] = workflow_def
        logger.info(f"Loaded workflow: {workflow_id} - {workflow_def.get('name')}")

        return workflow_id

    def compile_workflow(self, workflow_id: str) -> Any:
        """
        Compile a loaded workflow into a LangGraph executable

        Args:
            workflow_id: ID of workflow to compile

        Returns:
            Compiled LangGraph graph
        """
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not loaded")

        workflow = self.workflows[workflow_id]

        # Parse nodes and edges
        nodes = [
            WorkflowNode(
                id=n["id"],
                type=n["type"],
                label=n.get("label", ""),
                data=n,
                position=n.get("position", {}),
            )
            for n in workflow.get("nodes", [])
        ]

        edges = [
            WorkflowEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                label=e.get("label", ""),
                condition=e.get("condition"),
            )
            for e in workflow.get("edges", [])
        ]

        # Build LangGraph
        graph = StateGraph(WorkflowState)

        # Add nodes to graph
        entry_point = None
        for node in nodes:
            if node.type == "start":
                entry_point = node.id
                continue  # Start nodes don't execute, they just mark entry
            elif node.type == "end":
                continue  # End nodes map to END

            # Create executor for this node
            node_executor = self._create_node_executor(node, workflow)
            graph.add_node(node.id, node_executor)

        # Add edges to graph
        edge_map: Dict[str, List[WorkflowEdge]] = {}
        for edge in edges:
            if edge.source not in edge_map:
                edge_map[edge.source] = []
            edge_map[edge.source].append(edge)

        # Process edges
        for source_id, source_edges in edge_map.items():
            # Skip edges from start node - handle separately
            source_node = next((n for n in nodes if n.id == source_id), None)
            if source_node and source_node.type == "start":
                # Find first real node
                first_edge = source_edges[0]
                graph.set_entry_point(first_edge.target)
                continue

            # Check if this is a decision node (multiple conditional edges)
            conditional_edges = [e for e in source_edges if e.condition]

            if len(source_edges) > 1 or conditional_edges:
                # Create conditional routing function
                def make_router(edges: List[WorkflowEdge]):
                    def route(state: WorkflowState) -> str:
                        # Evaluate conditions
                        for edge in edges:
                            if edge.condition:
                                if self._evaluate_condition(edge.condition, state):
                                    target = edge.target
                                    # Check if target is END node
                                    target_node = next(
                                        (n for n in nodes if n.id == target), None
                                    )
                                    if target_node and target_node.type == "end":
                                        return END
                                    return target

                        # Default to first edge if no condition matches
                        default_target = edges[0].target
                        target_node = next(
                            (n for n in nodes if n.id == default_target), None
                        )
                        if target_node and target_node.type == "end":
                            return END
                        return default_target

                    return route

                router = make_router(source_edges)
                graph.add_conditional_edges(source_id, router)
            else:
                # Simple edge
                edge = source_edges[0]
                target = edge.target
                target_node = next((n for n in nodes if n.id == target), None)

                if target_node and target_node.type == "end":
                    graph.add_edge(source_id, END)
                else:
                    graph.add_edge(source_id, target)

        # Compile graph
        compiled = graph.compile()
        self.compiled_graphs[workflow_id] = compiled

        logger.info(f"Compiled workflow: {workflow_id}")
        return compiled

    def _create_node_executor(self, node: WorkflowNode, workflow: Dict) -> Callable:
        """
        Create an executor function for a workflow node

        Args:
            node: The workflow node to create executor for
            workflow: Full workflow definition for context

        Returns:
            Async function that executes the node
        """

        async def execute_node(state: WorkflowState) -> WorkflowState:
            logger.info(f"Executing node: {node.id} ({node.type})")

            # Update state
            state["current_node_id"] = node.id
            state["history"].append(node.id)

            # Execute based on node type
            if node.type == "intent":
                await self._execute_intent_node(node, state)
            elif node.type == "delay":
                await self._execute_delay_node(node, state)
            elif node.type == "decision":
                await self._execute_decision_node(node, state)
            elif node.type == "action":
                await self._execute_action_node(node, state)
            else:
                logger.warning(f"Unknown node type: {node.type}")

            return state

        return execute_node

    async def _execute_intent_node(self, node: WorkflowNode, state: WorkflowState):
        """Execute an intent node - let agent interpret and act"""
        intent = node.data.get("intent", "")
        context = node.data.get("context", {})

        logger.info(f"Intent: {intent}")
        logger.info(f"Context: {context}")

        # Build prompt for agent to interpret intent
        prompt = self._build_intent_prompt(intent, context)

        # Store in state for agent to access
        state["context"].update(
            {
                "current_intent": intent,
                "intent_context": context,
                "intent_prompt": prompt,
            }
        )

        # Agent should act on this intent
        # (In actual implementation, you'd trigger agent tools here)
        logger.info(f"Agent should execute intent: {intent}")

    async def _execute_delay_node(self, node: WorkflowNode, state: WorkflowState):
        """Execute a delay node - wait for specified time"""
        delay_ms = node.data.get("delay", 1000)
        delay_sec = delay_ms / 1000.0

        logger.info(f"Waiting {delay_sec} seconds...")
        await asyncio.sleep(delay_sec)

    async def _execute_decision_node(self, node: WorkflowNode, state: WorkflowState):
        """Execute a decision node - check conditions"""
        condition = node.data.get("condition", "")

        logger.info(f"Evaluating condition: {condition}")

        # Evaluate condition
        if condition == "detect_voice_or_movement":
            # In real implementation, check for actual user response
            # For now, simulate or check state
            detected = state["context"].get("user_responded", False)
            state["user_response_detected"] = detected
            logger.info(f"Response detected: {detected}")
        else:
            logger.warning(f"Unknown condition: {condition}")

    async def _execute_action_node(self, node: WorkflowNode, state: WorkflowState):
        """Execute an action node - explicit actions"""
        actions = node.data.get("actions", [])

        for action in actions:
            action_type = action.get("type", "")
            params = action.get("params", {})

            logger.info(f"Executing action: {action_type} with params: {params}")

            # Execute agent tools based on action type
            if hasattr(self.agent, action_type):
                tool = getattr(self.agent, action_type)
                if callable(tool):
                    await tool(**params)

    def _build_intent_prompt(self, intent: str, context: Dict[str, Any]) -> str:
        """Build a prompt for the agent to interpret an intent"""
        mood = context.get("mood", "neutral")
        energy = context.get("energy_level", "medium")
        urgency = context.get("urgency", "normal")
        goal = context.get("goal", "")

        prompt = f"""
You are executing the intent: "{intent}"

Context:
- Mood: {mood}
- Energy Level: {energy}
- Urgency: {urgency}
- Goal: {goal}

Express yourself using your available tools (movements, lights, voice, volume) to achieve this intent.
Choose appropriate actions that match the mood and energy level specified.
"""
        return prompt

    def _evaluate_condition(self, condition: str, state: WorkflowState) -> bool:
        """Evaluate a condition string against current state"""
        if condition == "true":
            return state.get("user_response_detected", False)
        elif condition == "false":
            return not state.get("user_response_detected", False)
        else:
            # Could support more complex expressions here
            logger.warning(f"Unknown condition format: {condition}")
            return False

    async def execute_workflow(
        self, workflow_id: str, initial_state: Optional[Dict[str, Any]] = None
    ) -> WorkflowState:
        """
        Execute a compiled workflow

        Args:
            workflow_id: ID of workflow to execute
            initial_state: Optional initial state values

        Returns:
            Final workflow state
        """
        if workflow_id not in self.compiled_graphs:
            # Try to compile if loaded
            if workflow_id in self.workflows:
                self.compile_workflow(workflow_id)
            else:
                raise ValueError(f"Workflow {workflow_id} not found")

        graph = self.compiled_graphs[workflow_id]

        # Initialize state
        state: WorkflowState = {
            "current_node_id": "",
            "workflow_data": self.workflows[workflow_id],
            "user_response_detected": False,
            "context": initial_state or {},
            "history": [],
        }

        logger.info(f"Starting workflow execution: {workflow_id}")

        # Execute graph
        final_state = await graph.ainvoke(state)

        logger.info(f"Workflow completed: {workflow_id}")
        logger.info(f"Execution path: {' -> '.join(final_state['history'])}")

        return final_state


async def demo_workflow_engine():
    """Demo the workflow engine"""
    from lelamp.service.motors.motors_service import MotorsService
    from lelamp.service.rgb.rgb_service import RGBService

    # Mock agent for demo
    class MockAgent:
        def __init__(self):
            self.motors_service = None
            self.rgb_service = None

    agent = MockAgent()
    engine = WorkflowEngine(agent)

    # Load and compile workflow
    workflow_id = engine.load_workflow("lelamp/workflows/wake_up.json")
    engine.compile_workflow(workflow_id)

    # Execute workflow
    result = await engine.execute_workflow(workflow_id)

    print(f"Workflow completed!")
    print(f"Path taken: {result['history']}")


if __name__ == "__main__":
    asyncio.run(demo_workflow_engine())
