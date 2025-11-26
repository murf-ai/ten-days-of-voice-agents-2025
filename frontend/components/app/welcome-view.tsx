import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mb-4 size-16 text-blue-600"
    >
      <path
        d="M32 8C18.745 8 8 18.745 8 32s10.745 24 24 24 24-10.745 24-24S45.255 8 32 8zm0 4c11.028 0 20 8.972 20 20s-8.972 20-20 20-20-8.972-20-20 8.972-20 20-20zm-2 8v16l12 6-2 4-14-7V20h4z"
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

        <h1 className="text-foreground mb-2 text-3xl font-bold text-blue-600">
          Razorpay AI Assistant
        </h1>

        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-base leading-6">
          Get instant answers about our payment solutions
        </p>

        <div className="mt-6 max-w-md space-y-3 text-sm">
          <div className="flex items-center gap-3 text-left">
            <span className="text-2xl">💳</span>
            <div>
              <p className="font-semibold">Ask about our services</p>
              <p className="text-muted-foreground text-xs">Pricing, integration, payment methods</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-left">
            <span className="text-2xl">⚡</span>
            <div>
              <p className="font-semibold">Get started quickly</p>
              <p className="text-muted-foreground text-xs">Connect with our sales team</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-left">
            <span className="text-2xl">🔒</span>
            <div>
              <p className="font-semibold">Secure & compliant</p>
              <p className="text-muted-foreground text-xs">PCI DSS Level 1 certified</p>
            </div>
          </div>
        </div>

        <Button
          variant="primary"
          size="lg"
          onClick={onStartCall}
          className="mt-8 w-64 bg-blue-600 font-mono hover:bg-blue-700"
        >
          {startButtonText || 'TALK TO AI ASSISTANT'}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose px-4 pt-1 text-xs leading-5 font-normal text-pretty">
          Powered by Murf Falcon (Fastest TTS API) & LiveKit Agents
        </p>
      </div>
    </div>
  );
};
