import { useState, useCallback } from 'react';

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
  skills: Record<string, number>;
  achievements: string[];
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
  skills: {
    stealth: 0,
    strength: 0,
    intelligence: 0,
    charisma: 0,
    perception: 0,
  },
  achievements: [],
};

export const useGameState = (initialState: Partial<GameState> = {}) => {
  const [gameState, setGameState] = useState<GameState>({
    ...initialGameState,
    ...initialState,
  });

  const updatePlayerName = useCallback((name: string) => {
    setGameState((prev) => ({ ...prev, playerName: name }));
  }, []);

  const addToInventory = useCallback((item: string) => {
    setGameState((prev) => {
      if (prev.inventory.length < 10 && !prev.inventory.includes(item)) {
        return { ...prev, inventory: [...prev.inventory, item] };
      }
      return prev;
    });
  }, []);

  const removeFromInventory = useCallback((item: string) => {
    setGameState((prev) => ({
      ...prev,
      inventory: prev.inventory.filter((i) => i !== item),
    }));
  }, []);

  const updateHealth = useCallback((amount: number) => {
    setGameState((prev) => ({
      ...prev,
      health: Math.max(0, Math.min(100, prev.health + amount)),
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

  const updateRelationship = useCallback((npcId: string, value: number) => {
    setGameState((prev) => ({
      ...prev,
      relationships: {
        ...prev.relationships,
        [npcId]: (prev.relationships[npcId] || 0) + value,
      },
    }));
  }, []);

  const updateSkill = useCallback((skill: string, value: number) => {
    setGameState((prev) => ({
      ...prev,
      skills: {
        ...prev.skills,
        [skill]: Math.min(100, (prev.skills[skill] || 0) + value),
      },
    }));
  }, []);

  const addAchievement = useCallback((achievement: string) => {
    setGameState((prev) => {
      if (!prev.achievements.includes(achievement)) {
        return { ...prev, achievements: [...prev.achievements, achievement] };
      }
      return prev;
    });
  }, []);

  const recordDecision = useCallback((decision: string) => {
    setGameState((prev) => ({
      ...prev,
      decisions: [...prev.decisions, decision],
      turnCount: prev.turnCount + 1,
    }));
  }, []);

  const updateLocation = useCallback((location: string) => {
    setGameState((prev) => ({
      ...prev,
      currentLocation: location,
      visitedLocations: prev.visitedLocations.includes(location)
        ? prev.visitedLocations
        : [...prev.visitedLocations, location],
    }));
  }, []);

  const updateStoryArc = useCallback((arc: string | null) => {
    setGameState((prev) => ({ ...prev, storyArc: arc }));
  }, []);

  const reset = useCallback(() => {
    setGameState(initialGameState);
  }, []);

  const getGameSummary = useCallback(
    () => ({
      playerName: gameState.playerName,
      turnCount: gameState.turnCount,
      health: gameState.health,
      inventoryCount: gameState.inventory.length,
      loreDiscovered: gameState.discoveredLore.length,
      locationsVisited: gameState.visitedLocations.length,
      decisionsCount: gameState.decisions.length,
      achievements: gameState.achievements.length,
    }),
    [gameState]
  );

  return {
    gameState,
    updatePlayerName,
    addToInventory,
    removeFromInventory,
    updateHealth,
    discoverLore,
    updateRelationship,
    updateSkill,
    addAchievement,
    recordDecision,
    updateLocation,
    updateStoryArc,
    reset,
    getGameSummary,
  };
};
