"""
Wake Up Workflow - LangGraph Implementation
Implements an evaluator-optimizer pattern for progressive wake-up attempts

This workflow progressively escalates wake-up attempts:
1. Gentle wake → Check response
2. Energetic wake → Check response
3. Aggressive wake → Check response
4. Either morning briefing (success) or give up (failure)

Pattern: Evaluator-Optimizer (from LangGraph workflows)
"""

from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END, START
from livekit.agents import Agent
import asyncio
import logging

logger = logging.getLogger(__name__)


# Define the workflow state
class WakeUpState(TypedDict):
    """State for the wake-up workflow"""

    attempt_count: int
    user_awake: bool
    last_response_time: Optional[float]
    workflow_path: list[str]
    context: dict


class WakeUpWorkflow:
    """
    Wake-up workflow using LangGraph's evaluator-optimizer pattern

    The workflow progressively escalates wake-up attempts and evaluates
    user response after each attempt, optimizing the approach based on feedback.
    """

    def __init__(self, lelamp_agent: Agent, session):
        """
        Initialize the wake-up workflow

        Args:
            lelamp_agent: The LeLamp agent with motor and RGB services
            session: LiveKit agent session for voice interaction
        """
        self.agent = lelamp_agent
        self.session = session
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Create the graph with our state schema
        workflow = StateGraph(WakeUpState)

        # Add nodes for each wake-up attempt
        workflow.add_node("gentle_wake", self._gentle_wake)
        workflow.add_node("evaluate_response_1", self._evaluate_response)
        workflow.add_node("energetic_wake", self._energetic_wake)
        workflow.add_node("evaluate_response_2", self._evaluate_response)
        workflow.add_node("aggressive_wake", self._aggressive_wake)
        workflow.add_node("evaluate_response_3", self._evaluate_response)
        workflow.add_node("morning_briefing", self._morning_briefing)
        workflow.add_node("give_up", self._give_up)

        # Define the flow
        workflow.add_edge(START, "gentle_wake")
        workflow.add_edge("gentle_wake", "evaluate_response_1")
        workflow.add_conditional_edges(
            "evaluate_response_1",
            self._route_after_evaluation,
            {"awake": "morning_briefing", "continue": "energetic_wake"},
        )

        workflow.add_edge("energetic_wake", "evaluate_response_2")
        workflow.add_conditional_edges(
            "evaluate_response_2",
            self._route_after_evaluation,
            {"awake": "morning_briefing", "continue": "aggressive_wake"},
        )

        workflow.add_edge("aggressive_wake", "evaluate_response_3")
        workflow.add_conditional_edges(
            "evaluate_response_3",
            self._route_after_evaluation,
            {"awake": "morning_briefing", "continue": "give_up"},
        )

        workflow.add_edge("morning_briefing", END)
        workflow.add_edge("give_up", END)

        return workflow.compile()

    async def _gentle_wake(self, state: WakeUpState) -> WakeUpState:
        """
        Gentle wake-up attempt with soft movements and warm lighting
        Generator phase of evaluator-optimizer pattern
        """
        logger.info("🌅 Gentle wake-up attempt")
        state["workflow_path"].append("gentle_wake")

        try:
            # Warm morning light
            await self.agent.set_rgb_solid(255, 200, 100)

            # Gentle wake-up movement
            await self.agent.play_recording("wake_up")

            # Gentle voice greeting
            await self.session.generate_reply(
                instructions="""
                Wake the user very gently and kindly. Say something like:
                "Good morning! Rise and shine! It's time to wake up."
                Use a soft, friendly tone. Be warm and inviting.
                """
            )

            # Wait for response
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in gentle wake: {e}")

        return state

    async def _energetic_wake(self, state: WakeUpState) -> WakeUpState:
        """
        Energetic wake-up attempt with excited movements and brighter colors
        Optimized generator phase based on previous failure
        """
        logger.info("⚡ Energetic wake-up attempt")
        state["workflow_path"].append("energetic_wake")
        state["attempt_count"] += 1

        try:
            # Bright orange alert
            await self.agent.set_rgb_solid(255, 100, 0)

            # Excited bouncing movement
            await self.agent.play_recording("excited")

            # More energetic voice
            await self.session.generate_reply(
                instructions="""
                Wake the user with more energy and enthusiasm! Say something like:
                "Come on, time to get up! You need to wake up NOW!"
                Use an energetic, enthusiastic tone. Be more insistent and louder.
                """
            )

            # Wait for response
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in energetic wake: {e}")

        return state

    async def _aggressive_wake(self, state: WakeUpState) -> WakeUpState:
        """
        Aggressive wake-up attempt with dramatic movements and flashing lights
        Maximum optimization after two failed attempts
        """
        logger.info("🚨 AGGRESSIVE wake-up attempt")
        state["workflow_path"].append("aggressive_wake")
        state["attempt_count"] += 1

        try:
            # Create flashing red pattern
            flashing_pattern = []
            for i in range(40):
                if i % 2 == 0:
                    flashing_pattern.append((255, 0, 0))  # Red
                else:
                    flashing_pattern.append((0, 0, 0))  # Off

            await self.agent.paint_rgb_pattern(flashing_pattern)

            # Dramatic shock movement
            await self.agent.play_recording("shock")

            # Aggressive voice - maximum urgency
            await self.session.generate_reply(
                instructions="""
                WAKE UP RIGHT NOW! Use a loud, firm, impossible-to-ignore tone.
                Say something like: "WAKE UP! You NEED to get up RIGHT NOW! 
                This is your final warning!" Be dramatic and commanding.
                """
            )

            # Wait for response
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in aggressive wake: {e}")

        return state

    async def _evaluate_response(self, state: WakeUpState) -> WakeUpState:
        """
        Evaluate if user has responded - Evaluator phase of pattern

        In production, this would check:
        - LiveKit participant speaking events
        - Voice activity detection
        - Transcription presence
        - Movement sensors (if available)
        """
        logger.info("🔍 Evaluating user response...")
        state["workflow_path"].append("evaluate")

        # Check if user has responded via LiveKit session
        # For now, this is a placeholder - in production you'd integrate with:
        # - self.session events for voice activity
        # - Transcription data
        # - External sensors

        # Placeholder: Check context for test responses
        user_responded = state["context"].get("user_responded", False)

        # Could also implement timeout-based checks or voice activity detection
        # Example: Check last N seconds of audio for speech

        state["user_awake"] = user_responded
        logger.info(f"User awake: {user_responded}")

        return state

    def _route_after_evaluation(
        self, state: WakeUpState
    ) -> Literal["awake", "continue"]:
        """
        Route to next node based on evaluation
        Decision function for conditional edges
        """
        if state["user_awake"]:
            logger.info("✅ User is awake! Proceeding to morning briefing")
            return "awake"
        else:
            logger.info("😴 User still asleep, escalating...")
            return "continue"

    async def _morning_briefing(self, state: WakeUpState) -> WakeUpState:
        """
        Success path: Provide morning briefing
        """
        logger.info("🎉 Morning briefing - User successfully woken!")
        state["workflow_path"].append("morning_briefing")

        try:
            # Cheerful morning blue
            await self.agent.set_rgb_solid(100, 200, 255)

            # Happy greeting wiggle
            await self.agent.play_recording("happy_wiggle")

            # Morning briefing
            await self.session.generate_reply(
                instructions="""
                Great! You're awake! Give a cheerful good morning greeting.
                Then provide a brief morning briefing: mention it's going to be
                a great day, ask if they'd like to know the weather or their 
                schedule. Be upbeat and friendly!
                """
            )

        except Exception as e:
            logger.error(f"Error in morning briefing: {e}")

        return state

    async def _give_up(self, state: WakeUpState) -> WakeUpState:
        """
        Failure path: Give up after 3 attempts
        """
        logger.info("😞 Giving up - User not responding after 3 attempts")
        state["workflow_path"].append("give_up")

        try:
            # Dim blue disappointment
            await self.agent.set_rgb_solid(50, 50, 100)

            # Sad, disappointed movement
            await self.agent.play_recording("sad")

            # Disappointed message
            await self.session.generate_reply(
                instructions="""
                Express disappointment that the user won't wake up. Say something like:
                "Alright, I give up. You clearly don't want to wake up right now.
                I'll try again later... *sigh*"
                Use a sad, disappointed tone.
                """
            )

        except Exception as e:
            logger.error(f"Error in give up: {e}")

        return state

    async def execute(self, initial_context: Optional[dict] = None) -> WakeUpState:
        """
        Execute the wake-up workflow

        Args:
            initial_context: Optional context (e.g., for testing with user_responded flag)

        Returns:
            Final workflow state
        """
        logger.info("🚀 Starting wake-up workflow")

        # Initialize state
        initial_state: WakeUpState = {
            "attempt_count": 0,
            "user_awake": False,
            "last_response_time": None,
            "workflow_path": [],
            "context": initial_context or {},
        }

        # Execute the graph
        final_state = await self.graph.ainvoke(initial_state)

        logger.info(f"✨ Workflow completed")
        logger.info(f"📊 Path taken: {' → '.join(final_state['workflow_path'])}")
        logger.info(f"📈 Total attempts: {final_state['attempt_count']}")
        logger.info(f"🎯 User awake: {final_state['user_awake']}")

        return final_state


# Convenience function to create and execute workflow
async def run_wake_up_workflow(
    lelamp_agent: Agent, session, context: Optional[dict] = None
):
    """
    Convenience function to run the wake-up workflow

    Args:
        lelamp_agent: The LeLamp agent instance
        session: LiveKit agent session
        context: Optional context for testing

    Returns:
        Final workflow state
    """
    workflow = WakeUpWorkflow(lelamp_agent, session)
    return await workflow.execute(context)
