import { useState, useCallback, useRef } from 'react';

export interface GameMessage {
  role: 'gm' | 'player';
  content: string;
  timestamp: string;
  turn: number;
}

export interface GameState {
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

export const useGameMaster = () => {
  const [messages, setMessages] = useState<GameMessage[]>([]);
  const [gameState, setGameState] = useState<GameState>(initialGameState);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const conversationHistoryRef = useRef<GameMessage[]>([]);

  const addMessage = useCallback((message: GameMessage) => {
    setMessages((prev) => [...prev, message]);
    conversationHistoryRef.current.push(message);
  }, []);

  const updateGameState = useCallback((updates: Partial<GameState>) => {
    setGameState((prev) => ({ ...prev, ...updates }));
  }, []);

  const addToInventory = useCallback(
    (item: string) => {
      setGameState((prev) => {
        if (prev.inventory.length < 10 && !prev.inventory.includes(item)) {
          return { ...prev, inventory: [...prev.inventory, item] };
        }
        return prev;
      });
    },
    []
  );

  const removeFromInventory = useCallback((item: string) => {
    setGameState((prev) => ({
      ...prev,
      inventory: prev.inventory.filter((i) => i !== item),
    }));
  }, []);

  const discoverLore = useCallback((lore: string) => {
    setGameState((prev) => {
      if (!prev.discoveredLore.includes(lore)) {
        return { ...prev, discoveredLore: [...prev.discoveredLore, lore] };
      }
      return prev;
    });
  }, []);

  const updateRelationship = useCallback(
    (npcId: string, value: number) => {
      setGameState((prev) => ({
        ...prev,
        relationships: {
          ...prev.relationships,
          [npcId]: (prev.relationships[npcId] || 0) + value,
        },
      }));
    },
    []
  );

  const recordDecision = useCallback((decision: string) => {
    setGameState((prev) => ({
      ...prev,
      decisions: [...prev.decisions, decision],
    }));
  }, []);

  const restartGame = useCallback(() => {
    setMessages([]);
    setGameState(initialGameState);
    conversationHistoryRef.current = [];
    setIsPlaying(false);
  }, []);

  const getConversationHistory = useCallback(
    () => conversationHistoryRef.current,
    []
  );

  return {
    messages,
    gameState,
    isPlaying,
    isLoading,
    setIsPlaying,
    setIsLoading,
    addMessage,
    updateGameState,
    addToInventory,
    removeFromInventory,
    discoverLore,
    updateRelationship,
    recordDecision,
    restartGame,
    getConversationHistory,
  };
};
    