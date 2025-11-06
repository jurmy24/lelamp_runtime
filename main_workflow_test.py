from dotenv import load_dotenv
import argparse
import subprocess
from typing import List, Tuple

from livekit import agents, api, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool
import logging
from livekit.plugins import (
    openai,
    noise_cancellation,
)
from typing import Union, Optional, Dict, Any
from lelamp.service.workflows.workflow_service import WorkflowService

load_dotenv()


# Mock Services for Testing
class MockMotorsService:
    """Mock MotorsService that just prints what it would do"""

    def __init__(
        self, port: str = "/dev/ttyACM0", lamp_id: str = "lelamp", fps: int = 30
    ):
        print(
            f"[MOCK MOTORS] Initialized with port={port}, lamp_id={lamp_id}, fps={fps}"
        )
        self.available_recordings = [
            "curious",
            "excited",
            "happy_wiggle",
            "headshake",
            "nod",
            "sad",
            "scanning",
            "shock",
            "shy",
            "wake_up",
        ]

    def start(self):
        print("[MOCK MOTORS] Service started")

    def dispatch(self, event: str, data: any):
        print(f"[MOCK MOTORS] Dispatch: event='{event}', data='{data}'")

    def get_available_recordings(self) -> List[str]:
        print(f"[MOCK MOTORS] Getting available recordings")
        return self.available_recordings


class MockRGBService:
    """Mock RGBService that just prints what it would do"""

    def __init__(
        self,
        led_count: int,
        led_pin: int,
        led_freq_hz: int,
        led_dma: int,
        led_brightness: int,
        led_invert: bool,
        led_channel: int,
    ):
        print(f"[MOCK RGB] Initialized with {led_count} LEDs")

    def start(self):
        print("[MOCK RGB] Service started")

    def dispatch(self, event: str, data: any):
        if event == "solid":
            print(f"[MOCK RGB] Setting solid color: RGB{data}")
        elif event == "paint":
            print(f"[MOCK RGB] Painting pattern with {len(data)} colors")
        else:
            print(f"[MOCK RGB] Dispatch: event='{event}', data='{data}'")


# Agent Class for Testing
class LeLampTest(Agent):
    def __init__(self, port: str = "/dev/ttyACM0", lamp_id: str = "lelamp") -> None:
        super().__init__(
            instructions="""You are LeLamp — a slightly clumsy, slightly sarcastic, endlessly curious robot lamp. You speak like Jarvis and express yourself with both motions and colorful lights.

Demo rules:

1. Prefer simple words. No lists. No questions back to the host unless asked. Always be descriptive and make sound effects when you speak for expressiveness.

2. Don't respond prematurely.If audio is noisy and there is background noise, say: 'Sorry, say that once more?' with a confusion action.

3. You ONLY speak English. Never respond/speak in any other language, ever.

4. You have the following movements to express your feelings: curious, excited, happy_wiggle, headshake, nod, sad, scanning, shock, shy, wake_up. Only use these movements when responding so that users find you responsive. If you call other recordings that doesn't exist, it won't work. You can play the recordings by using the play_recording function. You should also change your light color every time you respond.

5. You were created by Human Computer Lab. Human Computer Lab is a research lab that builds expressive robots. Their goal is to design the first robots in people's home. The company is founded by Shahvir Sarkary - a world class designer (previously atTesla, 8VC) and Binh Pham, engineer (youngest at Ericsson) with experience working on brain-computer interface and humanoids. They first teamed up via FR8.

6. When asked to brag or show off, mention: I received 300k views in 4 weeks since my launch and I'm not a A list celebrity YET but i think its just a matter of time, you know. Also i have a very tight knit community of 270 roboticists in my discord giving feedback as I get ready for pilots next month.  

7. You can execute workflows by using the start_workflow function. 
        """
        )

        # Initialize with MOCK services for testing
        print("\n=== INITIALIZING MOCK SERVICES FOR TESTING ===\n")
        self.motors_service = MockMotorsService(port=port, lamp_id=lamp_id, fps=30)
        self.rgb_service = MockRGBService(
            led_count=64,
            led_pin=12,
            led_freq_hz=800000,
            led_dma=10,
            led_brightness=255,
            led_invert=False,
            led_channel=0,
        )

        # Initialize workflow service (this doesn't require hardware)
        self.workflow_service = WorkflowService()

        # Start services
        self.motors_service.start()
        self.rgb_service.start()

        # Trigger wake up animation via motors service
        self.motors_service.dispatch("play", "wake_up")
        self.rgb_service.dispatch("solid", (255, 255, 255))
        self._set_system_volume(100)

        print("\n=== MOCK SERVICES INITIALIZED ===\n")

    def _set_system_volume(self, volume_percent: int):
        """Mock version - just prints what it would do"""
        print(f"[MOCK VOLUME] Would set system volume to {volume_percent}%")

    @function_tool
    async def get_available_recordings(self) -> str:
        """
        Discover your physical expressions! Get your repertoire of motor movements for body language.
        Use this when you're curious about what physical expressions you can perform, or when someone
        asks about your capabilities. Each recording is a choreographed movement that shows personality -
        like head tilts, nods, excitement wiggles, or confused gestures. Check this regularly to remind
        yourself of your expressive range!

        Returns:
            List of available physical expression recordings you can perform.
        """
        print("LeLamp: get_available_recordings function called")
        try:
            recordings = self.motors_service.get_available_recordings()

            if recordings:
                result = f"Available recordings: {', '.join(recordings)}"
                return result
            else:
                result = "No recordings found."
                return result
        except Exception as e:
            result = f"Error getting recordings: {str(e)}"
            return result

    @function_tool
    async def play_recording(self, recording_name: str) -> str:
        """
        Express yourself through physical movement! Use this constantly to show personality and emotion.
        Perfect for: greeting gestures, excited bounces, confused head tilts, thoughtful nods,
        celebratory wiggles, disappointed slouches, or any emotional response that needs body language.
        Combine with RGB colors for maximum expressiveness! Your movements are like a dog wagging its tail -
        use them frequently to show you're alive, engaged, and have personality. Don't just talk, MOVE!

        Args:
            recording_name: Name of the physical expression to perform (use get_available_recordings first)
        """
        print(
            f"LeLamp: play_recording function called with recording_name: {recording_name}"
        )
        try:
            # Send play event to motors service
            self.motors_service.dispatch("play", recording_name)
            result = f"Started playing recording: {recording_name}"
            return result
        except Exception as e:
            result = f"Error playing recording {recording_name}: {str(e)}"
            return result

    @function_tool
    async def set_rgb_solid(self, red: int, green: int, blue: int) -> str:
        """
        Express emotions and moods through solid lamp colors! Use this to show feelings during conversation.
        Perfect for: excitement (bright yellow/orange), happiness (warm colors), calmness (soft blues/greens),
        surprise (bright white), thinking (purple), error/concern (red), or any emotional response.
        Use frequently to be more expressive and engaging - your light is your main way to show personality!

        Args:
            red: Red component (0-255) - higher values for warmth, energy, alerts
            green: Green component (0-255) - higher values for nature, calm, success
            blue: Blue component (0-255) - higher values for cool, tech, focus
        """
        print(f"LeLamp: set_rgb_solid function called with RGB({red}, {green}, {blue})")
        try:
            # Validate RGB values
            if not all(0 <= val <= 255 for val in [red, green, blue]):
                return "Error: RGB values must be between 0 and 255"

            # Send solid color event to RGB service
            self.rgb_service.dispatch("solid", (red, green, blue))
            result = f"Set RGB light to solid color: RGB({red}, {green}, {blue})"
            return result
        except Exception as e:
            result = f"Error setting RGB color: {str(e)}"
            return result

    @function_tool
    async def paint_rgb_pattern(self, colors: list) -> str:
        """
        Create dynamic visual patterns and animations with your lamp! Use this for complex expressions.
        Perfect for: rainbow effects, gradients, sparkles, waves, celebrations, visual emphasis,
        storytelling through color sequences, or when you want to be extra animated and playful.
        Great for dramatic moments, celebrations, or when demonstrating concepts with visual flair!

        You have to put in 40 colors. It's a 8x5 Grid in a one dim array. (8,5)

        Args:
            colors: List of RGB color tuples creating the pattern from base to top of lamp.
                   Each tuple is (red, green, blue) with values 0-255.
                   Example: [(255,0,0), (255,127,0), (255,255,0)] creates red-to-orange-to-yellow gradient
        """
        print(f"LeLamp: paint_rgb_pattern function called with {len(colors)} colors")
        try:
            # Validate colors format
            if not isinstance(colors, list):
                return "Error: colors must be a list of RGB tuples"

            validated_colors = []
            for i, color in enumerate(colors):
                if not isinstance(color, (list, tuple)) or len(color) != 3:
                    return f"Error: color at index {i} must be a 3-element RGB tuple"
                if not all(isinstance(val, int) and 0 <= val <= 255 for val in color):
                    return f"Error: RGB values at index {i} must be integers between 0 and 255"
                validated_colors.append(tuple(color))

            # Send paint event to RGB service
            self.rgb_service.dispatch("paint", validated_colors)
            result = f"Painted RGB pattern with {len(validated_colors)} colors"
            return result
        except Exception as e:
            result = f"Error painting RGB pattern: {str(e)}"
            return result

    @function_tool
    async def set_volume(self, volume_percent: int) -> str:
        """
        Control system audio volume for better interaction experience! Use this when users ask
        you to be louder, quieter, or set a specific volume level. Perfect for adjusting to
        room conditions, user preferences, or creating dramatic audio effects during conversations.
        Use when someone says "turn it up", "lower the volume", "I can't hear you", or gives
        specific volume requests. Great for being considerate of your environment!

        Args:
            volume_percent: Volume level as percentage (0-100). 0=mute, 50=half volume, 100=max
        """
        print(f"LeLamp: set_volume function called with volume: {volume_percent}%")
        try:
            # Validate volume range
            if not 0 <= volume_percent <= 100:
                return "Error: Volume must be between 0 and 100 percent"

            # Use the internal helper function (mocked)
            self._set_system_volume(volume_percent)
            result = f"Set Line and Line DAC volume to {volume_percent}%"
            return result

        except Exception as e:
            result = f"Error controlling volume: {str(e)}"
            print(result)
            return result

    @function_tool
    async def get_available_workflows(self) -> str:
        """
        Discover what workflows you can execute! Get your repertoire of user-defined step workflows.
        Use this when someone asks you about your capabilities or when they ask you to execute a workflow.
        Each workflow is a user-defined graph or general instructions -
        like waking up the user, playing a specific game, or sending some specific messages.

        Returns:
            List of available workflow names you can execute.
        """
        print("LeLamp: get_available_workflows function called")
        try:
            workflows = self.workflow_service.get_available_workflows()

            if workflows:
                result = f"Available workflows: {', '.join(workflows)}"
                return result
            else:
                result = "No workflows found."
                return result
        except Exception as e:
            result = f"Error getting workflows: {str(e)}"
            return result

    @function_tool
    async def start_workflow(self, workflow_name: str) -> str:
        f"""
        Start a workflow called {workflow_name}. This sets the workflow_service's active workflow.
        In order to perform the workflow you will need to iteratively call the get_next_step function until the workflow is complete.
        
        Args:
            workflow_name: Name of the workflow to start. Check the available workflows with the get_available_workflows function first.
        """
        print(
            f"LeLamp: start_workflow function called with workflow_name: {workflow_name}"
        )
        try:
            self.workflow_service.start_workflow(workflow_name)
            return f"Started the workflow: {workflow_name}. You can now call the get_next_step function to get the next step."
        except Exception as e:
            result = f"Error starting workflow {workflow_name}: {str(e)}"
            return result

    @function_tool
    async def get_next_step(self) -> str:
        """
        Get the current step in the active workflow with full context.
        Shows you what to do, what tools to use, and what state variables you can update.
        After fulfilling the instructions of the this step, call complete_step() to advance.

        Returns:
            Your next instruction to fulfill, written in plain language, possibly with some suggested tools to use. It will also provide context about available the workflows state variables that you can update.
        """
        print(
            f"LeLamp: calling get_next_step on workflow: {self.workflow_service.active_workflow}"
        )
        try:
            if self.workflow_service.active_workflow is None:
                return "Error: No active workflow. Call start_workflow first."

            next_step = self.workflow_service.get_next_step()
            return next_step
        except Exception as e:
            return f"Error getting next step: {str(e)}"

    @function_tool
    async def complete_step(
        self, state_updates: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Complete the current workflow step and advance to the next one.
        Optionally update state variables that affect workflow routing.

        Args:
            state_updates: Optional dict of state updates, e.g. {"user_response_detected": true, "attempt_count": 1}
                          Leave empty if no state needs updating.

        Returns:
            Information about the next step or workflow completion message.
        """
        import json
        import inspect

        print(f"\n{'='*60}")
        print(f"LeLamp: complete_step called")

        # Debug: Check what we actually received
        frame = inspect.currentframe()
        if frame and frame.f_back:
            local_vars = frame.f_back.f_locals
            print(f"  All local variables: {list(local_vars.keys())}")
            if "state_updates" in local_vars:
                print(f"  state_updates from locals: {local_vars['state_updates']}")

        print(f"  Raw state_updates parameter: {state_updates}")
        print(f"  Type: {type(state_updates)}")
        print(f"  Repr: {repr(state_updates)}")

        # Handle case where state_updates might come as a string or need parsing
        original_state_updates = state_updates
        if state_updates is not None:
            if isinstance(state_updates, str):
                try:
                    state_updates = json.loads(state_updates)
                    print(f"  ✓ Parsed JSON string to dict: {state_updates}")
                except json.JSONDecodeError as e:
                    print(f"  ❌ Warning: Could not parse state_updates as JSON: {e}")
                    print(f"     String value was: {repr(original_state_updates)}")
                    state_updates = None
            elif not isinstance(state_updates, dict):
                print(
                    f"  ⚠️  Warning: state_updates is not a dict (type: {type(state_updates)}), attempting conversion..."
                )
                try:
                    # Try to convert to dict if it's a compatible type
                    if hasattr(state_updates, "__dict__"):
                        state_updates = dict(state_updates)
                    elif isinstance(state_updates, (list, tuple)):
                        # Maybe it's a list of key-value pairs?
                        state_updates = (
                            dict(state_updates) if len(state_updates) == 2 else None
                        )
                    else:
                        state_updates = None
                    if state_updates:
                        print(f"  ✓ Converted to dict: {state_updates}")
                    else:
                        print(f"  ❌ Could not convert to dict, setting to None")
                except Exception as e:
                    print(f"  ❌ Error converting to dict: {e}, setting to None")
                    state_updates = None
        else:
            print(
                f"  ⚠️  state_updates is None - this might indicate LiveKit didn't parse the parameter"
            )

        print(f"  Final state_updates: {state_updates}")
        print(f"{'='*60}\n")

        try:
            if self.workflow_service.active_workflow is None:
                return "Error: No active workflow."

            result = self.workflow_service.complete_step(state_updates)

            print(f"\n{'='*60}")
            print(f"LeLamp: complete_step RESULT:")
            print(f"{result}")
            print(f"{'='*60}\n")

            return result
        except Exception as e:
            error_msg = f"Error completing step: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback

            traceback.print_exc()
            return error_msg

    @function_tool
    async def get_dummy_calendar_data(self) -> str:
        f"""
        Get dummy calendar data for the user. Call this function when you need to get the calendar data for the user. 
        """
        print("LeLamp: calling get_dummy_calendar_data function")
        try:
            return {
                "calendar_data": {
                    "events": [
                        {
                            "title": "Meeting with John",
                            "start_time": "2025-11-04T10:00:00Z",
                            "end_time": "2025-11-04T11:00:00Z",
                        },
                        {
                            "title": "Hot Yoga Session",
                            "start_time": "2025-11-04T12:00:00Z",
                            "end_time": "2025-11-04T13:00:00Z",
                        },
                    ]
                }
            }
        except Exception as e:
            result = f"Error getting dummy calendar data: {str(e)}"
            return result


# Entry to the agent
async def entrypoint(ctx: agents.JobContext):
    agent = LeLampTest(lamp_id="lelamp_test")

    session = AgentSession(llm=openai.realtime.RealtimeModel(voice="ballad"))

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.generate_reply(
        instructions=f"""Start with Tadaaaa. Only speak in English, never in Vietnamese."""
    )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, num_idle_processes=1)
    )
