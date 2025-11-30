// import { Button } from '@/components/livekit/button';

// function WelcomeImage() {
//   return (
//     <svg
//       width="64"
//       height="64"
//       viewBox="0 0 64 64"
//       fill="none"
//       xmlns="http://www.w3.org/2000/svg"
//       className="text-fg0 mb-4 size-16"
//     >
//       <path
//         d="M15 24V40C15 40.7957 14.6839 41.5587 14.1213 42.1213C13.5587 42.6839 12.7956 43 12 43C11.2044 43 10.4413 42.6839 9.87868 42.1213C9.31607 41.5587 9 40.7957 9 40V24C9 23.2044 9.31607 22.4413 9.87868 21.8787C10.4413 21.3161 11.2044 21 12 21C12.7956 21 13.5587 21.3161 14.1213 21.8787C14.6839 22.4413 15 23.2044 15 24ZM22 5C21.2044 5 20.4413 5.31607 19.8787 5.87868C19.3161 6.44129 19 7.20435 19 8V56C19 56.7957 19.3161 57.5587 19.8787 58.1213C20.4413 58.6839 21.2044 59 22 59C22.7956 59 23.5587 58.6839 24.1213 58.1213C24.6839 57.5587 25 56.7957 25 56V8C25 7.20435 24.6839 6.44129 24.1213 5.87868C23.5587 5.31607 22.7956 5 22 5ZM32 13C31.2044 13 30.4413 13.3161 29.8787 13.8787C29.3161 14.4413 29 15.2044 29 16V48C29 48.7957 29.3161 49.5587 29.8787 50.1213C30.4413 50.6839 31.2044 51 32 51C32.7956 51 33.5587 50.6839 34.1213 50.1213C34.6839 49.5587 35 48.7957 35 48V16C35 15.2044 34.6839 14.4413 34.1213 13.8787C33.5587 13.3161 32.7956 13 32 13ZM42 21C41.2043 21 40.4413 21.3161 39.8787 21.8787C39.3161 22.4413 39 23.2044 39 24V40C39 40.7957 39.3161 41.5587 39.8787 42.1213C40.4413 42.6839 41.2043 43 42 43C42.7957 43 43.5587 42.6839 44.1213 42.1213C44.6839 41.5587 45 40.7957 45 40V24C45 23.2044 44.6839 22.4413 44.1213 21.8787C43.5587 21.3161 42.7957 21 42 21ZM52 17C51.2043 17 50.4413 17.3161 49.8787 17.8787C49.3161 18.4413 49 19.2044 49 20V44C49 44.7957 49.3161 45.5587 49.8787 46.1213C50.4413 46.6839 51.2043 47 52 47C52.7957 47 53.5587 46.6839 54.1213 46.1213C54.6839 45.5587 55 44.7957 55 44V20C55 19.2044 54.6839 18.4413 54.1213 17.8787C53.5587 17.3161 52.7957 17 52 17Z"
//         fill="currentColor"
//       />
//     </svg>
//   );
// }

// interface WelcomeViewProps {
//   startButtonText: string;
//   onStartCall: () => void;
// }

// export const WelcomeView = ({
//   startButtonText,
//   onStartCall,
//   ref,
// }: React.ComponentProps<'div'> & WelcomeViewProps) => {
//   return (
//     <div ref={ref}>
//       <section className="bg-background flex flex-col items-center justify-center text-center">
//         <WelcomeImage />

//         <p className="text-foreground max-w-prose pt-1 leading-6 font-medium">
//           Chat live with your voice AI agent
//         </p>

//         <Button variant="primary" size="lg" onClick={onStartCall} className="mt-6 w-64 font-mono">
//           {startButtonText}
//         </Button>
//       </section>

//       <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
//         <p className="text-muted-foreground max-w-prose pt-1 text-xs leading-5 font-normal text-pretty md:text-sm">
//           Need help getting set up? Check out the{' '}
//           <a
//             target="_blank"
//             rel="noopener noreferrer"
//             href="https://docs.livekit.io/agents/start/voice-ai/"
//             className="underline"
//           >
//             Voice AI quickstart
//           </a>
//           .
//         </p>
//       </div>
//     </div>
//   );
// };



"use client";

import { Button } from "@/components/livekit/button";
import { useSession } from "./session-provider";
import { Mic, Sparkles } from "lucide-react";

export function WelcomeView() {
  const { startSession } = useSession();

  return (
    <div className="flex h-screen w-full items-center justify-center bg-linear-to-br from-gray-900 via-black to-orange-900">
      <div className="w-full max-w-2xl px-6 text-center">
        {/* Logo/Icon */}
        <div className="mb-8">
          <div className="mx-auto mb-4 flex h-24 w-24 items-center justify-center rounded-full bg-orange-500/20 text-6xl">
            🎭
          </div>
          <h1 className="mb-2 text-5xl font-bold text-white">
            Improv Battle
          </h1>
          <p className="text-xl text-orange-400">भारतीय संस्करण</p>
        </div>

        {/* Tagline */}
        <p className="mb-8 text-2xl font-medium text-gray-300">
          बोलो, अभिनय करो, हँसो!
          <br />
          <span className="text-lg text-gray-400">
            Speak, Act, Laugh!
          </span>
        </p>

        {/* Description */}
        <div className="mb-10 rounded-lg border border-gray-700 bg-gray-900/50 p-6">
          <p className="text-gray-300">
            A high-energy improv game show where you perform in absurd Indian
            scenarios. The AI host will give you crazy situations in Hinglish,
            and you'll improvise your way through them!
          </p>
        </div>

        {/* Features */}
        <div className="mb-10 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-orange-500/30 bg-orange-500/10 p-4">
            <div className="mb-2 text-2xl">🎤</div>
            <h3 className="font-semibold text-orange-400">Voice-Powered</h3>
            <p className="text-sm text-gray-400">Speak naturally in Hinglish</p>
          </div>
          <div className="rounded-lg border border-purple-500/30 bg-purple-500/10 p-4">
            <div className="mb-2 text-2xl">🎭</div>
            <h3 className="font-semibold text-purple-400">4 Scenarios</h3>
            <p className="text-sm text-gray-400">Crazy Indian situations</p>
          </div>
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-4">
            <div className="mb-2 text-2xl">😄</div>
            <h3 className="font-semibold text-green-400">Live Reactions</h3>
            <p className="text-sm text-gray-400">Host reacts to your improv</p>
          </div>
        </div>

        {/* Start Button */}
        <Button
          size="lg"
          onClick={startSession}
          className="h-14 gap-3 bg-orange-600 px-8 text-lg font-semibold hover:bg-orange-700"
        >
          <Mic className="h-5 w-5" />
          Start Improv Battle
          <Sparkles className="h-5 w-5" />
        </Button>

        <p className="mt-6 text-sm text-gray-500">
          Make sure your microphone is enabled
        </p>
      </div>
    </div>
  );
}
