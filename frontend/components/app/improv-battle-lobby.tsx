// frontend/components/app/improv-battle-lobby.tsx
'use client';

import React, { useState } from 'react';
import { LiveKitRoom } from '@livekit/components-react';
import ImprovBattleUI from './improv-battle-ui';

interface ImprovBattleLobbyProps {
  onBack: () => void;
}

export function ImprovBattleLobby({ onBack }: ImprovBattleLobbyProps) {
  const [name, setName] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [connected, setConnected] = useState(false);

  const handleStartGame = async () => {
    if (!name.trim()) return;
    setIsConnecting(true);

    // In a real app you'd request a LiveKit token from your backend here.
    // For this demo we simply mark as "connected" so LiveKitRoom mounts.
    // The actual connection will be attempted by <LiveKitRoom /> using env vars.
    setConnected(true);
  };

  // Lobby screen (before connecting)
  if (!connected) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 flex items-center justify-center p-4">
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 max-w-md w-full border border-white/20 relative">
          {/* Back Button */}
          <button
            onClick={onBack}
            className="absolute top-4 left-4 text-gray-300 hover:text-white transition-colors"
          >
            ← Back
          </button>

          <div className="text-center">
            <h1 className="text-4xl font-bold text-yellow-400 mb-2">🎭</h1>
            <h2 className="text-2xl font-bold text-white mb-2">Improv Battle</h2>
            <p className="text-gray-300 mb-6">Join the ultimate voice improv challenge!</p>

            <div className="space-y-4">
              <div>
                <label className="block text-white text-sm font-medium mb-2 text-left">Contestant Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter your name"
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-yellow-400 focus:border-transparent"
                  onKeyDown={(e) => { if (e.key === 'Enter') handleStartGame(); }}
                />
              </div>

              <button
                onClick={handleStartGame}
                disabled={!name.trim() || isConnecting}
                className="w-full bg-yellow-500 hover:bg-yellow-600 disabled:bg-gray-600 text-black font-bold py-3 px-6 rounded-lg transition-colors duration-200 flex items-center justify-center"
              >
                {isConnecting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-black mr-2" />
                    Connecting...
                  </>
                ) : (
                  '🎭 Start Improv Battle'
                )}
              </button>
            </div>

            <div className="mt-6 text-sm text-gray-400">
              <p>• 3 rounds of improv scenarios</p>
              <p>• Voice-first performance</p>
              <p>• AI host feedback</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // LiveKitRoom screen (after clicking Start) — LiveKitRoom will attempt connection.
  return (
    <LiveKitRoom
      serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL || ''}
      token={process.env.NEXT_PUBLIC_LIVEKIT_TOKEN || ''}
      connect={true}
      audio={true}
      video={false}
      onConnected={() => {
        console.log('✅ Connected to LiveKit');
        setIsConnecting(false);
      }}
      onDisconnected={() => {
        console.log('❌ Disconnected from LiveKit');
        setIsConnecting(false);
        setConnected(false);
      }}
      onError={(error) => {
        console.error('💥 LiveKit error:', error);
        setIsConnecting(false);
      }}
    >
      <ImprovBattleUI playerName={name} onBack={() => { setConnected(false); onBack(); }} />
    </LiveKitRoom>
  );
}
