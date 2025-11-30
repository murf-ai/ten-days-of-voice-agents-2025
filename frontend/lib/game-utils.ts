export interface GameConfig {
  maxTurns: number;
  maxInventoryItems: number;
  startingHealth: number;
  difficultyLevel: 'easy' | 'normal' | 'hard' | 'nightmare';
}

const DEFAULT_GAME_CONFIG: GameConfig = {
  maxTurns: 50,
  maxInventoryItems: 10,
  startingHealth: 100,
  difficultyLevel: 'normal',
};

const calculateDifficultyModifier = (
  difficulty: GameConfig['difficultyLevel']
): number => {
  const modifiers: Record<string, number> = {
    easy: 1.5,
    normal: 1,
    hard: 0.75,
    nightmare: 0.5,
  };
  return modifiers[difficulty];
};

const rollDice = (sides: number = 20, count: number = 1): number => {
  let total = 0;
  for (let i = 0; i < count; i++) {
    total += Math.floor(Math.random() * sides) + 1;
  }
  return total;
};

export interface SkillCheckResult {
  success: boolean;
  margin: number;
  criticalSuccess: boolean;
  criticalFailure: boolean;
}

const performSkillCheck = (
  skill: number,
  difficulty: number,
  difficultyModifier: number = 1
): SkillCheckResult => {
  const roll = rollDice(20, 1);
  const adjustedSkill = Math.floor(skill * difficultyModifier);
  const totalRoll = roll + adjustedSkill;
  const margin = totalRoll - difficulty;

  return {
    success: totalRoll >= difficulty,
    margin: Math.abs(margin),
    criticalSuccess: roll === 20,
    criticalFailure: roll === 1,
  };
};

const formatItemName = (item: string): string => {
  return item
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
};

const saveGameProgress = (gameData: Record<string, any>): void => {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem('eldoria_game_progress', JSON.stringify(gameData));
    } catch (error) {
      console.error('Failed to save game progress:', error);
    }
  }
};

const loadGameProgress = (): Record<string, any> | null => {
  if (typeof window !== 'undefined') {
    try {
      const data = localStorage.getItem('eldoria_game_progress');
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error('Failed to load game progress:', error);
      return null;
    }
  }
  return null;
};

export interface GameStats {
  completionPercentage: number;
  inventoryUsage: number;
  healthPercentage: number;
  loreDiscovered: number;
  relationsCount: number;
}

const calculateGameStats = (gameState: any): GameStats => {
  return {
    completionPercentage: Math.min(100, (gameState.turnCount / 50) * 100),
    inventoryUsage: (gameState.inventory.length / 10) * 100,
    healthPercentage: gameState.health,
    loreDiscovered: gameState.discoveredLore.length,
    relationsCount: Object.keys(gameState.relationships).length,
  };
};

export type DifficultyLevel = 'trivial' | 'easy' | 'medium' | 'hard' | 'deadly';

const getEncounterDifficulty = (turnCount: number): DifficultyLevel => {
  if (turnCount < 3) return 'trivial';
  if (turnCount < 6) return 'easy';
  if (turnCount < 10) return 'medium';
  if (turnCount < 15) return 'hard';
  return 'deadly';
};

const generateGameSummary = (gameState: any): string => {
  return `
🎲 **Game Summary**
━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Turns: ${gameState.turnCount}
❤️ Health: ${gameState.health}/100
📍 Location: ${gameState.currentLocation}
📦 Inventory: ${gameState.inventory.length}/10

📖 Discovered Lore: ${gameState.discoveredLore.length}
👥 Known NPCs: ${Object.keys(gameState.relationships).length}
🗺️ Visited Locations: ${gameState.visitedLocations.length}

🎯 Story Arc: ${gameState.storyArc || 'Unfolding...'}
━━━━━━━━━━━━━━━━━━━━━━━━━
  `;
};

export {
  DEFAULT_GAME_CONFIG,
  calculateDifficultyModifier,
  rollDice,
  performSkillCheck,
  formatItemName,
  saveGameProgress,
  loadGameProgress,
  calculateGameStats,
  getEncounterDifficulty,
  generateGameSummary,
};
