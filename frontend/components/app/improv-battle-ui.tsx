// frontend/components/app/improv-battle-ui.tsx
'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  useRoomContext,
  useConnectionState,
  useDataChannel,
  useLocalParticipant,
} from '@livekit/components-react';
import { DataPacket_Kind } from 'livekit-client';

interface Round {
  scenario: string;
  host_reaction: string;
}

interface GameState {
  player_name: string;
  current_round: number;
  max_rounds: number;
  rounds: Round[];
  phase: 'intro' | 'awaiting_improv' | 'reacting' | 'done';
  current_scenario?: string;
}

interface ImprovBattleUIProps {
  playerName: string;
  onBack: () => void;
}

function decodePayload(payload: any): string {
  try {
    // payload can be Uint8Array, ArrayBuffer, or string depending on implementation
    if (!payload) return '';
    if (typeof payload === 'string') return payload;
    // if ArrayBuffer
    if (payload instanceof ArrayBuffer) {
      return new TextDecoder().decode(new Uint8Array(payload));
    }
    // if Uint8Array
    if (payload instanceof Uint8Array) {
      return new TextDecoder().decode(payload);
    }
    // if a wrapper object with .data or .payload
    if (payload.data) {
      return decodePayload(payload.data);
    }
    if (payload.payload) {
      return decodePayload(payload.payload);
    }
    // fallback - try JSON stringify
    return String(payload);
  } catch (e) {
    console.error('decodePayload error', e);
    return '';
  }
}

export default function ImprovBattleUI({ playerName, onBack }: ImprovBattleUIProps) {
  const [gameState, setGameState] = useState<GameState>({
    player_name: playerName || 'Guest',
    current_round: 0,
    max_rounds: 3,
    rounds: [],
    phase: 'intro',
  });
  const [isRecording, setIsRecording] = useState(false);
  const [connectionError, setConnectionError] = useState<string>('');
  const hasSentJoinMessage = useRef(false);

  // LiveKit hooks (may return undefined until connected)
  const room = useRoomContext?.();
  const connectionState = useConnectionState?.() ?? 'disconnected';
  const localParticipantWrapper = useLocalParticipant?.();
  const localParticipant = localParticipantWrapper?.localParticipant ?? null;

  // useDataChannel may return undefined until room ready; capture the returned object then extract send
  const dataChannelObj = useDataChannel?.('improv-battle', (msg: any) => {
    try {
      // Message payload handling: decode safely
      const raw = decodePayload(msg?.payload ?? msg?.data ?? msg);
      if (!raw) return;
      const data = JSON.parse(raw);
      // console.log('dataChannel message:', data);
      if (data.type === 'game_state_update' && data.state) {
        setGameState(data.state);
      } else if (data.type === 'scenario_start' && data.scenario) {
        setGameState(prev => ({
          ...prev,
          current_scenario: data.scenario,
          phase: 'awaiting_improv',
        }));
      } else if (data.type === 'host_reaction' && data.reaction) {
        setGameState(prev => ({
          ...prev,
          phase: 'reacting',
          rounds: [
            ...prev.rounds,
            {
              scenario: data.scenario ?? prev.current_scenario ?? `Round ${prev.current_round}`,
              host_reaction: data.reaction,
            },
          ],
        }));
      } else if (data.type === 'game_completed') {
        setGameState(prev => ({ ...prev, phase: 'done' }));
      }
    } catch (err) {
      console.error('Error parsing data channel message', err);
    }
  }) ?? null;

  // Extract send function safely
  const send = (dataChannelObj as any)?.send ?? undefined;

  // When connected, send a join message once
  useEffect(() => {
    if (connectionState === 'connected' && localParticipant && !hasSentJoinMessage.current) {
      if (!send) {
        setConnectionError('Data channel not ready yet.');
        return;
      }
      try {
        const data = { type: 'player_join', player_name: playerName || 'Guest', timestamp: Date.now() };
        // send expects ArrayBuffer | string | Uint8Array
        send(new TextEncoder().encode(JSON.stringify(data)), DataPacket_Kind.RELIABLE);
        hasSentJoinMessage.current = true;
        setConnectionError('');
      } catch (err) {
        console.error('Failed to send join:', err);
        setConnectionError('Failed to connect to game (join).');
      }
    }
  }, [connectionState, localParticipant, playerName, send]);

  const safeSend = (payload: any) => {
    if (!send) {
      setConnectionError('Not connected to game server (data channel missing).');
      return false;
    }
    try {
      send(new TextEncoder().encode(JSON.stringify(payload)), DataPacket_Kind.RELIABLE);
      setConnectionError('');
      return true;
    } catch (err) {
      console.error('safeSend error', err);
      setConnectionError('Failed to send game action.');
      return false;
    }
  };

  const startImprov = () => {
    setIsRecording(true);
    safeSend({ type: 'start_improv', timestamp: Date.now() });
  };

  const endScene = () => {
    setIsRecording(false);
    safeSend({ type: 'end_scene', timestamp: Date.now() });
  };

  const endGame = () => {
    safeSend({ type: 'end_game', timestamp: Date.now() });
    onBack();
  };

  // Render
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 text-white">
      {/* Header */}
      <div className="bg-black/50 border-b border-white/20 p-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <button onClick={onBack} className="text-gray-300 hover:text-white transition-colors">
              ← Back
            </button>
            <div>
              <h1 className="text-2xl font-bold text-yellow-400">🎭 Improv Battle</h1>
              <p className="text-gray-300">Player: {gameState.player_name}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold">
              Round {gameState.current_round} / {gameState.max_rounds}
            </div>
            <div className="text-sm text-gray-300 capitalize">Phase: {gameState.phase}</div>
          </div>
        </div>
      </div>

      {/* Connection Error */}
      {connectionError && <div className="bg-red-600 text-white p-3 text-center">⚠️ {connectionError}</div>}

      {/* Main Content */}
      <div className="container mx-auto p-6 max-w-4xl">
        {/* Current Scenario */}
        {gameState.current_scenario ? (
          <div className="bg-yellow-500/20 border border-yellow-400 rounded-xl p-6 mb-6">
            <h2 className="text-xl font-bold text-yellow-400 mb-3">🎯 Current Scenario</h2>
            <p className="text-lg">{gameState.current_scenario}</p>

            {gameState.phase === 'awaiting_improv' && (
              <div className="mt-4 flex items-center space-x-4">
                <div className={`w-3 h-3 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-gray-500'}`} />
                <span className="text-sm">{isRecording ? 'Performing your improv...' : 'Ready for your performance'}</span>

                {!isRecording ? (
                  <button
                    onClick={startImprov}
                    disabled={connectionState !== 'connected'}
                    className="ml-auto bg-green-500 hover:bg-green-600 disabled:bg-gray-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  >
                    🎤 Start Improv
                  </button>
                ) : (
                  <button
                    onClick={endScene}
                    disabled={connectionState !== 'connected'}
                    className="ml-auto bg-red-500 hover:bg-red-600 disabled:bg-gray-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  >
                    🏁 End Scene
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white/5 border border-white/5 rounded-xl p-6 mb-6 text-center text-gray-200">
            Waiting for the host to start the next scenario...
          </div>
        )}

        {/* Game Status */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Round Progress */}
          <div className="bg-white/10 rounded-xl p-6">
            <h3 className="font-bold text-lg mb-3">📊 Game Progress</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Rounds Completed:</span>
                <span>
                  {gameState.current_round} / {gameState.max_rounds}
                </span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-green-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(gameState.current_round / Math.max(1, gameState.max_rounds)) * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* Current Phase */}
          <div className="bg-white/10 rounded-xl p-6">
            <h3 className="font-bold text-lg mb-3">🎮 Game Status</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Phase:</span>
                <span className="capitalize">{gameState.phase}</span>
              </div>
              <div className="flex justify-between">
                <span>Connection:</span>
                <span
                  className={
                    connectionState === 'connected' ? 'text-green-400' : connectionState === 'connecting' ? 'text-yellow-400' : 'text-red-400'
                  }
                >
                  {connectionState}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Previous Rounds */}
        {gameState.rounds.length > 0 && (
          <div className="bg-white/10 rounded-xl p-6 mb-6">
            <h3 className="font-bold text-lg mb-4">📝 Previous Rounds</h3>
            <div className="space-y-4">
              {gameState.rounds.map((round, index) => (
                <div key={index} className="border-l-4 border-yellow-400 pl-4 py-2">
                  <div className="font-semibold text-yellow-300 mb-1">Round {index + 1}</div>
                  <div className="text-sm text-gray-300 mb-2">
                    <strong>Scenario:</strong> {round.scenario}
                  </div>
                  <div className="text-sm">
                    <strong>Host Feedback:</strong> {round.host_reaction}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex justify-center space-x-4">
          <button onClick={endGame} className="bg-red-500 hover:bg-red-600 px-6 py-3 rounded-lg font-semibold transition-colors">
            🏁 End Game
          </button>
        </div>

        {/* Instructions */}
        <div className="mt-8 bg-black/30 rounded-xl p-6">
          <h3 className="font-bold text-lg mb-3">🎯 How to Play</h3>
          <ul className="space-y-2 text-sm text-gray-300">
            <li>• Listen to the host's scenario</li>
            <li>• Click "Start Improv" and perform your scene</li>
            <li>• Click "End Scene" when finished</li>
            <li>• Receive host feedback after each round</li>
            <li>• Complete all rounds to finish the game</li>
          </ul>
        </div>
      </div>

      {/* Connection Status */}
      <div
        className={`fixed bottom-0 left-0 right-0 p-2 text-center text-sm ${
          connectionState === 'connected' ? 'bg-green-600' : connectionState === 'connecting' ? 'bg-yellow-600' : 'bg-red-600'
        }`}
      >
        {connectionState === 'connected' ? '✅ Connected to Improv Battle' : connectionState === 'connecting' ? '🔄 Connecting...' : '❌ Disconnected'}
      </div>
    </div>
  );
}
