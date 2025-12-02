'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useChat } from '@livekit/components-react';
import { motion } from 'motion/react';
import type { AppConfig } from '@/app-config';
import { ChatTranscript } from '@/components/app/chat-transcript';
import {
  AgentControlBar,
  type ControlBarControls,
} from '@/components/livekit/agent-control-bar/agent-control-bar';
import { useChatMessages } from '@/hooks/useChatMessages';
import { useConnectionTimeout } from '@/lib/useConnectionTimeout';
import { useDebugMode } from '@/hooks/useDebug';
import { cn } from '@/lib/utils';
import { ScrollArea } from '../livekit/scroll-area/scroll-area';
import { Zap } from 'lucide-react';

const MotionBottom = motion.create('div');

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';
const BOTTOM_VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
  },
};

interface GameSessionViewProps {
  appConfig: AppConfig;
  playerName?: string;
}

export const GameSessionView = ({
  appConfig,
  playerName,
  ...props
}: React.ComponentProps<'section'> & GameSessionViewProps) => {
  useConnectionTimeout(200_000);
  useDebugMode({ enabled: IN_DEVELOPMENT });

  const messages = useChatMessages();
  const { send } = useChat();
  const [roundNumber] = useState(1);
  const [playerNameSent, setPlayerNameSent] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Send player name as initial message to the agent
  useEffect(() => {
    if (playerName && !playerNameSent && send) {
      const timer = setTimeout(() => {
        send(`My name is ${playerName}`);
        setPlayerNameSent(true);
      }, 500); // Small delay to ensure connection is ready
      
      return () => clearTimeout(timer);
    }
  }, [playerName, playerNameSent, send]);

  const controls: ControlBarControls = {
    leave: true,
    microphone: true,
    chat: appConfig.supportsChatInput,
    camera: appConfig.supportsVideoInput,
  };

  return (
    <section
      {...props}
      className={cn(
        'relative flex w-full flex-col items-stretch gap-3 overflow-hidden rounded-lg bg-linear-to-b from-purple-900/20 to-black p-4'
      )}
    >
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-purple-400" />
          <h2 className="text-lg font-bold text-white">🎭 Improv Battle</h2>
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-sm text-gray-400">Round {roundNumber}/5</span>
          <span className="text-sm font-semibold text-purple-400">{playerName || 'Player'}</span>
        </div>
      </motion.div>

      {/* Progress Bar */}
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ delay: 0.2 }}
        className="h-1 bg-gray-700 rounded-full overflow-hidden"
      >
        <motion.div
          className="h-full bg-linear-to-r from-purple-500 to-pink-500"
          initial={{ width: '0%' }}
          animate={{ width: `${(roundNumber / 5) * 100}%` }}
          transition={{ duration: 0.3 }}
        />
      </motion.div>

      {/* Chat Area */}
      <div className="relative flex flex-col items-stretch gap-3 rounded-lg bg-black/40 backdrop-blur-sm p-4 flex-1">
        <ScrollArea
          ref={scrollAreaRef}
          className="flex-1 overflow-hidden rounded-lg"
        >
          <div className="pr-4">
            <ChatTranscript messages={messages} />
          </div>
        </ScrollArea>

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="rounded-lg bg-purple-500/10 border border-purple-500/20 p-3 text-xs text-gray-400 space-y-1"
        >
          <p>💡 <strong>Tip:</strong> Commit to your character and have fun!</p>
          <p>🎤 Speak clearly and don't be afraid to be bold.</p>
        </motion.div>
      </div>

      {/* Control Bar */}
      <MotionBottom {...BOTTOM_VIEW_MOTION_PROPS}>
        <AgentControlBar controls={controls} />
      </MotionBottom>
    </section>
  );
};
