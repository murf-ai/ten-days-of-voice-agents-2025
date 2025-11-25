'use client';

import React, { useEffect, useRef, useState } from 'react';
import { DataPacket_Kind, RemoteParticipant } from 'livekit-client';
import { motion } from 'motion/react';
import { useRoomContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { ChatTranscript } from '@/components/app/chat-transcript';
import { PreConnectMessage } from '@/components/app/preconnect-message';
import { TileLayout } from '@/components/app/tile-layout';
import {
  AgentControlBar,
  type ControlBarControls,
} from '@/components/livekit/agent-control-bar/agent-control-bar';
import { useChatMessages } from '@/hooks/useChatMessages';
import { useConnectionTimeout } from '@/hooks/useConnectionTimout';
import { useDebugMode } from '@/hooks/useDebug';
import { cn } from '@/lib/utils';
import { ScrollArea } from '../livekit/scroll-area/scroll-area';

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
    ease: 'easeOut',
  },
};

// --- Types for Wellness Check-in ---
interface CheckinLogEntry {
  timestamp: string;
  mood_summary: string | null;
  energy_level: string | null;
  objectives: string[];
  agent_summary: string | null;
}

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

interface SessionViewProps {
  appConfig: AppConfig;
}

export const SessionView = ({
  appConfig,
  ...props
}: React.ComponentProps<'section'> & SessionViewProps) => {
  useConnectionTimeout(200_000);
  useDebugMode({ enabled: IN_DEVELOPMENT });

  const room = useRoomContext();
  const messages = useChatMessages();
  const [chatOpen, setChatOpen] = useState(false);
  const [completedCheckin, setCompletedCheckin] = useState<CheckinLogEntry | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const controls: ControlBarControls = {
    leave: true,
    microphone: true,
    chat: appConfig.supportsChatInput,
    camera: appConfig.supportsVideoInput,
    screenShare: appConfig.supportsVideoInput,
  };

  // Listen for check-in completion data from agent
  useEffect(() => {
    if (!room) return;

    const handleDataReceived = (
      payload: Uint8Array,
      participant?: RemoteParticipant,
      kind?: DataPacket_Kind,
      topic?: string
    ) => {
      if (topic !== 'checkin_complete') return;

      try {
        const message = new TextDecoder().decode(payload);
        const data = JSON.parse(message);

        if (data.type === 'CHECKIN_COMPLETE' && data.entry) {
          console.log('Check-in Received:', data.entry);
          setCompletedCheckin(data.entry as CheckinLogEntry);
          setChatOpen(true); // Auto-open chat to show summary
        }
      } catch (e) {
        console.error('Failed to parse check-in data:', e);
      }
    };

    room.on('dataReceived', handleDataReceived);
    return () => {
      room.off('dataReceived', handleDataReceived);
    };
  }, [room]);

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <section className="bg-background relative z-10 h-full w-full overflow-hidden" {...props}>
      {/* Chat Transcript */}
      <div
        className={cn(
          'fixed inset-0 grid grid-cols-1 grid-rows-1',
          !chatOpen && 'pointer-events-none'
        )}
      >
        <Fade top className="absolute inset-x-4 top-0 h-40" />
        <ScrollArea ref={scrollAreaRef} className="px-4 pt-40 pb-[150px] md:px-6 md:pb-[180px]">
          <ChatTranscript
            hidden={!chatOpen}
            messages={messages}
            className="mx-auto max-w-2xl space-y-3 transition-opacity duration-300 ease-out"
          />

          {/* Wellness Check-in Summary - Shows in the transcript area */}
          {completedCheckin && chatOpen && (
            <div className="mx-auto mt-6 max-w-2xl">
              <CheckinSummary entry={completedCheckin} />
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Tile Layout */}
      <TileLayout chatOpen={chatOpen} />

      {/* Bottom */}
      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="fixed inset-x-3 bottom-0 z-50 md:inset-x-12"
      >
        {appConfig.isPreConnectBufferEnabled && (
          <PreConnectMessage messages={messages} className="pb-4" />
        )}
        <div className="bg-background relative mx-auto max-w-2xl pb-3 md:pb-12">
          <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
          <AgentControlBar controls={controls} onChatOpenChange={setChatOpen} />
        </div>
      </MotionBottom>
    </section>
  );
};

// --- Wellness Check-in Summary Component ---
const CheckinSummary = ({ entry }: { entry: CheckinLogEntry }) => {
  const date = new Date(entry.timestamp);
  const formattedDate = date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
  const formattedTime = date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="bg-card border-border animate-in fade-in slide-in-from-bottom-4 rounded-lg border p-6 shadow-lg duration-500">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-xl font-bold">Daily Check-in Complete ✓</h3>
          <p className="text-muted-foreground text-sm">
            {formattedDate} at {formattedTime}
          </p>
        </div>
        <MoodEmoji mood={entry.mood_summary} />
      </div>

      <div className="space-y-4">
        {/* Mood Section */}
        {entry.mood_summary && (
          <div className="rounded-md bg-blue-50 p-3 dark:bg-blue-900/20">
            <p className="text-xs font-semibold tracking-wide text-blue-600 uppercase dark:text-blue-400">
              Mood
            </p>
            <p className="mt-1 text-sm font-medium capitalize">{entry.mood_summary}</p>
          </div>
        )}

        {/* Energy Section */}
        {entry.energy_level && (
          <div className="rounded-md bg-amber-50 p-3 dark:bg-amber-900/20">
            <p className="text-xs font-semibold tracking-wide text-amber-600 uppercase dark:text-amber-400">
              Energy Level
            </p>
            <div className="mt-2 flex items-center gap-2">
              <EnergyBar level={entry.energy_level} />
              <span className="text-sm font-medium capitalize">{entry.energy_level}</span>
            </div>
          </div>
        )}

        {/* Objectives Section */}
        {entry.objectives && entry.objectives.length > 0 && (
          <div className="rounded-md bg-green-50 p-3 dark:bg-green-900/20">
            <p className="text-xs font-semibold tracking-wide text-green-600 uppercase dark:text-green-400">
              Today's Objectives
            </p>
            <ul className="mt-2 space-y-1">
              {entry.objectives.map((obj, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-green-600 dark:text-green-400">✓</span>
                  <span>{obj}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Agent Summary */}
        {entry.agent_summary && (
          <div className="border-t pt-3">
            <p className="text-muted-foreground text-sm italic">"{entry.agent_summary}"</p>
          </div>
        )}
      </div>

      <div className="mt-4 rounded-md bg-purple-50 p-3 text-center text-sm text-purple-800 dark:bg-purple-900/20 dark:text-purple-200">
        ✨ Keep up the great work! Your check-in has been saved.
      </div>
    </div>
  );
};

// --- Helper Components ---
const MoodEmoji = ({ mood }: { mood: string | null }) => {
  if (!mood) return <span className="text-4xl">😊</span>;

  const moodLower = mood.toLowerCase();

  if (moodLower.includes('happy') || moodLower.includes('great') || moodLower.includes('good')) {
    return <span className="text-4xl">😊</span>;
  }
  if (
    moodLower.includes('stressed') ||
    moodLower.includes('anxious') ||
    moodLower.includes('worried')
  ) {
    return <span className="text-4xl">😰</span>;
  }
  if (
    moodLower.includes('tired') ||
    moodLower.includes('exhausted') ||
    moodLower.includes('drained')
  ) {
    return <span className="text-4xl">😴</span>;
  }
  if (moodLower.includes('sad') || moodLower.includes('down') || moodLower.includes('low')) {
    return <span className="text-4xl">😔</span>;
  }
  if (
    moodLower.includes('motivated') ||
    moodLower.includes('energized') ||
    moodLower.includes('excited')
  ) {
    return <span className="text-4xl">🤩</span>;
  }

  return <span className="text-4xl">😊</span>;
};

const EnergyBar = ({ level }: { level: string }) => {
  const levelLower = level.toLowerCase();
  let bars = 2; // medium by default

  if (levelLower.includes('low')) bars = 1;
  if (levelLower.includes('high')) bars = 3;

  return (
    <div className="flex gap-1">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className={cn(
            'h-4 w-6 rounded',
            i <= bars ? 'bg-amber-500 dark:bg-amber-400' : 'bg-gray-200 dark:bg-gray-700'
          )}
        />
      ))}
    </div>
  );
};
