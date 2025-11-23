// hooks/useOrderReceiver.ts
// This hook listens for order data from the LiveKit agent via text streams

import { useEffect, useState, useRef } from 'react';
import { useRoomContext } from '@livekit/components-react';

export interface CoffeeOrder {
  drinkType: string;
  size: string;
  milk: string;
  extras: string[];
  name: string;
}

export function useOrderReceiver() {
  const [order, setOrder] = useState<CoffeeOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const room = useRoomContext();
  const hasRegistered = useRef(false);

  useEffect(() => {
    if (!room || hasRegistered.current) return;

    console.log('Registering text stream handler for coffee-order');

    // Register handler for "coffee-order" topic
    room.registerTextStreamHandler('coffee-order', async (reader, participantInfo) => {
      try {
        const info = reader.info;
        console.log(
          `Received text stream from ${participantInfo.identity}\n` +
          `  Topic: ${info.topic}\n` +
          `  Timestamp: ${info.timestamp}\n` +
          `  ID: ${info.id}\n` +
          `  Size: ${info.size}`
        );
        
        // Option 2: Get the entire text after the stream completes
        const orderText = await reader.readAll();
        console.log('Raw order data:', orderText);
        
        // Parse the JSON order data
        const orderData = JSON.parse(orderText) as CoffeeOrder;
        
        // Update state with the new order
        setOrder(orderData);
        setError(null);
        
        console.log('Order received and parsed:', orderData);
      } catch (err) {
        console.error('Error processing order:', err);
        setError(err instanceof Error ? err.message : 'Failed to process order');
      }
    });

    hasRegistered.current = true;

    
  }, [room]);

  return { order, error };
}