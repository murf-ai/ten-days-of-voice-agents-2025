import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="text-fg0 mb-4 size-16"
    >
      <path
        d="M32 8C20.954 8 12 16.954 12 28v8c0 11.046 8.954 20 20 20s20-8.954 20-20v-8c0-11.046-8.954-20-20-20zm0 4c8.837 0 16 7.163 16 16v8c0 8.837-7.163 16-16 16s-16-7.163-16-16v-8c0-8.837 7.163-16 16-16zm-6 12c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm12 0c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z"
        fill="currentColor"
      />
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

        <h1 className="text-foreground mb-2 text-2xl font-bold">Teach-the-Tutor</h1>

        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-base leading-6">
          Active Recall Coach - Learn by Teaching
        </p>

        <div className="mt-4 max-w-md space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-lg">📚</span>
            <span>Learn Mode - I explain concepts</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">❓</span>
            <span>Quiz Mode - I test your knowledge</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">🎓</span>
            <span>Teach Back - You explain to me</span>
          </div>
        </div>

        <Button variant="primary" size="lg" onClick={onStartCall} className="mt-6 w-64 font-mono">
          {startButtonText || 'START LEARNING'}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-xs leading-5 font-normal text-pretty md:text-sm">
          Powered by LiveKit Agents and Murf AI
        </p>
      </div>
    </div>
  );
};
