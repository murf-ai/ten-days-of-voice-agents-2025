'use client';

import { useState } from 'react';
import { motion } from 'motion/react';
import { Button } from '@/components/livekit/button';
import { Mic2, RotateCcw } from 'lucide-react';

interface ImprovGameViewProps {
  onStartGame: (playerName: string) => void;
  onBack?: () => void;
}

export const ImprovGameView = ({ onStartGame, onBack }: ImprovGameViewProps) => {
  const [playerName, setPlayerName] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleStartGame = async () => {
    if (playerName.trim()) {
      setIsLoading(true);
      onStartGame(playerName.trim());
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && playerName.trim() && !isLoading) {
      handleStartGame();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="flex h-svh w-full items-center justify-center bg-linear-to-br from-purple-900 via-black to-black p-4"
    >
      <div className="w-full max-w-md">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8 text-center"
        >
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-purple-600/20 p-3">
            <Mic2 className="h-8 w-8 text-purple-400" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">
            🎭 Improv Battle
          </h1>
          <p className="text-gray-400 text-sm">
            Show off your improvisation skills with an AI host
          </p>
        </motion.div>

        {/* Join Form */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-6 rounded-xl border border-purple-500/20 bg-black/40 backdrop-blur-sm p-6"
        >
          {/* Name Input */}
          <div className="space-y-2">
            <label htmlFor="playerName" className="block text-sm font-medium text-gray-300">
              Your Name
            </label>
            <input
              id="playerName"
              type="text"
              placeholder="Enter your contestant name..."
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
              className="w-full rounded-lg border border-purple-500/30 bg-black/50 px-4 py-3 text-white placeholder-gray-500 transition-all focus:border-purple-500 focus:bg-black/70 focus:outline-none focus:ring-2 focus:ring-purple-500/20 disabled:opacity-50"
            />
          </div>

          {/* Info Box */}
          <div className="rounded-lg bg-purple-500/10 p-4 border border-purple-500/20">
            <h3 className="text-sm font-semibold text-purple-300 mb-2">How it works:</h3>
            <ul className="space-y-1 text-xs text-gray-400">
              <li>✨ Get a unique improv scenario</li>
              <li>🎤 Perform in character using your voice</li>
              <li>⭐ Get witty feedback from the host</li>
              <li>🔄 Complete multiple rounds</li>
            </ul>
          </div>

          {/* Start Button */}
          <Button
            variant="primary"
            size="lg"
            onClick={handleStartGame}
            disabled={!playerName.trim() || isLoading}
            className="w-full"
          >
            {isLoading ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
              </motion.div>
            ) : (
              <Mic2 className="mr-2 h-4 w-4" />
            )}
            {isLoading ? 'Starting Battle...' : 'Start Improv Battle'}
          </Button>

          {/* Back Button */}
          {onBack && (
            <Button
              variant="secondary"
              size="lg"
              onClick={onBack}
              disabled={isLoading}
              className="w-full"
            >
              Back
            </Button>
          )}
        </motion.div>

        {/* Footer */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mt-6 text-center text-xs text-gray-500"
        >
          Get ready to think on your feet! 🎤
        </motion.p>
      </div>
    </motion.div>
  );
};
