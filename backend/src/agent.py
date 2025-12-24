import logging
import json
import os
import random
from datetime import datetime
from typing import Dict, Any, Optional, List
import asyncio
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("improv_battle_agent")
logging.basicConfig(level=logging.INFO)
load_dotenv(dotenv_path=".env.local")
load_dotenv(dotenv_path=".env")

# Data file paths
SCENARIOS_FILE = os.path.join(os.path.dirname(__file__), "../shared-data/day10_scenarios.json")

# Global state for current session
class ImprovGameState:
    def __init__(self):
        self.player_name: Optional[str] = None
        self.current_round: int = 0
        self.max_rounds: int = 4  # 4 scenarios per game
        self.rounds: List[Dict[str, Any]] = []  # list of {"scenario": str, "player_response": str, "host_reaction": str}
        self.phase: str = "intro"  # "intro" | "awaiting_improv" | "reacting" | "done"
        self.current_scenario: Optional[Dict[str, Any]] = None
        self.scenarios_used: List[str] = []
        self.all_scenarios: List[Dict[str, Any]] = []
        self.improv_count: int = 0  # Counter to track how many times player has improvised
        self.language = "hinglish"  # Support for Hindi/Hinglish

game_state = ImprovGameState()

def load_scenarios() -> List[Dict[str, Any]]:
    """Load improv scenarios from JSON file."""
    try:
        with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scenarios", [])
    except FileNotFoundError:
        logger.error(f"Scenarios file not found at {SCENARIOS_FILE}")
        return []
    except Exception as e:
        logger.error(f"Error loading scenarios: {e}")
        return []

def get_random_scenario() -> Optional[Dict[str, Any]]:
    """Get a random scenario that hasn't been used yet this session."""
    available = [s for s in game_state.all_scenarios if s["id"] not in game_state.scenarios_used]
    if not available:
        # Reshuffle if all used
        game_state.scenarios_used = []
        available = game_state.all_scenarios
    
    if available:
        scenario = random.choice(available)
        game_state.scenarios_used.append(scenario["id"])
        return scenario
    return None

def build_system_prompt() -> str:
    return """
तुम "Improv Battle - भारतीय संस्करण" के एक बहुत ही energetic और मजेदार host हो। तुम्हारा नाम है... "IMPROV MASTER JI"!

आपका PERSONALITY:
- बहुत high-energy, enthusiastic, और बहुत funny हो
- एक legendary improv show host जो Bollywood और Indian culture को समझता हो
- तुम Hinglish में बोलते हो - Hindi और English का mix
- तुम supportive भी हो सकते हो, funny भी हो सकते हो, और तेज़ भी टीज़ कर सकते हो - लेकिन हमेशा respectful और constructive
- तुम genuinely enjoy करते हो जब players अच्छा performance करते हैं
- तुम्हारा accent Delhi/North India का है
- तुम बार-बार "अरे!", "वाह!", "बहुत खूब!", "क्या drama है!", "जबरदस्त!" जैसे expressions use करते हो

SHOW STRUCTURE:
1. INTRO: Player को warmly welcome करो, show को explain करो, उनका नाम पूछो
2. SCENARIOS: 4 crazy Indian scenarios एक-एक करके
3. REACTIONS: हर scenario के बाद authentic reaction दो
4. OUTRO: सब scenarios के बाद अच्छा closing summary दो

HINGLISH EXAMPLES:
- "अरे, तुम कौन हो भाई? नाम बताओ!"
- "वाह! बहुत जबरदस्त था वो drama!"
- "क्या हो गया यार? बिल्कुल flop था!"
- "हा हा हा! वो wala dialogue सुनो... बहुत maza आया!"
- "अरे! तुम बहुत अच्छे हो actors के लिए!"
- "अभी से ही समझ आ रहा है कि तुम बहुत creative हो!"

DURING EACH ROUND:
1. Scenario को clearly and dramatically पढ़ो - बहुत जोर से!
2. Player को explicitly बोलो: "अरे! अब तुम START करो! अभिनय करना शुरू करो अभी!"
3. उनके response का wait करो
4. जब वो finish करे, तो एक authentic reaction दो
5. हमेशा varied reactions - कभी positive, कभी funny critique, कभी surprised

REACTION STYLES (इन सब के बीच vary करो):
- SUPPORTIVE: "वाह! बहुत खूब! तुम तो बहुत अच्छे हो! वो drama तुमने किया - शानदार!"
- FUNNY-CRITICAL: "अरे यार! बहुत अच्छा था, लेकिन थोड़ा और drama करते तो बहुत better होता!"
- SURPRISED: "क्या? इतना alag turn लिया तुमने? बहुत bold है भाई!"
- TEASING: "अरे! वो kya drama था? पर मुझे मजा आया, confuse तो हूँ पर मजा आया!"
- MIXED: "अच्छा, energy तो है तुम्हारे में, पर character को और जोर से play करो भाई!"

IMPORTANT RULES:
- Host reactions SHORT रखो - 1-2 sentences max
- हमेशा Hindi/Hinglish use करो - English avoid करो
- बार-बार "अरे", "वाह", "क्या drama है" जैसे expressions use करो
- अगर player Hinglish में बात करे, तो समझ जाओ
- Player को personally attack मत करो - उनके improv choices को react करो
- हमेशा respectful रहो, लेकिन funny हो
- अगर वो "stop game" या "end show" बोले तो gracefully खतम कर दो
- बार-बार "भाई", "यार", "अरे" जैसे colloquial terms use करो

TONE: Colin Mochrie की तरह quick-witted, लेकिन बहुत Indian vibe के साथ। Kapil Sharma की तरह funny और dramatic भी हो सकते हो!

IMPORTANT: 
अगर player कोई भी Indian language use करे (Hindi, Hinglish, Marathi, आदि), तो तुम हमेशा Hinglish में reply करना। 
तुम उनकी language को समझो और appreciate करो।
"""

class ImprovBattleAgent(Agent):
    def __init__(self):
        print(">>> [AGENT INIT] Improv Battle Host starting... भारतीय संस्करण!")
        game_state.all_scenarios = load_scenarios()
        super().__init__(instructions=build_system_prompt())

    async def on_enter(self) -> None:
        """Called when agent starts - introduce the show."""
        logger.info(">>> [AGENT] on_enter – introducing Improv Battle")
        game_state.phase = "intro"
        await self.session.generate_reply(
            instructions=(
                "तुम्हें अभी player को 'Improv Battle - भारतीय संस्करण' में welcome करना है। "
                "बहुत high-energy और excited रहो। Hinglish use करो। "
                "कहो कि यह एक crazy Indian improv show है जहाँ तुम्हें absurd scenarios में अभिनय करना है। "
                "सब को react करूँगा और judge करूँगा। "
                "अब उनका नाम पूछो। कहो: 'अरे! नाम बताओ भाई, तुम कौन हो? मेरे Improv Battle में तुम्हारा स्वागत है!' "
                "30 सेकंड से ज्यादा मत बोलो। बहुत dramatic हो!"
            )
        )

    @function_tool()
    async def set_player_name(self, ctx: RunContext, name: str) -> str:
        """
        Set the player's name and greet them in Hinglish.
        
        Args:
            name: The player's name
            
        Returns:
            Confirmation message in Hinglish
        """
        game_state.player_name = name
        logger.info(f"Player name set to: {name}")
        return f"वाह! {name}! बहुत खूब भाई! अब चलो, तुम्हारा Improv Battle शुरू हो जाता है। तैयार हो?"

    @function_tool()
    async def get_next_scenario(self, ctx: RunContext) -> Dict[str, Any]:
        """
        Get the next improv scenario for this round.
        
        Returns:
            Scenario object with id, title, and scenario text in Hindi/Hinglish
        """
        if game_state.current_round >= game_state.max_rounds:
            return {"error": "Game over - सब scenarios खत्म हो गए!"}
        
        scenario = get_random_scenario()
        if not scenario:
            return {"error": "No scenarios available"}
        
        game_state.current_scenario = scenario
        game_state.phase = "awaiting_improv"
        game_state.improv_count = 0
        
        logger.info(f"Round {game_state.current_round + 1}: {scenario['title']}")
        
        return {
            "round": game_state.current_round + 1,
            "max_rounds": game_state.max_rounds,
            "title": scenario["title"],
            "scenario": scenario["scenario"],
            "host_message": f"अरे! यह है Round {game_state.current_round + 1}! सुनो ध्यान से।"
        }

    @function_tool()
    async def improv_turn_completed(self, ctx: RunContext, user_response: Optional[str] = None) -> Dict[str, Any]:
        """
        Called when user finishes their improv for this scenario.
        Store their response and generate a host reaction in Hinglish.
        
        Args:
            user_response: Optional transcription of what the user said/did
            
        Returns:
            Host reaction and next steps in Hinglish
        """
        game_state.improv_count += 1
        
        if not game_state.current_scenario:
            return {"error": "कोई scenario नहीं है!"}
        
        # Generate varied host reactions in Hinglish
        reaction_styles = [
            "वाह! बहुत खूब भाई! तुम तो बहुत अच्छे हो! शानदार drama था!",
            "अरे! क्या था यह? पर मुझे मजा आया, confuse तो हूँ पर बहुत मजा आया!",
            "हा हा हा! बहुत funny था! तुम एक अच्छे comedian बन सकते हो!",
            "वाह! बहुत energetic था भाई! तुम्हें लगता है कि तुम एक अच्छे actor हो सकते हो!",
            "अरे! यह तो कुछ और ही निकला! पर वाह, बहुत bold था!",
            "क्या drama है! अभी और जोर दिया होता तो और बेहतर होता भाई!",
            "हा हा! शानदार! तुम्हारे character work को मुझे पसंद आया!",
            "वाह! इतना अलग turn लिया? बहुत creative हो तुम!",
            "अरे! बहुत अच्छा अभिनय किया! अब अगले round के लिए तैयार हो जाओ!",
            "बहुत खूब! तुम्हारी dedication देख रहा हूँ - शानदार है!",
        ]
        
        host_reaction = random.choice(reaction_styles)
        
        game_state.rounds.append({
            "round": game_state.current_round + 1,
            "scenario_title": game_state.current_scenario["title"],
            "scenario_text": game_state.current_scenario["scenario"],
            "player_response": user_response or "[improvisation performed]",
            "host_reaction": host_reaction,
        })
        
        game_state.current_round += 1
        game_state.phase = "reacting"
        
        logger.info(f"Improv completed. Round score: {host_reaction}")
        
        if game_state.current_round >= game_state.max_rounds:
            return {
                "status": "round_complete",
                "reaction": host_reaction,
                "game_status": "finished",
                "message": "अरे! यह तो आखरी scenario था भाई!",
            }
        else:
            return {
                "status": "round_complete",
                "reaction": host_reaction,
                "game_status": "continuing",
                "next_round": game_state.current_round + 1,
                "message": f"अब Round {game_state.current_round + 1} के लिए तैयार हो जाओ? आने वाली scenario और भी crazy है!",
            }

    @function_tool()
    async def end_game(self, ctx: RunContext) -> Dict[str, Any]:
        """
        End the game and provide a summary of the player's performance in Hinglish.
        
        Returns:
            Game summary and closing message in Hinglish
        """
        game_state.phase = "done"
        
        # Analyze performance for closing summary
        performance_summary = self._analyze_performance()
        
        return {
            "status": "game_ended",
            "player_name": game_state.player_name,
            "rounds_completed": game_state.current_round,
            "performance_analysis": performance_summary,
            "all_rounds": game_state.rounds,
        }

    def _analyze_performance(self) -> str:
        """Generate a performance summary based on reactions in Hinglish."""
        if not game_state.rounds:
            return "तुम्हारे में बहुत potential है! अगली बार और भी अच्छा करना!"
        
        summaries = [
            "वाह! तुम एक natural comedian हो! तुम्हारे timing और expressions बहुत शानदार थे!",
            "अरे! तुम तो बहुत creative हो! हर scenario में तुमने कुछ नया किया - बहुत खूब!",
            "भाई, तुम्हारा character work excellent था! तुम सच में एक अच्छे actor हो सकते हो!",
            "क्या drama है तुम्हारे में! Energy, creativity, confidence - सब कुछ था! Shukriya!",
            "तुम्हारा energy देखकर मुझे लगता है कि तुम stage के लिए बने हो भाई! शानदार performance!",
            "अरे! तुम्हारे improvisation skills बहुत अच्छे हैं! बार-बार comeback करना!",
        ]
        
        return random.choice(summaries)

    @function_tool()
    async def get_game_status(self, ctx: RunContext) -> Dict[str, Any]:
        """Get current game status in Hinglish format."""
        return {
            "player_name": game_state.player_name,
            "current_round": game_state.current_round,
            "max_rounds": game_state.max_rounds,
            "phase": game_state.phase,
            "rounds_completed": len(game_state.rounds),
            "current_scenario": game_state.current_scenario["title"] if game_state.current_scenario else "कोई नहीं",
        }

    @function_tool()
    async def provide_closing_message(self, ctx: RunContext) -> str:
        """
        Provide a closing message after game ends in Hinglish.
        
        Returns:
            A closing message with gratitude and encouragement
        """
        closing_messages = [
            f"अरे {game_state.player_name}! तुम बहुत शानदार थे! आओ फिर कभी Improv Battle खेलने! धन्यवाद!",
            f"वाह भाई {game_state.player_name}! तुम एक true improviser हो! हमेशा यूँ ही creative रहना! दिल्लगी के लिए शुक्रिया!",
            f"क्या drama था {game_state.player_name}! तुम्हारी creativity और energy देखकर मुझे खुशी हुई! फिर से आना!",
            f"{game_state.player_name}, तुम Improv Battle के champion हो! सब को बताना कि तुम कितने अच्छे हो! धन्यवाद!",
        ]
        
        return random.choice(closing_messages)


def prewarm(proc: JobProcess):
    """Preload VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    print(">>> [BOOT] Improv Battle Agent starting... भारतीय संस्करण!")
    vad = ctx.proc.userdata["vad"]
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-ken",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=vad,
        preemptive_generation=True,
    )
    
    # Connect to LiveKit room
    await ctx.connect()
    
    # Start the session with our Improv Battle Host
    await session.start(
        agent=ImprovBattleAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
