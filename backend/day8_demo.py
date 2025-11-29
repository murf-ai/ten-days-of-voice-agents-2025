import asyncio

# Demo independent of the project imports to avoid dependency issues when running locally.
from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class GMUserdata:
    story_history: List[dict] = field(default_factory=list)
    named_characters: Set[str] = field(default_factory=set)
    named_locations: Set[str] = field(default_factory=set)
    decisions: List[str] = field(default_factory=list)
    turn_count: int = 0
    session_active: bool = False


async def restart_story_local(userdata: GMUserdata, universe: str = None) -> str:
    userdata.story_history = []
    userdata.named_characters = set()
    userdata.named_locations = set()
    userdata.decisions = []
    userdata.turn_count = 0
    userdata.session_active = True

    uni = (universe or "fantasy").strip().lower()
    if uni == "sci-fi":
        opening = (
            "You awaken in the humming corridors of the starcruiser 'Asterion', alarms faintly wailing. "
            "Neon panels flicker; a distant bulkhead door is ajar. A datapad nearby shows the ship is off-course toward a rogue planet. "
            "Your companion, a grizzled engineer named Kora, looks to you with concern. What do you do?"
        )
    else:
        opening = (
            "Moonlight spills across the moss-covered stones of the Old Watchtower. A chill wind carries the scent of smoke and iron. "
            "A tattered map flutters in your hand, pointing toward the Ruins of Hadrin where a lost relic is said to lie. "
            "Nearby, a young squire named Elen whispers about strange footsteps. What do you do?"
        )

    userdata.story_history.append({"role": "gm", "text": opening})
    return opening


async def show_story_state_local(userdata: GMUserdata) -> str:
    chars = ", ".join(sorted(userdata.named_characters)) or "(none yet)"
    locs = ", ".join(sorted(userdata.named_locations)) or "(none yet)"
    decs = " | ".join(userdata.decisions) or "(no major decisions yet)"
    return f"Characters: {chars}\nLocations: {locs}\nDecisions: {decs}\nTurns: {userdata.turn_count}"


async def run_demo():
    gm = GMUserdata()

    # Start a fresh fantasy session
    opening = await restart_story_local(gm, universe="fantasy")
    print("GM:", opening)

    # Scripted player responses driving a mini-arc
    players = [
        "I whisper to Elen and ask if she heard anything.",
        "I follow the footprints toward the east wall, moving quietly.",
        "I draw my dagger and peer through the archway.",
        "I call out softly, 'Hello? Who goes there?'.",
        "I decide to take the narrow passage, holding my torch high.",
        "I examine the strange symbol on the wall and touch it.",
        "I pull the lever hidden behind the tapestry.",
        "I grab the glowing relic and tuck it into my pack.",
        "I run back toward the tower entrance, urging Elen to follow.",
        "I hide behind the boulder and wait for the noise to pass."
    ]

    # Simple simulated GM replies that reference past decisions/names
    for i, p in enumerate(players, start=1):
        gm.story_history.append({"role": "player", "text": p})
        gm.turn_count += 1

        # rudimentary memory extraction: capture capitalized words as names/locations
        for token in p.replace("'", "").split():
            if token.istitle() and len(token) > 1:
                if token.lower() in ("elen", "kora"):
                    gm.named_characters.add(token)
                else:
                    gm.named_locations.add(token)

        # Add a decision summary for some turns
        if "pull the lever" in p.lower():
            gm.decisions.append("pulled the hidden lever")
        if "relic" in p.lower():
            gm.decisions.append("recovered the relic")

        # Construct a short GM reply to advance the mini-arc
        if i < 4:
            reply = "The shadows stir and a distant clatter echoes. Elen tugs your sleeve, eyes wide. What do you do?"
        elif i < 7:
            reply = "A mechanism whirs open; the air smells of ozone. The corridor ahead glows with an otherworldly light. What do you do?"
        else:
            reply = "With the relic secured, a rumble shakes the ruins — it's time to escape. What do you do?"

        gm.story_history.append({"role": "gm", "text": reply})
        print("Player:", p)
        print("GM:", reply)

    # At the end, show the remembered state
    state = await show_story_state_local(gm)
    print('\n=== Session state summary ===')
    print(state)


if __name__ == '__main__':
    asyncio.run(run_demo())
