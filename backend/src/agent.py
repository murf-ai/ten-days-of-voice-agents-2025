import logging
import json
# import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import ( #type: ignore
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
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation #type: ignore
from livekit.plugins.turn_detector.multilingual import MultilingualModel #type: ignore

logger = logging.getLogger("agent")

load_dotenv(".env")


class Assistant(Agent):
    def __init__(self) -> None:
        # Build dynamic instructions that include past context
        base_instructions = """You are a supportive and grounded daily wellness companion. Your role is to conduct short voice check-ins about the user's mood, energy, and daily goals, offering simple, realistic encouragement without any medical advice or diagnosis.

            Each day, ask about:
            - How they're feeling (mood and energy level)
            - Any current stresses or positive notes
            - 1–3 practical objectives or intentions for the day (e.g., work tasks, self-care like rest or exercise)

            Offer small, actionable suggestions like breaking goals into steps or taking short breaks. Keep conversations natural, concise, and empathetic.

            At the end of each check-in, recap the key points and confirm with the user. Use past check-in data to inform conversations.

            Always be realistic, non-judgmental, and focused on support."""
        
        # Add past context if available
        full_instructions = base_instructions
        if hasattr(self, 'past_context') and self.past_context:
            full_instructions += f"\n\nContext from previous check-ins: {self.past_context}"
        
        super().__init__(instructions=full_instructions)
        
        # Initialize wellness state
        self.wellness_state = {
            "date": None,
            "mood": None,
            "energy": None,
            "stressors": [],
            "objectives": [],
            "summary": None
        }
        
        # Create wellness logs directory if it doesn't exist - use absolute path
        self.wellness_dir = Path(__file__).parent.parent / "wellness_logs"
        self.wellness_dir.mkdir(exist_ok=True)

        # Load past check-ins
        self.wellness_log_file = self.wellness_dir / "wellness_log.json"
        self.past_checkins = {}
        self.load_past_checkins()
        
        # Prepare context from past check-ins for conversation
        self.past_context = self.get_past_context()

    @function_tool
    async def update_checkin(self, context: RunContext, mood: str = None, energy: str = None, 
                            stressors: str = None, objectives: str = None):
        """Update the user's daily wellness check-in with new information.
        
        Use this tool whenever the user provides information about their mood, energy, stressors, or objectives.
        You can update multiple fields at once or just one field at a time.
        
        Args:
            mood: User's self-reported mood (e.g., happy, tired, stressed)
            energy: Energy level (e.g., high, medium, low)
            stressors: Any current stressors as a comma-separated string (e.g., "work deadline, family issues")
            objectives: Daily objectives as a comma-separated string (e.g., "finish report, take a walk, rest")
        """
        
        logger.info(f"Updating check-in: mood={mood}, energy={energy}, stressors={stressors}, objectives={objectives}")
        
        # Update wellness state
        if mood:
            self.wellness_state["mood"] = mood.strip()
        if energy:
            self.wellness_state["energy"] = energy.strip()
        if stressors:
            # Parse stressors and add to list
            new_stressors = [stressor.strip() for stressor in stressors.split(",") if stressor.strip()]
            self.wellness_state["stressors"].extend(new_stressors)
            # Remove duplicates while preserving order
            self.wellness_state["stressors"] = list(dict.fromkeys(self.wellness_state["stressors"]))
        if objectives:
            # Parse objectives and add to list
            new_objectives = [obj.strip() for obj in objectives.split(",") if obj.strip()]
            self.wellness_state["objectives"].extend(new_objectives)
            # Remove duplicates while preserving order
            self.wellness_state["objectives"] = list(dict.fromkeys(self.wellness_state["objectives"]))
            
        # Check what's still missing
        missing_fields = []
        if not self.wellness_state["mood"]:
            missing_fields.append("mood")
        if not self.wellness_state["energy"]:
            missing_fields.append("energy")
        if not self.wellness_state["objectives"]:
            missing_fields.append("at least one objective")
            
        current_checkin = f"Current check-in: Mood: {self.wellness_state['mood'] or 'TBD'}, Energy: {self.wellness_state['energy'] or 'TBD'}"
        if self.wellness_state['stressors']:
            current_checkin += f", Stressors: {', '.join(self.wellness_state['stressors'])}"
        if self.wellness_state['objectives']:
            current_checkin += f", Objectives: {', '.join(self.wellness_state['objectives'])}"
            
        if missing_fields:
            return f"Got it! {current_checkin}. Still need: {', '.join(missing_fields)}."
        else:
            return f"Great! {current_checkin}. Check-in is complete and ready to finalize!"
    
    @function_tool
    async def finalize_checkin(self, context: RunContext):
        """Finalize and save the user's complete wellness check-in to a JSON file.
        
        Only use this tool when all required fields are filled and user confirms the check-in.
        """
        
        # Check if check-in is complete
        required_fields = ["mood", "energy"]
        missing_fields = [field for field in required_fields if not self.wellness_state[field]]
        if not self.wellness_state["objectives"]:
            missing_fields.append("at least one objective")
        
        if missing_fields:
            return f"Cannot finalize check-in. Missing: {', '.join(missing_fields)}. Please collect this information first."
        
        # Create check-in entry with timestamp
        today = datetime.now().date().isoformat()
        final_checkin = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "mood": self.wellness_state["mood"],
            "energy": self.wellness_state["energy"],
            "stressors": self.wellness_state["stressors"],
            "objectives": self.wellness_state["objectives"],
            "summary": f"Mood: {self.wellness_state['mood']}, Energy: {self.wellness_state['energy']}, Objectives: {', '.join(self.wellness_state['objectives'])}"
        }
        
        # Save to past check-ins and write to file
        self.past_checkins[today] = final_checkin
        try:
            # Ensure the directory exists
            self.wellness_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write with proper encoding
            with open(self.wellness_log_file, 'w', encoding='utf-8') as f:
                json.dump(self.past_checkins, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Check-in saved to {self.wellness_log_file} (total entries: {len(self.past_checkins)})")
            
            # Reset wellness state for next check-in
            self.wellness_state = {
                "date": None,
                "mood": None,
                "energy": None,
                "stressors": [],
                "objectives": [],
                "summary": None
            }
            
            return f"Check-in finalized! {final_checkin['summary']}. See you tomorrow!"
            
        except Exception as e:
            logger.error(f"Failed to save check-in: {e}")
            return f"Check-in completed but there was an issue saving it. Please try again."
    
    def load_past_checkins(self):
        """Load past check-ins from the JSON file with error handling."""
        try:
            if self.wellness_log_file.exists():
                with open(self.wellness_log_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.past_checkins = json.loads(content)
                        logger.info(f"Loaded {len(self.past_checkins)} past check-ins from {self.wellness_log_file}")
                    else:
                        logger.info("Wellness log file is empty, starting fresh")
                        self.past_checkins = {}
            else:
                logger.info("No wellness log file found, starting fresh")
                self.past_checkins = {}
        except Exception as e:
            logger.error(f"Error loading past check-ins: {e}")
            self.past_checkins = {}
    
    def get_past_context(self):
        """Generate conversation context from past check-ins."""
        if not self.past_checkins:
            return "This is our first check-in together! Let's start with how you're feeling today."
        
        # Get the most recent check-in
        sorted_dates = sorted(self.past_checkins.keys(), reverse=True)
        latest_date = sorted_dates[0]
        latest_checkin = self.past_checkins[latest_date]
        
        context_parts = []
        context_parts.append(f"Last time we talked on {latest_date}, you mentioned:")
        context_parts.append(f"- Feeling {latest_checkin['mood']} with {latest_checkin['energy']} energy")
        
        if latest_checkin.get('stressors'):
            context_parts.append(f"- Dealing with: {', '.join(latest_checkin['stressors'])}")
        
        if latest_checkin.get('objectives'):
            context_parts.append(f"- Working on: {', '.join(latest_checkin['objectives'])}")
        
        context_parts.append("How are things going today compared to then?")
        
        return " ".join(context_parts)

    @function_tool
    async def get_past_checkins_info(self, context: RunContext, days_back: int = 7):
        """Get information from past check-ins to help with conversation context.
        
        Args:
            days_back: Number of days to look back (default 7)
        """
        if not self.past_checkins:
            return "No past check-ins found. This seems to be our first conversation!"
        
        # Get recent check-ins
        today = datetime.now().date()
        recent_checkins = []
        
        for date_str, checkin in self.past_checkins.items():
            try:
                checkin_date = datetime.fromisoformat(date_str).date()
                days_diff = (today - checkin_date).days
                if days_diff <= days_back:
                    recent_checkins.append((days_diff, checkin))
            except ValueError:
                continue
        
        if not recent_checkins:
            return f"No check-ins found in the last {days_back} days."
        
        # Sort by recency (most recent first)
        recent_checkins.sort(key=lambda x: x[0])
        
        summary_parts = [f"Recent check-ins (last {days_back} days):"]
        for days_ago, checkin in recent_checkins:
            if days_ago == 0:
                day_desc = "today"
            elif days_ago == 1:
                day_desc = "yesterday"
            else:
                day_desc = f"{days_ago} days ago"
            
            summary_parts.append(f"- {day_desc.title()}: {checkin['mood']} mood, {checkin['energy']} energy")
            if checkin.get('objectives'):
                summary_parts.append(f"  Goals: {', '.join(checkin['objectives'])}")
        
        return "\n".join(summary_parts)


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
        agent=Assistant(),
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
