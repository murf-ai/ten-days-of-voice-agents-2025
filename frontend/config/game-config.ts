export const GAME_MASTER_CONFIG = {
  universe: {
    name: 'Eldoria',
    description: 'A realm of ancient magic, forgotten kingdoms, and shadow creatures',
    timeOfDay: 'dusk',
    weather: 'misty rain',
  },

  gameplay: {
    maxTurns: 50,
    maxInventorySlots: 10,
    startingHealth: 100,
    difficulty: 'normal' as const,
    autoSave: true,
    autoSaveInterval: 5, // turns
  },

  features: {
    voiceInput: true,
    textInput: true,
    gameSave: true,
    achievements: true,
    skillSystem: true,
    relationshipTracking: true,
    loreDiscovery: true,
  },

  ui: {
    theme: 'dark-fantasy',
    showGameState: true,
    animateMessages: true,
    soundEnabled: false,
    messageDelay: 1500, // ms
  },

  storytelling: {
    minResponseLength: 150,
    maxResponseLength: 1000,
    branching: true,
    consequenceTracking: true,
    worldReactivity: true,
  },

  npcBehaviors: {
    kaelTrust: 0,
    guardianRespect: 0,
    shadowOrderHatred: 0,
  },
};

export const DIFFICULTY_SETTINGS = {
  easy: {
    skillCheckModifier: 1.5,
    healthMultiplier: 1.2,
    encounterFrequency: 0.5,
    lootChance: 0.8,
  },
  normal: {
    skillCheckModifier: 1,
    healthMultiplier: 1,
    encounterFrequency: 1,
    lootChance: 0.6,
  },
  hard: {
    skillCheckModifier: 0.75,
    healthMultiplier: 0.8,
    encounterFrequency: 1.5,
    lootChance: 0.4,
  },
  nightmare: {
    skillCheckModifier: 0.5,
    healthMultiplier: 0.6,
    encounterFrequency: 2,
    lootChance: 0.2,
  },
};

export const ACHIEVEMENT_CONDITIONS = {
  firstSteps: { condition: 'turnCount >= 5', reward: '+10 XP', icon: '👣' },
  trustedAlly: { condition: 'kaelRelationship >= 10', reward: '+25 XP', icon: '🤝' },
  forestWalker: { condition: 'visitedLocations.includes("forest")', reward: '+15 XP', icon: '🌲' },
  templeExplorer: { condition: 'visitedLocations.includes("temple")', reward: '+50 XP', icon: '🏛️' },
  crystalSeeker: { condition: 'inventory.includes("Crystal of Zar\'an")', reward: '+100 XP', icon: '💎' },
  wiseSacrifice: { condition: 'decision === "destroy_crystal"', reward: '+75 XP', icon: '⚖️' },
  shadowDefeat: { condition: 'shadowOrderDefeated === true', reward: '+200 XP', icon: '⚔️' },
};
