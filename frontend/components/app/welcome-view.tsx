import { ShoppingCart, Microphone, Lightning } from '@phosphor-icons/react';
import { Button } from '@/components/livekit/button';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ...props
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div {...props} className="flex flex-col items-center justify-center w-full max-w-lg mx-auto">
      {/* Main Card */}
      <div className="flex flex-col items-center text-center space-y-6">
        {/* Icon */}
        <div className="w-24 h-24 bg-yellow-400 rounded-3xl flex items-center justify-center shadow-lg shadow-yellow-400/20 mb-2">
          <ShoppingCart size={48} weight="fill" className="text-slate-950" />
        </div>

        {/* Title */}
        <div className="space-y-2">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-white">
            blinkit <span className="text-yellow-400">express</span>
          </h2>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-400/10 border border-yellow-400/20 text-yellow-400 text-sm font-bold uppercase tracking-wider">
            <Lightning weight="fill" />
            Delivery in 8 minutes
          </div>
        </div>

        {/* Description */}
        <div className="space-y-4 max-w-md">
          <p className="text-lg text-slate-200 font-medium">
            Everything you need, delivered in minutes.
          </p>
          <p className="text-sm text-slate-400 leading-relaxed">
            Just ask for groceries, snacks, or household items. Our AI assistant will build your cart instantly.
          </p>
        </div>

        {/* Start Button */}
        <Button
          variant="primary"
          size="lg"
          onClick={onStartCall}
          className="mt-4 w-full sm:w-auto min-w-[200px] h-14 text-lg font-bold bg-yellow-400 hover:bg-yellow-500 text-slate-950 border-none shadow-lg shadow-yellow-400/20 transition-all hover:scale-105"
        >
          <Microphone size={24} weight="fill" className="mr-2" />
          {startButtonText}
        </Button>
      </div>

      {/* Try saying hint */}
      <div className="mt-12 px-6 py-3 bg-slate-800/50 border border-white/10 rounded-full text-slate-300 text-sm animate-pulse flex items-center gap-2">
        <span className="text-yellow-400">💡 Try saying:</span> "I need milk, bread, and eggs"
      </div>
    </div>
  );
};

function SparkleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M9.9 2.5L11.6 7.6C11.7 8 12 8.3 12.4 8.4L17.5 10.1C18.2 10.3 18.2 11.3 17.5 11.5L12.4 13.2C12 13.3 11.7 13.6 11.6 14L9.9 19.1C9.7 19.8 8.7 19.8 8.5 19.1L6.8 14C6.7 13.6 6.4 13.3 6 13.2L0.9 11.5C0.2 11.3 0.2 10.3 0.9 10.1L6 8.4C6.4 8.3 6.7 8 6.8 7.6L8.5 2.5C8.7 1.8 9.7 1.8 9.9 2.5Z" />
    </svg>
  );
}

function CubeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
    </svg>
  );
}
