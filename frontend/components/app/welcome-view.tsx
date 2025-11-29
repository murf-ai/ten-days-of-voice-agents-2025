import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-4 size-16 text-red-600"
    >
      <path
        d="M32 4L28 16L16 20L28 24L32 36L36 24L48 20L36 16L32 4ZM20 28L18 32L14 34L18 36L20 40L22 36L26 34L22 32L20 28ZM44 32L42 36L38 38L42 40L44 44L46 40L50 38L46 36L44 32ZM32 44C24 44 18 48 18 56V62H46V56C46 48 40 44 32 44Z"
        fill="currentColor"
      />
      <circle cx="32" cy="8" r="3" fill="currentColor" />
      <circle cx="16" cy="20" r="2" fill="currentColor" />
      <circle cx="48" cy="20" r="2" fill="currentColor" />
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

        <h1 className="mb-1 text-4xl font-extrabold text-red-600">Hero Academy</h1>
        <p className="mb-2 font-mono text-xs tracking-widest text-red-500 uppercase">
          Voice Adventure RPG
        </p>

        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-base leading-6">
          Become a hero with quirk powers in an anime-style adventure
        </p>

        <div className="mt-6 max-w-lg space-y-3">
          <div className="flex items-start gap-3 rounded-lg border-2 border-red-500/30 bg-red-50 p-4 dark:bg-red-900/20">
            <span className="text-3xl">⚡</span>
            <div className="text-left">
              <p className="font-bold text-red-600">Your Quirk Power</p>
              <p className="text-muted-foreground text-xs">
                Lightning Strike - Channel electricity through your body for devastating attacks!
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
            <span className="text-2xl">🎯</span>
            <div className="text-left">
              <p className="text-sm font-semibold">Your Mission</p>
              <p className="text-muted-foreground text-xs">
                Defeat the Shadow Demon terrorizing the village
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-lg bg-purple-50 p-2 dark:bg-purple-900/20">
              <div className="font-bold">💚 Health</div>
              <div className="text-muted-foreground">100/100</div>
            </div>
            <div className="rounded-lg bg-yellow-50 p-2 dark:bg-yellow-900/20">
              <div className="font-bold">⚡ Energy</div>
              <div className="text-muted-foreground">100/100</div>
            </div>
            <div className="rounded-lg bg-green-50 p-2 dark:bg-green-900/20">
              <div className="font-bold">🎲 Dice</div>
              <div className="text-muted-foreground">d20 System</div>
            </div>
          </div>
        </div>

        <Button
          variant="primary"
          size="lg"
          onClick={onStartCall}
          className="mt-8 w-72 bg-gradient-to-r from-red-600 to-orange-600 font-mono text-base font-bold hover:from-red-700 hover:to-orange-700"
        >
          {startButtonText || '🎌 BEGIN ADVENTURE'}
        </Button>

        <p className="text-muted-foreground mt-4 text-xs italic">
          "The path of a hero is never easy, but it's always worth it!"
        </p>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-xs leading-5 font-normal">
          🎮 Anime Voice RPG • Powered by Murf Falcon TTS
        </p>
      </div>
    </div>
  );
};
