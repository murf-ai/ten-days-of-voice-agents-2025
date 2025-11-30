import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-4 size-16 text-orange-600"
    >
      <path
        d="M32 8L24 16H16V48H48V16H40L32 8ZM32 12L36 16H28L32 12ZM20 20H44V44H20V20ZM26 26V38H38V26H26Z"
        fill="currentColor"
      />
      <circle cx="32" cy="32" r="4" fill="currentColor" />
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

        <h1 className="mb-1 text-4xl font-extrabold text-orange-600">Urban Drip India</h1>
        <p className="mb-2 font-mono text-xs tracking-widest text-orange-500 uppercase">
          Voice Commerce Experience
        </p>

        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-base leading-6">
          Shop Indian streetwear with your voice
        </p>

        <div className="mt-6 grid max-w-lg grid-cols-2 gap-3 text-sm">
          <div className="flex flex-col items-center gap-2 rounded-lg bg-orange-50 p-4 dark:bg-orange-900/20">
            <span className="text-3xl">👕</span>
            <p className="font-semibold">10+ Products</p>
            <p className="text-muted-foreground text-xs">Hoodies, Tees, Accessories</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <span className="text-3xl">🛒</span>
            <p className="font-semibold">Smart Cart</p>
            <p className="text-muted-foreground text-xs">Add, remove, checkout</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
            <span className="text-3xl">💳</span>
            <p className="font-semibold">ACP Protocol</p>
            <p className="text-muted-foreground text-xs">Structured commerce</p>
          </div>
          <div className="flex flex-col items-center gap-2 rounded-lg bg-purple-50 p-4 dark:bg-purple-900/20">
            <span className="text-3xl">🗣️</span>
            <p className="font-semibold">Voice Shopping</p>
            <p className="text-muted-foreground text-xs">Just speak your order</p>
          </div>
        </div>

        <Button
          variant="primary"
          size="lg"
          onClick={onStartCall}
          className="mt-8 w-64 bg-orange-600 font-mono hover:bg-orange-700"
        >
          {startButtonText || '🛍️ START SHOPPING'}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-xs leading-5 font-normal">
          🛍️ ACP-Inspired Commerce • Powered by Murf Falcon TTS
        </p>
      </div>
    </div>
  );
};
