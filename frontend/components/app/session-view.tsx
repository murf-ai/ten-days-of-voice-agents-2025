'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
// Added useLocalParticipant to get the user's name
import { useLocalParticipant } from '@livekit/components-react';
import { ParticipantEvent, type LocalParticipant } from 'livekit-client';
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

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'pointer-events-none h-4',
        top && 'bg-gradient-to-b from-black/10 to-transparent',
        bottom && 'bg-gradient-to-t from-black/10 to-transparent',
        className
      )}
    />
  );
}

// === BACKGROUND ICONS ===
const FloatingIcon = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn("absolute opacity-10 text-white pointer-events-none select-none", className)}>
    {children}
  </div>
);

const TvIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
    <path d="M21 6h-7.59l3.29-3.29L16 2l-4 4-4-4-.71.71L10.59 6H3a2 2 0 00-2 2v12a2 2 0 002 2h18a2 2 0 002-2V8a2 2 0 00-2-2zm0 14H3V8h18v12zM9 10v8l7-4z" />
  </svg>
);

const TeddyIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
    <path d="M12 2C9 2 7 3.5 6 5c-1 0-4 1-4 4 0 2 1.5 3.5 3 3.8V14c0 3 4 4 7 4s7-1 7-4v-1.2c1.5-.3 3-1.8 3-3.8 0-3-3-4-4-4-1-1.5-3-3-6-3zm-3 8c.8 0 1.5.7 1.5 1.5S9.8 13 9 13s-1.5-.7-1.5-1.5.7-1.5 1.5-1.5zm6 0c.8 0 1.5.7 1.5 1.5S15.8 13 15 13s-1.5-.7-1.5-1.5.7-1.5 1.5-1.5z" />
  </svg>
);

const NoteIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
    <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
  </svg>
);

const StarIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full">
    <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
  </svg>
);

// === PLAYER BADGE ===
function PlayerBadge({ participant }: { participant?: LocalParticipant }) {
  // Use local state to ensure we re-render immediately on events
  const [displayName, setDisplayName] = useState('Sam');

  useEffect(() => {
    // If we have a participant, set up listeners, otherwise default is 'Sam'
    if (!participant) return;

    const updateName = () => {
      let name = participant.name || '';

      // Fallback: Check metadata if name is generic or empty
      if ((!name || name === 'user' || name === 'identity') && participant.metadata) {
        try {
          const meta = JSON.parse(participant.metadata);
          if (meta.name) name = meta.name;
          if (meta.displayName) name = meta.displayName;
        } catch {
          // Metadata was not JSON or didn't contain name
        }
      }

      // If the name is default 'user', 'identity' or empty, fall back to 'Sam'
      const finalName = (name === 'user' || name === 'identity' || name.trim() === '') 
        ? 'Sam' 
        : name;
      
      setDisplayName(finalName);
    };

    // Initial set
    updateName();

    participant.on(ParticipantEvent.NameChanged, updateName);
    participant.on(ParticipantEvent.MetadataChanged, updateName);

    return () => {
      participant.off(ParticipantEvent.NameChanged, updateName);
      participant.off(ParticipantEvent.MetadataChanged, updateName);
    };
  }, [participant]);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.5 }}
      className="absolute top-4 left-4 z-40 flex items-center gap-3 rounded-2xl 
      bg-white/20 p-2 pr-5 backdrop-blur-xl border border-white/30 shadow-xl ring-1 ring-white/20"
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 text-purple-900 shadow-sm">
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          viewBox="0 0 24 24" 
          fill="currentColor" 
          className="size-6"
        >
          <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM3.751 20.105a8.25 8.25 0 0 1 16.498 0 .75.75 0 0 1-.437.695A18.683 18.683 0 0 1 12 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 0 1-.437-.695Z" clipRule="evenodd" />
        </svg>
      </div>
      <div className="flex flex-col">
        <span className="text-[10px] uppercase font-bold text-white/70 tracking-wider">Contestant</span>
        <span className="text-sm font-extrabold text-white leading-none tracking-wide">{displayName}</span>
      </div>
    </motion.div>
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

  // Hook to get the current user's details
  const { localParticipant } = useLocalParticipant();
  
  const messages = useChatMessages();
  const [chatOpen, setChatOpen] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const controls: ControlBarControls = {
    leave: true,
    microphone: true,
    chat: appConfig.supportsChatInput,
    camera: appConfig.supportsVideoInput,
    screenShare: appConfig.supportsVideoInput,
  };

  useEffect(() => {
    const lastMessage = messages.at(-1);
    const lastMessageIsLocal = lastMessage?.from?.isLocal === true;

    if (scrollAreaRef.current && lastMessageIsLocal) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <section
      className="relative z-10 h-full w-full overflow-hidden"
      {...props}
    >
      {/* Background Gradient & Icons */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 select-none overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-900 via-purple-800 to-pink-700" />
        
        {/* Floating Icons Background */}
        <FloatingIcon className="top-[10%] left-[10%] w-12 h-12 -rotate-12 opacity-10">
          <TvIcon />
        </FloatingIcon>
        <FloatingIcon className="top-[20%] right-[15%] w-10 h-10 rotate-12 opacity-10">
          <TeddyIcon />
        </FloatingIcon>
        <FloatingIcon className="bottom-[15%] left-[8%] w-14 h-14 rotate-[-6deg] opacity-10">
          <NoteIcon />
        </FloatingIcon>
        <FloatingIcon className="bottom-[25%] right-[10%] w-8 h-8 rotate-45 opacity-15">
          <StarIcon />
        </FloatingIcon>
        <FloatingIcon className="top-[40%] left-[25%] w-6 h-6 rotate-[15deg] opacity-10">
          <StarIcon />
        </FloatingIcon>
        <FloatingIcon className="bottom-[40%] right-[30%] w-12 h-12 -rotate-[20deg] opacity-5">
          <TvIcon />
        </FloatingIcon>
      </div>

      {/* Player Badge */}
      <PlayerBadge participant={localParticipant} />

      {/* Chat Transcript -> Right Side */}
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
            className="ml-auto mr-0 md:mr-12 max-w-lg space-y-3 transition-opacity duration-300 ease-out"
          />
        </ScrollArea>
      </div>

      {/* Tile Layout (Agent Visuals) */}
      <TileLayout chatOpen={chatOpen} />

      {/* Bottom Controls -> Right Side Aligned */}
      <MotionBottom
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="fixed inset-x-3 bottom-0 z-50 md:inset-x-12"
      >
        {appConfig.isPreConnectBufferEnabled && (
          <PreConnectMessage messages={messages} className="pb-4" />
        )}
        
        <div className="relative ml-auto mr-0 md:mr-4 max-w-lg pb-3 md:pb-12">
          <Fade bottom className="absolute inset-x-0 top-0 h-4 -translate-y-full" />
          <AgentControlBar controls={controls} onChatOpenChange={setChatOpen} />
        </div>
      </MotionBottom>
    </section>
  );
};