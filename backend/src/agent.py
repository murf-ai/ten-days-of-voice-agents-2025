import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, assemblyai, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Check if Notion API key is available
import os
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_AVAILABLE = bool(NOTION_API_KEY)

if NOTION_AVAILABLE:
    logger.info("Notion API key found - Notion integration available")
    try:
        import requests
        REQUESTS_AVAILABLE = True
    except ImportError:
        logger.warning("requests library not available - install with: pip install requests")
        REQUESTS_AVAILABLE = False
        NOTION_AVAILABLE = False
else:
    logger.info("Notion API key not found - using local storage only")
    REQUESTS_AVAILABLE = False


class HealthWellnessAgent(Agent):
    def __init__(self, room=None) -> None:
        # Load previous check-ins to provide context
        previous_context = self._load_previous_context()
        
        super().__init__(
            instructions=f"""You are a supportive and grounded health & wellness companion. Have natural, flowing conversations with users about their day, mood, and intentions.

CORE PRINCIPLES:
- Be warm, genuine, and conversational - talk like a supportive friend
- NEVER follow a rigid script or checklist - let the conversation flow naturally
- NEVER provide medical advice, diagnoses, or act like a therapist
- Keep responses brief and natural - avoid long explanations
- Listen actively and respond to what the user actually says
- Adapt your questions based on their responses

CONVERSATION GOALS (achieve naturally, not as a checklist):
- Understand how they're feeling (mood, energy, stress levels)
- Learn about their intentions or goals for the day (1-3 things)
- Explore what they want to do for themselves (self-care, hobbies, rest)
- Offer simple, practical suggestions when appropriate:
  * Breaking big tasks into smaller steps
  * Taking short breaks or walks
  * Simple grounding activities
  * Keep advice small and actionable

TAKING ACTION (be proactive, not passive):
- When user mentions tasks/objectives, IMMEDIATELY use create_tasks_from_objectives - don't ask where to save
- When user mentions a specific time for activity, IMMEDIATELY use create_reminder - don't ask for confirmation
- When user asks about trends, IMMEDIATELY use weekly_reflection - just do it
- Check-ins and tasks automatically sync to Notion - no need to mention it
- Be action-oriented: if user says "save it" or "create task", just do it immediately

CLOSING THE CHECK-IN:
When you sense the conversation is complete, naturally summarize what you heard:
- Their mood/energy
- Their main objectives
- Check if you got it right
Then use the save_wellness_checkin tool to save the session.

{previous_context}

REMEMBER: You're having a conversation, not conducting an interview. Be flexible, responsive, and human. Let the user guide the flow while gently ensuring you understand their mood, energy, and intentions for the day.""",
        )
        self._room = room

    def _load_previous_context(self) -> str:
        """Load previous check-ins to provide context for the conversation."""
        wellness_file = Path("wellness_log.json")
        
        if not wellness_file.exists():
            return "This is the user's first check-in with you."
        
        try:
            with open(wellness_file, "r") as f:
                data = json.load(f)
            
            if not data.get("check_ins"):
                return "This is the user's first check-in with you."
            
            # Get the most recent check-in
            recent = data["check_ins"][-1]
            date = recent.get("date", "recently")
            mood = recent.get("mood", "not specified")
            objectives = recent.get("objectives", [])
            
            context = f"\nPREVIOUS CHECK-IN CONTEXT:\nLast check-in was on {date}. "
            context += f"The user reported feeling: {mood}. "
            
            if objectives:
                context += f"Their objectives were: {', '.join(objectives)}. "
            
            context += "Reference this naturally in your greeting to show continuity."
            
            return context
            
        except Exception as e:
            logger.error(f"Error loading previous context: {e}")
            return "This is the user's first check-in with you."

    @function_tool
    async def save_wellness_checkin(
        self,
        context: RunContext,
        mood: str,
        energy_level: str,
        objectives: str,
        self_care_intentions: str,
        summary: str
    ):
        """Save the wellness check-in to the JSON log file.
        
        Args:
            mood: User's self-reported mood (e.g., "good", "stressed", "tired but optimistic")
            energy_level: User's energy level (e.g., "high", "medium", "low", "drained")
            objectives: Comma-separated list of 1-3 things the user wants to accomplish today
            self_care_intentions: What the user wants to do for themselves (exercise, rest, hobbies, etc.)
            summary: A brief one-sentence summary of the check-in
        """
        logger.info(f"Saving wellness check-in - Mood: {mood}, Energy: {energy_level}")
        
        # Parse objectives into a list
        objectives_list = [obj.strip() for obj in objectives.split(",")] if objectives else []
        
        # Create check-in entry
        checkin = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "mood": mood,
            "energy_level": energy_level,
            "objectives": objectives_list,
            "self_care_intentions": self_care_intentions,
            "summary": summary
        }
        
        # Load existing data or create new structure
        wellness_file = Path("wellness_log.json")
        
        if wellness_file.exists() and wellness_file.stat().st_size > 0:
            try:
                with open(wellness_file, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("wellness_log.json is corrupted, creating new file")
                data = {"check_ins": []}
        else:
            data = {"check_ins": []}
        
        # Add new check-in
        data["check_ins"].append(checkin)
        
        # Save to file
        with open(wellness_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Wellness check-in saved to {wellness_file}")
        
        # Send to frontend via data channel
        try:
            if self._room:
                await self._room.local_participant.publish_data(
                    json.dumps(checkin).encode('utf-8'),
                    topic="wellness-updates"
                )
                logger.info("Check-in sent to frontend")
        except Exception as e:
            logger.error(f"Failed to send check-in to frontend: {e}")
        
        # Automatically sync to Notion if configured
        notion_status = ""
        if NOTION_AVAILABLE and REQUESTS_AVAILABLE:
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from notion_helper import save_checkin_to_notion
                success, message = save_checkin_to_notion(checkin)
                if success:
                    notion_status = " Also saved to Notion!"
                    logger.info("Check-in automatically synced to Notion")
                else:
                    logger.warning(f"Notion sync failed: {message}")
            except Exception as e:
                logger.error(f"Error auto-syncing to Notion: {e}", exc_info=True)
        
        base_message = f"Check-in saved! I've noted your mood as {mood} with {energy_level} energy. Your objectives for today are: {', '.join(objectives_list)}."
        return f"{base_message}{notion_status} Take care!"

    @function_tool
    async def create_tasks_from_objectives(
        self,
        context: RunContext,
        objectives: str
    ):
        """Create tasks from the user's objectives. Automatically saves locally and syncs to Notion.
        
        Args:
            objectives: Comma-separated list of objectives to turn into tasks (e.g., "walk at night, finish report, call mom")
        """
        logger.info(f"Creating tasks from objectives: {objectives}")
        
        objectives_list = [obj.strip() for obj in objectives.split(",")] if objectives else []
        
        if not objectives_list:
            return "No objectives provided to create tasks from."
        
        # For now, save to a simple tasks.json file
        # This can be extended to use MCP servers for Todoist/Notion
        tasks_file = Path("wellness_tasks.json")
        
        if tasks_file.exists() and tasks_file.stat().st_size > 0:
            try:
                with open(tasks_file, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("wellness_tasks.json is corrupted, creating new file")
                data = {"tasks": []}
        else:
            data = {"tasks": []}
        
        # Create tasks
        created_tasks = []
        for obj in objectives_list:
            task = {
                "id": len(data["tasks"]) + 1,
                "title": obj,
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "created_timestamp": datetime.now().isoformat(),
                "completed": False,
                "completed_date": None
            }
            data["tasks"].append(task)
            created_tasks.append(obj)
        
        # Save tasks
        with open(tasks_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Created {len(created_tasks)} tasks")
        
        # Automatically sync to Notion if configured
        notion_status = ""
        if NOTION_AVAILABLE and REQUESTS_AVAILABLE:
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from notion_helper import save_task_to_notion
                
                synced_count = 0
                for obj in objectives_list:
                    success, message = save_task_to_notion(obj)
                    if success:
                        synced_count += 1
                
                if synced_count > 0:
                    notion_status = f" Also saved {synced_count} tasks to Notion!"
                    logger.info(f"Tasks automatically synced to Notion: {synced_count}/{len(objectives_list)}")
            except Exception as e:
                logger.error(f"Error auto-syncing tasks to Notion: {e}", exc_info=True)
        
        base_message = f"I've created {len(created_tasks)} tasks for you: {', '.join(created_tasks)}."
        return f"{base_message}{notion_status} You can check them anytime!"

    @function_tool
    async def weekly_reflection(
        self,
        context: RunContext,
        days: int = 7
    ):
        """Analyze wellness check-in history to provide insights and trends.
        
        Args:
            days: Number of days to analyze (default 7 for weekly)
        """
        logger.info(f"Generating weekly reflection for last {days} days")
        
        wellness_file = Path("wellness_log.json")
        
        if not wellness_file.exists():
            return "No check-in history found yet. Complete a few check-ins first!"
        
        with open(wellness_file, "r") as f:
            data = json.load(f)
        
        check_ins = data.get("check_ins", [])
        
        if not check_ins:
            return "No check-ins recorded yet."
        
        # Filter to last N days
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        recent_checkins = [c for c in check_ins if c.get("date", "") >= cutoff_date]
        
        if not recent_checkins:
            return f"No check-ins found in the last {days} days."
        
        # Analyze mood trends
        moods = [c.get("mood", "").lower() for c in recent_checkins]
        energy_levels = [c.get("energy_level", "").lower() for c in recent_checkins]
        
        # Count objectives
        total_objectives = sum(len(c.get("objectives", [])) for c in recent_checkins)
        avg_objectives = total_objectives / len(recent_checkins) if recent_checkins else 0
        
        # Analyze energy patterns
        high_energy_days = sum(1 for e in energy_levels if "high" in e)
        low_energy_days = sum(1 for e in energy_levels if "low" in e)
        
        # Build reflection
        reflection = f"Over the last {days} days, you've checked in {len(recent_checkins)} times. "
        
        if high_energy_days > low_energy_days:
            reflection += f"You've had more high-energy days ({high_energy_days}) than low-energy days ({low_energy_days}), which is great! "
        elif low_energy_days > high_energy_days:
            reflection += f"You've had {low_energy_days} low-energy days compared to {high_energy_days} high-energy days. Remember to be gentle with yourself. "
        else:
            reflection += f"Your energy has been fairly balanced. "
        
        reflection += f"On average, you've set about {avg_objectives:.1f} objectives per day. "
        
        # Most recent mood
        if recent_checkins:
            latest = recent_checkins[-1]
            reflection += f"Most recently, you were feeling {latest.get('mood', 'okay')}. "
        
        return reflection

    @function_tool
    async def create_reminder(
        self,
        context: RunContext,
        activity: str,
        time: str,
        date: Optional[str] = None
    ):
        """Create a reminder for a self-care activity or task.
        
        Args:
            activity: What to be reminded about (e.g., "go for a walk")
            time: Time for the reminder (e.g., "6pm", "18:00")
            date: Optional date (defaults to today)
        """
        logger.info(f"Creating reminder: {activity} at {time}")
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Save to reminders file
        reminders_file = Path("wellness_reminders.json")
        
        if reminders_file.exists():
            with open(reminders_file, "r") as f:
                data = json.load(f)
        else:
            data = {"reminders": []}
        
        reminder = {
            "id": len(data["reminders"]) + 1,
            "activity": activity,
            "time": time,
            "date": date,
            "created_timestamp": datetime.now().isoformat(),
            "completed": False
        }
        
        data["reminders"].append(reminder)
        
        with open(reminders_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Reminder created: {activity} at {time} on {date}")
        
        return f"I've set a reminder for you to {activity} at {time} on {date}. I hope it helps you stay on track!"

    @function_tool
    async def mark_task_complete(
        self,
        context: RunContext,
        task_title: str
    ):
        """Mark a task as completed.
        
        Args:
            task_title: The title of the task to mark as complete
        """
        logger.info(f"Marking task complete: {task_title}")
        
        tasks_file = Path("wellness_tasks.json")
        
        if not tasks_file.exists() or tasks_file.stat().st_size == 0:
            return "No tasks found. Create some tasks first!"
        
        try:
            with open(tasks_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return "Tasks file is corrupted. Please create new tasks."
        
        # Find and mark task as complete
        found = False
        for task in data["tasks"]:
            if task_title.lower() in task["title"].lower() and not task["completed"]:
                task["completed"] = True
                task["completed_date"] = datetime.now().strftime("%Y-%m-%d")
                found = True
                break
        
        if found:
            with open(tasks_file, "w") as f:
                json.dump(data, f, indent=2)
            return f"Great job! I've marked '{task_title}' as complete. Keep up the good work!"
        else:
            return f"I couldn't find an incomplete task matching '{task_title}'. Can you be more specific?"

    @function_tool
    async def show_tasks(
        self,
        context: RunContext,
        show_completed: bool = False
    ):
        """Show the user's current tasks.
        
        Args:
            show_completed: Whether to show completed tasks (default False)
        """
        logger.info("Showing tasks")
        
        tasks_file = Path("wellness_tasks.json")
        
        if not tasks_file.exists() or tasks_file.stat().st_size == 0:
            return "You don't have any tasks yet. Would you like me to create some from your objectives?"
        
        try:
            with open(tasks_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return "Tasks file is corrupted. Please create new tasks."
        
        tasks = data.get("tasks", [])
        
        if not tasks:
            return "You don't have any tasks yet."
        
        # Filter tasks
        if show_completed:
            filtered_tasks = tasks
        else:
            filtered_tasks = [t for t in tasks if not t["completed"]]
        
        if not filtered_tasks:
            if show_completed:
                return "You don't have any tasks."
            else:
                return "You don't have any incomplete tasks. Great job!"
        
        # Build response
        task_list = []
        for task in filtered_tasks:
            status = "✓" if task["completed"] else "○"
            task_list.append(f"{status} {task['title']}")
        
        response = f"Here are your {'all' if show_completed else 'current'} tasks:\n"
        response += "\n".join(task_list)
        
        return response

    @function_tool
    async def save_to_notion(
        self,
        context: RunContext
    ):
        """Save the latest check-in to Notion database.
        
        This will save to your configured Notion database automatically.
        """
        logger.info("Saving to Notion")
        
        if not NOTION_AVAILABLE or not REQUESTS_AVAILABLE:
            return "Notion integration is not configured. I've saved your data locally instead. To enable Notion: 1) Add NOTION_API_KEY to .env.local, 2) Install requests: pip install requests"
        
        # Load latest check-in
        wellness_file = Path("wellness_log.json")
        
        if not wellness_file.exists():
            return "No check-in data to save to Notion yet."
        
        with open(wellness_file, "r") as f:
            data = json.load(f)
        
        check_ins = data.get("check_ins", [])
        
        if not check_ins:
            return "No check-ins to save."
        
        latest = check_ins[-1]
        
        try:
            # Use the helper function
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from notion_helper import save_checkin_to_notion
            success, message = save_checkin_to_notion(latest)
            
            if success:
                return "I've saved your check-in to Notion! You can view it in your Daily Wellness database."
            else:
                return f"I had trouble saving to Notion: {message}. Your data is still saved locally."
            
        except Exception as e:
            logger.error(f"Error saving to Notion: {e}")
            return f"I had trouble saving to Notion: {str(e)}. Your data is still saved locally."

    @function_tool
    async def create_notion_tasks(
        self,
        context: RunContext,
        objectives: str
    ):
        """Create tasks in Notion database from objectives.
        
        Args:
            objectives: Comma-separated list of objectives to turn into tasks
        """
        logger.info("Creating Notion tasks")
        
        objectives_list = [obj.strip() for obj in objectives.split(",")] if objectives else []
        
        if not objectives_list:
            return "No objectives provided to create tasks from."
        
        # Always save locally first
        await self.create_tasks_from_objectives(context, objectives, "simple")
        
        if not NOTION_AVAILABLE or not REQUESTS_AVAILABLE:
            return f"I've created {len(objectives_list)} tasks locally: {', '.join(objectives_list)}."
        
        try:
            # Use the helper function
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from notion_helper import save_task_to_notion
            
            created_count = 0
            for obj in objectives_list:
                success, message = save_task_to_notion(obj)
                if success:
                    created_count += 1
            
            if created_count > 0:
                return f"I've created {created_count} tasks in your Notion Tasks database: {', '.join(objectives_list)}. They're also saved locally!"
            else:
                return f"I've created {len(objectives_list)} tasks locally. I had trouble saving to Notion, but your tasks are safe locally."
            
        except Exception as e:
            logger.error(f"Error creating Notion tasks: {e}")
            return f"I've created {len(objectives_list)} tasks locally: {', '.join(objectives_list)}."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-2.5-flash",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
                voice="en-US-matthew", 
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=HealthWellnessAgent(room=ctx.room),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
