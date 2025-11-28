import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-4 size-16 text-green-600"
    >
      <path
        d="M16 8L12 16V56C12 58.21 13.79 60 16 60H48C50.21 60 52 58.21 52 56V16L48 8H16ZM18 12H46L48 16H16L18 12ZM16 20H48V56H16V20ZM24 28V32H40V28H24ZM24 36V40H40V36H24ZM24 44V48H32V44H24Z"
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

        <h1 className="text-foreground mb-2 text-3xl font-bold text-green-600">
          QuickMart Express
        </h1>

        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-base leading-6">
          Voice-powered grocery & food ordering
        </p>

        <div className="mt-6 grid max-w-md grid-cols-2 gap-4 text-sm">
          <div className="flex flex-col items-center gap-2 rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
            <span className="text-3xl">🛒</span>
            <p className="font-semibold">Smart Cart</p>
            <p className="text-muted-foreground text-xs">Add, remove, update items</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <span className="text-3xl">🍳</span>
            <p className="font-semibold">Recipe Mode</p>
            <p className="text-muted-foreground text-xs">"Ingredients for pasta"</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-orange-50 p-4 dark:bg-orange-900/20">
            <span className="text-3xl">⚡</span>
            <p className="font-semibold">Quick Search</p>
            <p className="text-muted-foreground text-xs">30+ products available</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-purple-50 p-4 dark:bg-purple-900/20">
            <span className="text-3xl">🚚</span>
            <p className="font-semibold">Fast Delivery</p>
            <p className="text-muted-foreground text-xs">30 min delivery</p>
          </div>
        </div>

        <Button 
          variant="primary" 
          size="lg" 
          onClick={onStartCall} 
          className="mt-8 w-64 bg-green-600 font-mono hover:bg-green-700"
        >
          {startButtonText || "START SHOPPING"}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-xs leading-5 font-normal">
          Powered by Murf Falcon TTS & LiveKit Agents
        </p>
      </div>
    </div>
  );
};