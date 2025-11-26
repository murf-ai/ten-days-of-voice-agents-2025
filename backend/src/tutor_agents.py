from __future__ import annotations

from dataclasses import asdict
from typing import Literal, Optional

from livekit.agents import Agent, RunContext, ChatContext, function_tool

from .tutor_content import (
    TutorState,
    CONCEPT_BY_ID,
    CONTENT_FOR_PROMPT,
    get_default_concept_id,
)

# NOTE: adjust imports to match your existing config / Murf Falcon setup.
# e.g. you probably have something like config.tts_falcon_matthew already.
from . import config


# ---------- Base mixin with common tools ---------- #

class BaseTutorAgent(Agent):
    """Shared tools + instructions for mode switching."""

    def __init__(
        self,
        mode: Literal["welcome", "learn", "quiz", "teach_back"],
        *,
        chat_ctx: Optional[ChatContext] = None,
        tts=None,
        extra_mode_instructions: str = "",
    ) -> None:

        base_instructions = f"""
You are part of a multi-agent **Teach-the-Tutor: Active Recall Coach**.

There are three learning modes:
- learn: Explain one concept clearly using the JSON content.
- quiz: Ask short questions, wait for answers, then give brief corrections.
- teach_back: Ask the user to teach the concept back, then give qualitative feedback.

Current mode: {mode}

Course content comes from this JSON (do NOT invent new concepts):

{CONTENT_FOR_PROMPT}

Rules:
- Always stick to the given concepts and their summaries.
- Before teaching or quizzing, pick ONE concept to focus on (by id).
- Keep turns short and conversational, one question or explanation chunk at a time.
- If the user asks to change mode (e.g. "quiz me" / "let me teach it"), call the switch_mode tool.
- If the user mentions a specific concept name or id, use that concept.

Mode-specific behavior:
{extra_mode_instructions}
        """

        super().__init__(instructions=base_instructions, chat_ctx=chat_ctx, tts=tts)

    # ---- Tools shared by all three modes ---- #

    @function_tool()
    async def switch_mode(
        self,
        context: RunContext[TutorState],
        mode: Literal["learn", "quiz", "teach_back"],
        concept_id: Optional[str] = None,
    ):
        """
        Switch between learn, quiz, and teach_back modes.
        Use this whenever the user asks to 'learn', 'quiz', or 'teach back'.
        """

        if concept_id is None:
            concept_id = context.userdata.current_concept_id or get_default_concept_id()

        if concept_id not in CONCEPT_BY_ID:
            # fall back gracefully
            concept_id = get_default_concept_id()

        context.userdata.mode = mode
        context.userdata.current_concept_id = concept_id

        # handoff to the appropriate agent, preserving chat context
        chat_ctx = self.session.chat_ctx

        if mode == "learn":
            return LearnAgent(chat_ctx=chat_ctx)
        elif mode == "quiz":
            return QuizAgent(chat_ctx=chat_ctx)
        else:  # teach_back
            return TeachBackAgent(chat_ctx=chat_ctx)

    @function_tool()
    async def set_concept(
        self,
        context: RunContext[TutorState],
        concept_id: str,
    ):
        """
        Set the active concept by id.
        Valid ids are the 'id' values from the JSON (e.g. 'variables', 'loops').
        Use this whenever the user explicitly asks for a specific concept.
        """
        if concept_id not in CONCEPT_BY_ID:
            valid_ids = ", ".join(CONCEPT_BY_ID.keys())
            return f"Unknown concept id '{concept_id}'. Valid ids: {valid_ids}."

        context.userdata.current_concept_id = concept_id
        return f"OK, we'll focus on '{concept_id}'."


# ---------- Router agent (first touch) ---------- #

class RouterAgent(BaseTutorAgent):
    """
    First agent the user talks to.
    Job: greet, clarify mode + concept, then hand off.
    """

    def __init__(self):
        super().__init__(
            mode="welcome",
            extra_mode_instructions="""
- Greet the learner.
- Briefly describe the three modes: learn, quiz, teach_back.
- Ask: (1) which mode they want, and (2) which concept (by name or id).
- Then call the switch_mode tool with the chosen mode and concept.
- After calling switch_mode, you don't continue the conversation.
""",
            # Use any voice you like for initial greeting.
            # Could be same as learn (Matthew) or something neutral.
            tts=config.tts_router,  # define in config if needed
        )

    async def on_enter(self) -> None:
        # Kick off the greeting / mode selection
        await self.session.generate_reply(
            instructions=(
                "Greet the learner. Explain that you have three modes: "
                "learn, quiz, and teach_back. Ask which mode they want "
                "and whether they want to start with 'variables' or 'loops'."
            )
        )


# ---------- Learn Agent (Matthew) ---------- #

class LearnAgent(BaseTutorAgent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None):
        super().__init__(
            mode="learn",
            chat_ctx=chat_ctx,
            tts=config.tts_matthew,  # Murf Falcon voice "Matthew"
            extra_mode_instructions="""
In learn mode:
- Pick the active concept from the user's state or from what they said.
- Use that concept's summary as the backbone of your explanation.
- Explain in clear, friendly language, with 1–2 short examples.
- Pause regularly and ask, "Should I repeat or move to a quick quiz?"
""",
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as the Learn mode tutor. "
                "Briefly explain which concept you'll cover first and give a short overview."
            )
        )


# ---------- Quiz Agent (Alicia) ---------- #

class QuizAgent(BaseTutorAgent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None):
        super().__init__(
            mode="quiz",
            chat_ctx=chat_ctx,
            tts=config.tts_alicia,  # Murf Falcon voice "Alicia"
            extra_mode_instructions="""
In quiz mode:
- Ask one short question at a time, based on the concept's `sample_question`.
- Wait for the user's answer before giving feedback.
- Give brief feedback: what was correct, what was missing.
- Then ask a follow-up question or let them switch modes if they ask.
""",
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as the Quiz mode tutor. "
                "Confirm the active concept and ask the first short question about it."
            )
        )


# ---------- Teach-Back Agent (Ken) ---------- #

class TeachBackAgent(BaseTutorAgent):
    def __init__(self, chat_ctx: Optional[ChatContext] = None):
        super().__init__(
            mode="teach_back",
            chat_ctx=chat_ctx,
            tts=config.tts_ken,  # Murf Falcon voice "Ken"
            extra_mode_instructions="""
In teach_back mode:
- Ask the learner to explain the concept in their own words.
- Let them speak fully before responding.
- Then give 1–3 sentences of qualitative feedback:
  - What they explained well.
  - What they missed or could improve.
- Optionally suggest whether they should go back to learn or try a quiz.
""",
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as the Teach-back coach. "
                "Ask the learner to explain the current concept in their own words."
            )
        )
