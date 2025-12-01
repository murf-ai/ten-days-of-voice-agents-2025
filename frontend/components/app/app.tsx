'use client';

import React, { useState } from 'react';
import { RoomAudioRenderer, StartAudio } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { ImprovBattleLobby } from '@/components/app/improv-battle-lobby';

interface AppProps {
  appConfig: AppConfig;
}

/**
 * Main app component which shows a landing / view controller by default,
 * and lets the user switch into the Improv Battle experience.
 */
export function App({ appConfig }: AppProps) {
  const [gameMode, setGameMode] = useState<'default' | 'improv-battle'>('default');

  // Defensive: ensure appConfig exists
  if (!appConfig) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="max-w-xl w-full text-center bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-2">Missing app configuration</h2>
          <p className="text-sm text-gray-600">Please provide a valid appConfig to initialize the session.</p>
        </div>
      </div>
    );
  }

  return (
    <SessionProvider appConfig={appConfig}>
      {gameMode === 'improv-battle' ? (
        <>
          <ImprovBattleLobby onBack={() => setGameMode('default')} />
          {/* UI components for audio playback and monitoring */}
          <StartAudio label="Start Audio" />
          <RoomAudioRenderer />
          <Toaster />
        </>
      ) : (
        <>
          <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
            {/* Game Mode Selection */}
            <div className="fixed top-4 left-4 z-10">
              <button
                onClick={() => setGameMode('improv-battle')}
                className="bg-yellow-500 hover:bg-yellow-600 text-black font-bold py-2 px-4 rounded-lg transition-colors"
                aria-label="Start Improv Battle"
              >
                🎭 Start Improv Battle
              </button>
            </div>

            <main className="grid h-screen grid-cols-1 place-content-center px-4">
              <ViewController />
            </main>
          </div>

          {/* Always include audio controls & toast so session audio works */}
          <StartAudio label="Start Audio" />
          <RoomAudioRenderer />
          <Toaster />
        </>
      )}
    </SessionProvider>
  );
}

export default App;
