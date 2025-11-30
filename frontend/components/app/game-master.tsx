'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import styles from '@/styles/game-master.module.css';

interface GameMessage {
  role: 'gm' | 'player';
  content: string;
  timestamp: string;
  turn: number;
}

interface GameState {
  playerName: string;
  inventory: string[];
  currentLocation: string;
  visitedLocations: string[];
  turnCount: number;
  discoveredLore: string[];
  relationships: Record<string, number>;
  storyArc: string | null;
  health: number;
  decisions: string[];
}

const initialGameState: GameState = {
  playerName: 'Adventurer',
  inventory: ['worn_leather_pouch', 'traveling_clothes'],
  currentLocation: 'tavern_start',
  visitedLocations: ['tavern_start'],
  turnCount: 0,
  discoveredLore: [],
  relationships: {},
  storyArc: null,
  health: 100,
  decisions: [],
};

export const GameMaster: React.FC = () => {
  const [messages, setMessages] = useState<GameMessage[]>([]);
  const [gameState, setGameState] = useState<GameState>(initialGameState);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showGameState, setShowGameState] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (!isPlaying) {
      initializeGame();
    }
  }, [isPlaying]);

  const initializeGame = () => {
    const openingMessage: GameMessage = {
      role: 'gm',
      content: `🐉 **Welcome to the Realm of Eldoria!**

You awaken in the **Weathered Ale House**, a cozy tavern with warm firelight flickering against stone walls. Rain batters the windows in heavy sheets. The smell of hearth smoke and ale fills the air.

A *hooded figure* slides into the seat across from you, revealing *silver scars* on their neck. "You have the look of someone who knows how to survive. I have a proposition."

On the table, they slide an **ancient map**, worn and stained with age. But armored guards with black cloaks enter the tavern, scanning the crowd.

**What do you do?**`,
      timestamp: new Date().toISOString(),
      turn: 0,
    };

    setMessages([openingMessage]);
    setGameState((prev) => ({
      ...prev,
      turnCount: 0,
      decisions: ['met_mysterious_stranger'],
    }));
    setIsPlaying(true);
  };

  const restartGame = () => {
    setMessages([]);
    setGameState(initialGameState);
    setIsPlaying(false);
  };

  const generateGMResponse = useCallback((playerAction: string): string => {
    const actionLower = playerAction.toLowerCase();
    
    const responses: Record<string, string> = {
      trust: `The stranger nods with relief. "I'm Kael. The Shadow Order hunts that map. We need to move—now!"

You slip through the kitchen as guards storm the entrance. Rain soaks your face in the dark alley. Kael hands you an ancient dagger.

"The Forbidden Forest is our sanctuary. The Shadow Order fears what lives there."

*Added to inventory: Ancient Dagger*
*Discovered Lore: Kael fights against the Shadow Order*

An old wooden gate leads to the forest. You hear horses approaching.

**What do you do?**`,

      question: `Kael leans back. "Fair question. That map leads to the Lost Temple of Zar'an—a place of ancient power. The Shadow Order wants to awaken darkness. I won't allow it."

Before more words, the tavern door CRASHES open. Guards storm inside, pointing directly at your table.

"There! Don't move!"

Kael curses. "We're out of time!"

**What do you do?**`,

      reject: `Kael's expression hardens. "Your loss. But you've made enemies."

They stand quickly. Too late. Guards grab Kael before escape. The stranger's eyes meet yours—defiance mixed with despair.

A guard turns toward you. "You know this criminal?"

Behind them, all exits seal.

*You're alone. Enemies know your face.*

**What do you do?**`,

      grab: `You lunge for the map. It's warm to the touch, pulsing with energy.

Kael nods. "Good instinct!"

Guards burst through. Kael draws a silver blade and cuts a path toward the back. "Go!"

You sprint through the kitchen, map clutched tight. Chaos erupts behind you.

*Added to inventory: Ancient Map*
*Discovered Lore: The Shadow Order seeks the Lost Temple of Zar'an*

You burst into the rain-soaked alley. Pursuing hoofbeats grow closer.

**What do you do?**`,

      forest: `You plunge into the **Forbidden Forest** with Kael.

The moment you cross the threshold, the rain ceases. Trees tower impossibly high. Bioluminescent vines cast eerie blue-green light.

"This place is alive," you whisper.

Kael nods. "And it remembers."

A sound stops you both. Not guards—something else. Something massive. Golden eyes peer from darkness. A **shadow creature**.

Kael draws their blade but doesn't attack. "Don't move. Don't breathe hard."

*Encountered: Shadow Guardian*

The creature circles, studying you both.

**What do you do?**`,

      bow: `You slowly lower yourself to one knee—a gesture of deep respect.

Kael hesitates, then follows.

The creature's form shimmers. For a moment, you see—a woman? A spirit? Something ancient and lonely.

A voice like wind through dead leaves touches your mind: *"Seekers of truth. The temple awaits. But beware—the Shadow Order is not your only enemy."*

The creature dissolves into mist.

Kael stands slowly. "I've never seen one of the Guardians do that. You passed the test."

A path of glowing stones opens before you.

*Relationship with Forest Spirits: +10*

**What do you do?**`,

      temple: `Following the illuminated path, the trees part for you. Hours pass—or minutes; time feels strange here.

The trees open into a clearing. And there stands the **Lost Temple of Zar'an**.

Towering spires twist upward, defying gravity. Glowing runes pulse on every surface. The entrance is a massive archway carved with robed figures and celestial bodies.

"It's real," Kael breathes. "It's actually real."

But something is wrong. The glow flickers, irregular. You hear voices—rough and commanding—from inside.

"The Shadow Order," Kael whispers. "They're already here."

*Current Location: Lost Temple of Zar'an*

Kael draws their blade. "We can sneak through the lower entrance or create a distraction. Your call."

**What do you do?**`,

       sneak: `"Stealth," you whisper.

You both approach carefully. The lower entrance—crumbling stone, vines covering it—becomes visible. Dark and unguarded.

Kael produces a torch that glows without flame—shadow-light. Inside, the tunnel is narrow and cold. Your footsteps echo despite your caution.

After an eternity, the tunnel opens into a vast chamber. Walls covered in shelves—thousands of ancient tomes and artifacts. A library of forgotten knowledge, preserved by time itself.

In the center: a pedestal. On it rests a crystal orb, glowing with inner light.

But guards stand positioned around the chamber. Three Shadow Order operatives, all armed.

Kael points to a shadow-covered ledge above. A possible route to reach the orb undetected.

*Stealth Check: High Difficulty*

**What do you do?**`,

      distraction: `"Create a distraction," you suggest.

Kael's lips curl into a dangerous smile. "I like how you think."

Kael hurls a stone through a temple window. It shatters with tremendous force.

Inside, chaos erupts. Guards rush toward the sound, shouting commands.

"Now! While they're distracted!" Kael hisses.

You slip through the main entrance undetected. Guards have rushed away, leaving the back corridor completely undefended.

You see it: a door marked with ancient runes glowing faintly. Something tells you this is important—the inner sanctum, perhaps.

Behind you, guards realize the deception. Shouts of anger. They're regrouping.

*Alert Level: CRITICAL*
*Time Remaining: ~30 seconds*

The rune-marked door is right there.

**What do you do?**`,

      sanctum: `You rush toward the rune-marked door with Kael close behind. Your hands touch the ancient wood—and it swings open instantly, as if waiting for you.

Inside is a chamber bathed in starlight. The ceiling isn't stone—it's transparent, showing a night sky filled with constellations you've never seen.

At the center floats the **Crystal of Zar'an**—a gem the size of a fist, pulsing with power that predates civilization itself.

The moment you cross the threshold, the door SLAMS shut behind you. Not imprisoning—protecting. Ancient magic seals you inside.

Kael approaches the crystal cautiously. "This is what the Shadow Order seeks. If they activate it with dark intent..."

You can feel the power radiating from the crystal. It's calling to you—ancient and wise, offering knowledge, power, secrets. Your mind touches the edge of that consciousness and recoils slightly at its scope.

Outside, guards pound on the door—frantic, angry, desperate. The door holds firm. For now.

*Current Location: Inner Sanctum of Zar'an*
*Discovered Artifact: The Crystal of Zar'an (Ancient Power Source)*
*Door Status: Magically Sealed (Will hold for ~5 minutes)*

Kael turns to you, eyes wide. "This is the crucial moment. Take it? Destroy it? Leave it?"

**What do you do?**`,

      take: `"We take it," you decide. "Knowledge is power. The Shadow Order can't have this."

You step toward the crystal carefully. The moment your hand touches it, the world explodes into sensation.

Visions flood your mind—ancient mages performing rituals, civilizations rising and falling, the Shadow Order's true origin, and something else—*something vast waking in the deep places of the world*.

You stagger backward, gasping. Kael catches you.

"What did you see?" they ask urgently.

"Everything," you manage. "And nothing. The crystal... it's alive. Conscious. And it's been waiting for someone to—"

The door EXPLODES inward.

Shadows pour into the chamber—corrupted versions of forest creatures. The Shadow Order has dark magic indeed.

But something miraculous happens. The crystal rises from its pedestal and flies to your hand, settling into your grip as if it belongs there. The moment you hold it, power courses through you—*clarifying*—as if you've understood something fundamental about yourself.

The corrupted creatures hesitate, confused. The crystal's light repels their darkness.

Kael draws their blade. "Run! Use the crystal's power! I'll hold them off!"

Behind you, the chamber has another exit—an ancient passage leading down, deeper into the earth. The way ahead glows faintly with the crystal's light.

*Obtained: Crystal of Zar'an*
*Health Restored: 100/100*
*New Ability Unlocked: Crystal Attunement*
*Relationship with Kael: +15*

**What do you do?**`,

      destroy: `"It has to be destroyed," you say, voice heavy. "Power this great... it corrupts. Eventually, someone will abuse it."

Kael's expression is conflicted, but they nod slowly. "You might be right. The Resistance has learned that lesson the hard way."

You raise your hand, reaching for the crystal. As your fingers close around it, you feel the vast consciousness within—millions of years of awareness, watching, waiting. And you feel its... *sadness*. The crystal doesn't want to end. But it understands.

You focus all your will on one thought: *dispersion*. Return to the earth. Return to the stars. Become whole again.

The crystal begins to shatter—not violently, but like a musical note fading into silence. Each fragment glows brightly before dispersing as pure light, spreading through the chamber like fireflies. The light passes through the walls themselves, returning to the world it came from so long ago.

The void it leaves feels... *peaceful*.

But the Shadow Order operatives have broken through the door. They see what you've done and let out a collective shriek of rage and despair.

"No! The artifact! Centuries of planning—"

Kael moves with deadly grace, blocking the entrance. "Go! The path down—it leads to the Old Way. Use it!"

Behind you, an ancient passage glows faintly. Your instincts scream to run.

*Destroyed: Crystal of Zar'an*
*Shadow Order: Severely Weakened*
*Relationship with Kael: +10*
*Discovered Lore: The Resistance has fought the Shadow Order for centuries*

**What do you do?**`,

      escape: `You run down the ancient passage with Kael close behind. The path glows faintly with phosphorescent moss, lighting your way through the darkness. Behind you, sounds of pursuit echo—armored boots, angry shouts, the crackle of dark magic.

You run until your lungs burn, until your legs feel like they might give out beneath you.

Then the passage opens into an immense underground cavern.

Your footsteps echo across stone as you skid to a halt. What you see steals your breath.

An *underground city*—or the ruins of one. Towers of white stone rise from the cavern floor, connected by graceful bridges. Bioluminescent fungi paint the walls in shades of blue and green. At the center sits what looks like a colossal tree, made entirely of stone and crystal, its roots spreading across the cavern like veins.

"The Old City," Kael breathes. "The city that existed before recorded history. The Shadow Order was supposed to guard it, not destroy it. No wonder they've gone so wrong."

A sound stops you both—not the pursuing guards, but something else. A deep, resonant voice that seems to come from the stone city itself.

"For a thousand years, we have waited. A seeker who chose wisdom over power. A guardian who chose sacrifice over dominion. Welcome, travelers, to the heart of Eldoria."

The crystal tree begins to glow, brighter and brighter, until the entire cavern is bathed in soft light. The pursuing guards skid to a halt at the cavern entrance, stunned into silence.

*Current Location: The Old City (Hidden from the world above)*
*Encountered: The Custodian of the Old City (Ancient Entity)*
*Story Arc: Reaching Final Confrontation*
*Turns Completed: ${gameState.turnCount}*

The Custodian's voice continues: "The Shadow Order will retreat. They cannot stand against the power awakening here. But know this—your choices have set events in motion that will echo across millennia. You have become part of Eldoria's fate."

Kael looks at you with newfound respect. "Partner, I think you just saved the world. Or at least, gave it a fighting chance."

**🎲 MINI-ARC COMPLETE: The Temple's Secret**

Your choices shaped the story. The Shadow Order has been defeated. The Old City has been rediscovered.

**What would you like to do?**
1. Continue exploring the Old City
2. Return to the Weathered Ale House
3. Start a new adventure`,
    };

    const matchedResponse = Object.keys(responses).find((key) =>
      actionLower.includes(key)
    );

    return (
      responses[matchedResponse || ''] ||
      `Your action echoes through Eldoria. The story responds to your choice...

${playerAction}

The world shifts. Magic crackles in the air. What you do next could change the fate of kingdoms.

*Your turn count: ${gameState.turnCount + 1}*

**What do you do?**`
    );
  }, [gameState.turnCount]);

  const handlePlayerAction = useCallback(
    (action: string) => {
      if (!action.trim()) return;

      setIsLoading(true);

      const playerMessage: GameMessage = {
        role: 'player',
        content: action,
        timestamp: new Date().toISOString(),
        turn: gameState.turnCount,
      };

      setMessages((prev) => [...prev, playerMessage]);

      setTimeout(() => {
        const gmResponse = generateGMResponse(action);
        const gmMessage: GameMessage = {
          role: 'gm',
          content: gmResponse,
          timestamp: new Date().toISOString(),
          turn: gameState.turnCount + 1,
        };

        setMessages((prev) => [...prev, gmMessage]);
        setGameState((prev) => ({
          ...prev,
          turnCount: prev.turnCount + 1,
          decisions: [...prev.decisions, action.substring(0, 50)],
        }));
        setIsLoading(false);
      }, 1500);
    },
    [gameState.turnCount, generateGMResponse]
  );

  return (
    <div className={styles.gameMasterContainer}>
      <div className={styles.gameHeader}>
        <div className={styles.titleSection}>
          <h1>🎲 Eldoria: Voice Adventure</h1>
          <p className={styles.subtitle}>A D&D-Style Voice Agent RPG</p>
        </div>
        <div className={styles.statsSection}>
          <span className={styles.stat}>Turn: {gameState.turnCount}</span>
          <span className={styles.stat}>📍 {gameState.currentLocation}</span>
          <span className={styles.stat}>❤️ {gameState.health}/100</span>
        </div>
      </div>

      <div className={styles.mainContent}>
        <div className={styles.gameWindow}>
          <div className={styles.narrativeArea}>
            {messages.map((msg, idx) => (
              <div key={idx} className={`${styles.message} ${styles[msg.role]}`}>
                <div className={styles.messageHeader}>
                  <span className={styles.role}>
                    {msg.role === 'gm' ? '🎭 Game Master' : '⚔️ You'}
                  </span>
                  <span className={styles.turn}>Turn {msg.turn}</span>
                </div>
                <div className={styles.messageContent}>
                  {msg.content.split('\n').map((line, i) => (
                    <div key={i}>{line}</div>
                  ))}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className={`${styles.message} ${styles.loading}`}>
                <div className={styles.messageHeader}>
                  <span className={styles.role}>🎭 Game Master</span>
                </div>
                <div className={styles.messageContent}>
                  The GM is crafting the next scene...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {showGameState && (
            <div className={styles.sidePanel}>
              <h3>📜 Adventure Log</h3>

              <div className={styles.statBlock}>
                <h4>Inventory ({gameState.inventory.length}/10)</h4>
                <ul className={styles.itemList}>
                  {gameState.inventory.length > 0 ? (
                    gameState.inventory.map((item, idx) => (
                      <li key={idx}>
                        {item
                          .replace(/_/g, ' ')
                          .replace(/\b\w/g, (l) => l.toUpperCase())}
                      </li>
                    ))
                  ) : (
                    <li className={styles.emptyState}>Empty</li>
                  )}
                </ul>
              </div>

              <div className={styles.statBlock}>
                <h4>Discovered Lore</h4>
                {gameState.discoveredLore.length > 0 ? (
                  <ul className={styles.itemList}>
                    {gameState.discoveredLore.map((lore, idx) => (
                      <li key={idx}>{lore}</li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.emptyState}>No lore discovered yet...</p>
                )}
              </div>

              <div className={styles.statBlock}>
                <h4>Relationships</h4>
                {Object.keys(gameState.relationships).length > 0 ? (
                  <ul className={styles.itemList}>
                    {Object.entries(gameState.relationships).map(
                      ([npc, sentiment], idx) => (
                        <li key={idx}>
                          {npc}: {sentiment > 0 ? '❤️ Friendly' : '💔 Hostile'}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p className={styles.emptyState}>
                    Meet NPCs to build relationships...
                  </p>
                )}
              </div>

              <div className={styles.statBlock}>
                <h4>Story Decisions ({gameState.decisions.length})</h4>
                {gameState.decisions.length > 0 ? (
                  <ul className={`${styles.itemList} ${styles.smallText}`}>
                    {gameState.decisions.slice(-5).map((decision, idx) => (
                      <li key={idx}>→ {decision}...</li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.emptyState}>Adventure awaits...</p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className={styles.inputSection}>
          <button
            className={styles.toggleButton}
            onClick={() => setShowGameState(!showGameState)}
            title="Toggle adventure log"
          >
            {showGameState ? '📖 Hide' : '📖 Show'} Log
          </button>

          <PlayerActionInput onSubmit={handlePlayerAction} isLoading={isLoading} />

          <button
            className={styles.restartButton}
            onClick={restartGame}
            title="Start a new adventure"
          >
            🔄 New Adventure
          </button>
        </div>
      </div>
    </div>
  );
};

interface PlayerActionInputProps {
  onSubmit: (action: string) => void;
  isLoading?: boolean;
}

const PlayerActionInput: React.FC<PlayerActionInputProps> = ({ 
  onSubmit, 
  isLoading = false 
}) => {
  const [input, setInput] = useState('');

const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSubmit(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && e.ctrlKey && !isLoading) {
      handleSubmit(e as any);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={styles.inputForm}>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="What do you do, adventurer? (Type or press Ctrl+Enter)"
        className={styles.inputField}
        rows={3}
        disabled={isLoading}
      />
      <div className={styles.actionButtons}>
        <button
          type="submit"
          className={styles.submitButton}
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? '⏳ Processing...' : '📢 Take Action'}
        </button>
      </div>
    </form>
  );
};
