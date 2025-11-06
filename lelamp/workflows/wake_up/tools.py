from livekit.agents import function_tool


@function_tool
async def get_dummy_calendar_data(self) -> dict:
    """
    Get the user's calendar data for today. Call this function when you need to see what 
    meetings, events, or tasks the user has scheduled for the day. This helps you inform 
    them about their daily schedule during the wake-up routine.
    
    Returns:
        A dictionary containing today's calendar events with titles, start times, and end times.
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
        return {"error": result}

