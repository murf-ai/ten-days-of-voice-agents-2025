import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-4 size-16 text-purple-600"
    >
      <path
        d="M32 8C18.7 8 8 18.7 8 32s10.7 24 24 24 24-10.7 24-24S45.3 8 32 8zm0 4c11.1 0 20 8.9 20 20s-8.9 20-20 20-20-8.9-20-20 8.9-20 20-20z"
        fill="currentColor"
      />
      <circle cx="22" cy="26" r="3" fill="currentColor" />
      <circle cx="42" cy="26" r="3" fill="currentColor" />
      <path
        d="M20 38c0-6.6 5.4-12 12-12s12 5.4 12 12"
        stroke="currentColor"
        strokeWidth="3"
        fill="none"
      />
      <path d="M16 16l6 6M48 16l-6 6" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div>
      <section className="bg-background flex flex-col items-center justify-center text-center">
        <WelcomeImage />

        <h1 className="mb-1 text-4xl font-extrabold text-purple-600">🎭 Improv Battle</h1>
        <p className="mb-2 font-mono text-xs tracking-widest text-purple-500 uppercase">
          Voice Improv Game Show
        </p>

        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-base leading-6">
          Act out hilarious scenarios, get live feedback from your AI host!
        </p>

        <div className="mt-6 grid max-w-lg grid-cols-2 gap-3 text-sm">
          <div className="flex flex-col items-center gap-2 rounded-lg bg-purple-50 p-4 dark:bg-purple-900/20">
            <span className="text-3xl">🎬</span>
            <p className="font-semibold">3 Scenarios</p>
            <p className="text-muted-foreground text-xs">Wild improv challenges</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-pink-50 p-4 dark:bg-pink-900/20">
            <span className="text-3xl">🎤</span>
            <p className="font-semibold">Live Feedback</p>
            <p className="text-muted-foreground text-xs">Honest, witty reactions</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <span className="text-3xl">😂</span>
            <p className="font-semibold">No Scripts</p>
            <p className="text-muted-foreground text-xs">Pure improvisation</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-orange-50 p-4 dark:bg-orange-900/20">
            <span className="text-3xl">⭐</span>
            <p className="font-semibold">Your Style</p>
            <p className="text-muted-foreground text-xs">Get your improv summary</p>
          </div>
        </div>

        <Button
          variant="primary"
          size="lg"
          onClick={onStartCall}
          className="mt-8 w-64 bg-purple-600 font-mono hover:bg-purple-700"
        >
          {startButtonText || '🎭 START IMPROV BATTLE'}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-xs leading-5 font-normal">
          🎭 Day 10: Improv Battle • Powered by Murf Falcon TTS
        </p>
      </div>
    </div>
  );
};
