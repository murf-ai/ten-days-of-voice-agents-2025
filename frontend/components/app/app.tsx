'use client';

import { RoomAudioRenderer, StartAudio, useConnectionState } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { ConnectionState } from 'livekit-client';
import { OrderDisplay } from './OrderDisplay';


interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
 // const connectionState = useConnectionState();
 // const isConnected = connectionState === ConnectionState.Connected;
  return (
    <SessionProvider appConfig={appConfig}>
      <main className="grid h-svh grid-cols-1 place-content-center">
        <ViewController />
        
         
          {/* <div className="fixed bottom-0 left-0 right-0 max-h-50 overflow-y-auto">
          <OrderDisplay />
        </div> */}
        
      </main>
      <StartAudio label="Start Audio" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}
