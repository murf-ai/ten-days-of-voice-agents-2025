"use client";

import { useEffect, useState } from "react";
import { useSession } from "./session-provider";
import { useChatMessages } from "@/hooks/useChatMessages";
import { ChatTranscript } from "./chat-transcript";
import { AgentControlBar } from "@/components/livekit/agent-control-bar/agent-control-bar";
import { Button } from "@/components/livekit/button";
import { Mic, MicOff, PhoneOff } from "lucide-react";

interface Scenario {
  id: string;
  title: string;
  title_hi: string;
  scenario: string;
  difficulty: "easy" | "medium" | "hard";
  category: string;
}

interface GameState {
  playerName: string | null;
  currentRound: number;
  maxRounds: number;
  phase: "intro" | "awaiting_improv" | "reacting" | "done";
  currentScenario: Scenario | null;
}

export function ImprovGameView() {
  const { endSession } = useSession();
  const messages = useChatMessages();
  const [gameState, setGameState] = useState<GameState>({
    playerName: null,
    currentRound: 0,
    maxRounds: 4,
    phase: "intro",
    currentScenario: null,
  });

  const [isListening, setIsListening] = useState(false);

  // Parse game state from agent messages
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage) return;

    const text = lastMessage.message.toLowerCase();

    // Detect scenario presentation
    if (text.includes("scenario") || text.includes("round")) {
      // Extract scenario from agent response
      // Agent speaks the scenario, we display it
      const roundMatch = text.match(/round (\d+)/i);
      if (roundMatch) {
        setGameState((prev) => ({
          ...prev,
          currentRound: parseInt(roundMatch[1]),
          phase: "awaiting_improv",
        }));
      }
    }

    // Detect player name
    if (text.includes("नाम") || text.includes("name")) {
      const nameMatch = text.match(/name.*?is\s+(\w+)/i);
      if (nameMatch) {
        setGameState((prev) => ({ ...prev, playerName: nameMatch[1] }));
      }
    }

    // Detect game end
    if (text.includes("game over") || text.includes("खत्म")) {
      setGameState((prev) => ({ ...prev, phase: "done" }));
    }
  }, [messages]);

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case "easy":
        return "bg-green-500/20 text-green-400 border-green-500/30";
      case "medium":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      case "hard":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      default:
        return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  return (
    <div className="flex h-screen w-full flex-col bg-black text-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
        <div>
          <h1 className="text-2xl font-bold text-orange-500">
            🎭 Improv Battle - भारतीय संस्करण
          </h1>
          <p className="text-sm text-gray-400">
            {gameState.playerName
              ? `Player: ${gameState.playerName}`
              : "Waiting for player..."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="rounded-md border border-orange-500/30 bg-orange-400/10 px-2.5 py-0.5 text-xs font-semibold text-orange-400">
            Round {gameState.currentRound}/{gameState.maxRounds}
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={endSession}
            className="gap-2"
          >
            <PhoneOff className="h-4 w-4" />
            End Game
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Scenario Display - Left Side */}
        <div className="flex w-1/2 flex-col border-r border-gray-800 p-6">
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-300">
              Current Scenario
            </h2>
          </div>

          {gameState.phase === "intro" && (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <div className="mb-4 text-6xl">🎤</div>
                <h3 className="mb-2 text-2xl font-bold text-orange-500">
                  Welcome to Improv Battle!
                </h3>
                <p className="text-gray-400">
                  The host will introduce the game and ask for your name.
                  <br />
                  Speak clearly into your microphone!
                </p>
              </div>
            </div>
          )}

          {gameState.phase === "awaiting_improv" && (
            <div className="flex flex-1 flex-col">
              {/* Scenario Card */}
              <div className="rounded-lg border border-orange-500/30 bg-gray-900/50 p-6">
                <div className="mb-4 flex items-start justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-orange-400">
                      Round {gameState.currentRound}
                    </h3>
                    {gameState.currentScenario && (
                      <>
                        <p className="mt-1 text-lg text-white">
                          {gameState.currentScenario.title_hi}
                        </p>
                        <p className="text-sm text-gray-400">
                          {gameState.currentScenario.title}
                        </p>
                      </>
                    )}
                  </div>
                  {gameState.currentScenario && (
                    <div className={`rounded-md border px-2.5 py-0.5 text-xs font-semibold ${getDifficultyColor(
                      gameState.currentScenario.difficulty
                    )}`}>
                      {gameState.currentScenario.difficulty.toUpperCase()}
                    </div>
                  )}
                </div>

                {gameState.currentScenario && (
                  <div className="mb-4">
                    <p className="text-base leading-relaxed text-gray-300">
                      {gameState.currentScenario.scenario}
                    </p>
                  </div>
                )}

                {gameState.currentScenario && (
                  <div className="flex items-center gap-2">
                    <div className="rounded-md border border-purple-500/30 bg-purple-400/10 px-2.5 py-0.5 text-xs font-semibold text-purple-400">
                      {gameState.currentScenario.category}
                    </div>
                  </div>
                )}
              </div>

              {/* Instructions */}
              <div className="mt-6 rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
                <div className="flex items-start gap-3">
                  <div className="mt-1">
                    {isListening ? (
                      <Mic className="h-5 w-5 animate-pulse text-red-500" />
                    ) : (
                      <MicOff className="h-5 w-5 text-gray-500" />
                    )}
                  </div>
                  <div>
                    <h4 className="font-semibold text-blue-400">
                      अब तुम्हारी बारी! Your Turn!
                    </h4>
                    <p className="mt-1 text-sm text-gray-300">
                      Start improvising your performance. Speak your response
                      clearly. The host is listening and will react to your
                      performance.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {gameState.phase === "done" && (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <div className="mb-4 text-6xl">🎉</div>
                <h3 className="mb-2 text-2xl font-bold text-green-500">
                  Game Complete!
                </h3>
                <p className="text-gray-400">
                  Thanks for playing! Check the chat for your final score.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Chat Transcript - Right Side */}
        <div className="flex w-1/2 flex-col">
          <div className="border-b border-gray-800 px-6 py-4">
            <h2 className="text-xl font-semibold text-gray-300">
              Live Conversation
            </h2>
            <p className="text-sm text-gray-500">
              Host reactions and your responses
            </p>
          </div>
          <div className="flex-1 overflow-hidden">
            <ChatTranscript />
          </div>
        </div>
      </div>

      {/* Control Bar */}
      <div className="border-t border-gray-800 p-4">
        <AgentControlBar />
      </div>
    </div>
  );
}
