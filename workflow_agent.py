"""
Workflow-enabled LeLamp Agent
Integrates workflow engine with LeLamps LiveKit agent
"""

from typing import Optional, Dict, Any
from livekit import agents
from livekit.agents import Agent, function_tool
import asyncio
import logging

from lelamp.workflow_engine import WorkflowEngine, WorkflowState

logger = logging.getLogger(__name__)


class WorkflowAgent:
    """
    Wrapper that enables workflow execution within LiveKit agent context
    """

    def __init__(self, lelamp_agent: Agent, session: agents.AgentSession):
        """
        Initialize workflow-enabled agent

        Args:
            lelamp_agent: Base LeLamp agent instance
            session: LiveKit agent session
        """
        self.agent = lelamp_agent
        self.session = session
        self.engine = WorkflowEngine(lelamp_agent)
        self.current_workflow_task: Optional[asyncio.Task] = None
        self.workflow_state: Optional[WorkflowState] = None

    async def load_workflow(self, workflow_path: str) -> str:
        """Load a workflow definition"""
        workflow_id = self.engine.load_workflow(workflow_path)
        self.engine.compile_workflow(workflow_id)
        return workflow_id

    async def execute_intent(self, intent: str, context: Dict[str, Any]):
        """
        Execute an intent with the agent
        Let the agent interpret the intent and choose appropriate actions

        Args:
            intent: The intent to execute
            context: Context including mood, energy, urgency, goal
        """
        # mood = context.get("mood", "neutral")
        # energy = context.get("energy_level", "medium")
        # urgency = context.get("urgency", "normal")
        # goal = context.get("goal", "")
        description = context.get("description", "")

        # Build dynamic instruction for the agent
        instruction = f"""
            Execute this intent: {intent}

            {description}

            Use your available tools (play_recording, set_rgb_solid, paint_rgb_pattern, speak) to express this intent.
            Choose movements and colors that match the mood and energy. Be expressive and use multiple modalities.
        """

        # Generate agent response based on intent
        try:
            await self.session.generate_reply(instructions=instruction)
        except Exception as e:
            logger.error(f"Error executing intent: {e}")

    async def start_workflow(
        self, workflow_id: str, initial_context: Optional[Dict[str, Any]] = None
    ):
        """
        Start a workflow in the background

        Args:
            workflow_id: ID of workflow to execute
            initial_context: Optional initial context
        """
        if self.current_workflow_task and not self.current_workflow_task.done():
            logger.warning("Workflow already running, cancelling previous workflow")
            self.current_workflow_task.cancel()

        # Create workflow execution task
        self.current_workflow_task = asyncio.create_task(
            self._execute_workflow_with_agent(workflow_id, initial_context)
        )

        logger.info(f"Started workflow: {workflow_id}")

    async def _execute_workflow_with_agent(
        self, workflow_id: str, initial_context: Optional[Dict[str, Any]]
    ):
        """
        Internal method to execute workflow with agent integration
        """
        try:
            # Get workflow definition
            workflow = self.engine.workflows[workflow_id]
            nodes = workflow.get("nodes", [])

            # Initialize state
            state: WorkflowState = {
                "current_node_id": "",
                "workflow_data": workflow,
                "user_response_detected": False,
                "context": initial_context or {},
                "history": [],
            }

            # Find start node
            start_node = next((n for n in nodes if n["type"] == "start"), None)
            if not start_node:
                logger.error("No start node found in workflow")
                return

            # Execute workflow step by step with agent integration
            await self._execute_workflow_steps(nodes, workflow.get("edges", []), state)

            self.workflow_state = state
            logger.info("Workflow execution completed")

        except asyncio.CancelledError:
            logger.info("Workflow execution cancelled")
        except Exception as e:
            logger.error(f"Workflow execution error: {e}", exc_info=True)

    async def _execute_workflow_steps(
        self, nodes: list, edges: list, state: WorkflowState
    ):
        """Execute workflow steps with agent"""
        # Build edge map
        edge_map: Dict[str, list] = {}
        for edge in edges:
            if edge["source"] not in edge_map:
                edge_map[edge["source"]] = []
            edge_map[edge["source"]].append(edge)

        # Find start and first real node
        start_node = next((n for n in nodes if n["type"] == "start"), None)
        if not start_node:
            return

        start_edges = edge_map.get(start_node["id"], [])
        if not start_edges:
            return

        current_node_id = start_edges[0]["target"]

        # Execute nodes in sequence
        max_iterations = 100  # Prevent infinite loops
        iteration = 0

        while current_node_id != "end" and iteration < max_iterations:
            iteration += 1

            # Find current node
            current_node = next((n for n in nodes if n["id"] == current_node_id), None)
            if not current_node or current_node["type"] == "end":
                break

            # Execute node
            logger.info(f"Executing: {current_node_id} ({current_node['type']})")
            state["current_node_id"] = current_node_id
            state["history"].append(current_node_id)

            # Execute based on type
            if current_node["type"] == "intent":
                await self._execute_intent_with_agent(current_node, state)
            elif current_node["type"] == "delay":
                delay_ms = current_node.get("delay", 1000)
                await asyncio.sleep(delay_ms / 1000.0)
            elif current_node["type"] == "decision":
                await self._execute_decision(current_node, state)

            # Determine next node
            node_edges = edge_map.get(current_node_id, [])
            if not node_edges:
                break

            # Handle conditional edges
            if len(node_edges) > 1 or any(e.get("condition") for e in node_edges):
                next_node_id = self._evaluate_edges(node_edges, state)
            else:
                next_node_id = node_edges[0]["target"]

            current_node_id = next_node_id

        logger.info(f"Workflow path: {' -> '.join(state['history'])}")

    async def _execute_intent_with_agent(self, node: Dict, state: WorkflowState):
        """Execute intent node with agent"""
        intent = node.get("intent", "")
        context = node.get("context", {})

        # Add any description from actions
        actions = node.get("actions", [])
        if actions:
            for action in actions:
                if "description" in action:
                    context["description"] = action["description"]

        # Execute intent with agent
        await self.execute_intent(intent, context)

    async def _execute_decision(self, node: Dict, state: WorkflowState):
        """Execute decision node - check for user response"""
        condition = node.get("condition", "")

        if condition == "detect_voice_or_movement":
            # Check if user has responded during the wait
            # In real implementation, you'd check LiveKit transcription or participant events
            # For now, check if there's been any voice activity

            # Placeholder: Check state or session for user activity
            # You could monitor session events, transcriptions, etc.
            user_responded = state["context"].get("user_responded", False)

            # Could also check self.session for participant speaking events
            # or implement voice activity detection

            state["user_response_detected"] = user_responded
            logger.info(f"Decision: User responded = {user_responded}")
        else:
            logger.warning(f"Unknown condition: {condition}")

    def _evaluate_edges(self, edges: list, state: WorkflowState) -> str:
        """Evaluate conditional edges and return next node"""
        for edge in edges:
            condition = edge.get("condition")

            if condition == "true":
                if state.get("user_response_detected", False):
                    return edge["target"]
            elif condition == "false":
                if not state.get("user_response_detected", False):
                    return edge["target"]
            elif condition is None:
                return edge["target"]

        # Default to first edge
        return edges[0]["target"]

    def stop_workflow(self):
        """Stop current workflow execution"""
        if self.current_workflow_task and not self.current_workflow_task.done():
            self.current_workflow_task.cancel()
            logger.info("Workflow stopped")

    async def register_workflow_tools(self):
        """Register workflow control tools with the agent"""

        @function_tool
        async def start_workflow(workflow_name: str) -> str:
            """
            Start a predefined workflow like wake_up, greeting, etc.

            Args:
                workflow_name: Name of the workflow to start (e.g., 'wake_up')
            """
            try:
                workflow_path = f"lelamp/workflows/{workflow_name}.json"
                workflow_id = await self.load_workflow(workflow_path)
                await self.start_workflow(workflow_id)
                return f"Started workflow: {workflow_name}"
            except Exception as e:
                return f"Error starting workflow: {str(e)}"

        # Register tools with agent
        # Note: This depends on your LiveKit agent setup
        return start_workflow


# Helper function to create workflow-enabled entrypoint
def create_workflow_entrypoint(lelamp_agent_class):
    """
    Create a workflow-enabled entrypoint for LiveKit

    Args:
        lelamp_agent_class: Your LeLamp agent class

    Returns:
        Entrypoint function for LiveKit
    """

    async def entrypoint(ctx: agents.JobContext):
        from livekit.plugins import openai, noise_cancellation
        from livekit.agents import AgentSession, RoomInputOptions

        # Create agent instance
        agent = lelamp_agent_class(lamp_id="lelamp")

        # Create session
        session = AgentSession(llm=openai.realtime.RealtimeModel(voice="ballad"))

        # Create workflow agent wrapper
        workflow_agent = WorkflowAgent(agent, session)

        # Pre-load common workflows
        try:
            await workflow_agent.load_workflow("lelamp/workflows/wake_up.json")
            logger.info("Loaded wake_up workflow")
        except Exception as e:
            logger.warning(f"Could not load wake_up workflow: {e}")

        # Start session
        await session.start(
            room=ctx.room,
            agent=agent,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )

        # Initial greeting
        await session.generate_reply(
            instructions=f"""When you wake up, start with Tadaaaa. Only speak in English, never in Vietnamese."""
        )

        # Keep workflow agent available for the session
        ctx.workflow_agent = workflow_agent

    return entrypoint
