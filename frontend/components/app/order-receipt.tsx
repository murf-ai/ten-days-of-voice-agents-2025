'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useRoomContext } from '@livekit/components-react';
import type { DataPacket_Kind } from '@livekit/protocol';

interface OrderState {
  drinkType?: string;
  size?: string;
  milk?: string;
  extras?: string[];
  name?: string;
}

export function OrderReceipt() {
  const [order, setOrder] = useState<OrderState>({});
  const [isVisible, setIsVisible] = useState(false);
  const room = useRoomContext();

  useEffect(() => {
    const handleDataReceived = (
      payload: Uint8Array,
      participant?: any,
      kind?: DataPacket_Kind,
      topic?: string
    ) => {
      if (topic === 'order-updates') {
        try {
          const decoder = new TextDecoder();
          const orderData = JSON.parse(decoder.decode(payload));
          console.log('Received order data:', orderData);
          setOrder(orderData);
          setIsVisible(true);
        } catch (e) {
          console.error('Failed to parse order data:', e);
        }
      }
    };

    room.on('dataReceived', handleDataReceived);

    return () => {
      room.off('dataReceived', handleDataReceived);
    };
  }, [room]);

  const getCupSize = () => {
    switch (order.size?.toLowerCase()) {
      case 'small':
        return 'h-32';
      case 'medium':
        return 'h-40';
      case 'large':
        return 'h-48';
      default:
        return 'h-36';
    }
  };

  const hasWhippedCream = order.extras?.some(
    (extra) => extra.toLowerCase().includes('whipped') || extra.toLowerCase().includes('cream')
  );

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, x: 100 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 100 }}
          className="fixed right-4 top-4 z-50 w-80 rounded-lg bg-white p-6 shadow-2xl"
        >
          {/* Receipt Header */}
          <div className="mb-4 border-b-2 border-dashed border-gray-300 pb-4 text-center">
            <h2 className="text-2xl font-bold text-gray-800">☕ Starbucks</h2>
            <p className="text-sm text-gray-600">Order Receipt</p>
          </div>

          {/* Visual Cup */}
          <div className="mb-6 flex justify-center">
            <div className="relative">
              {/* Cup */}
              <div
                className={`${getCupSize()} w-24 rounded-b-lg bg-gradient-to-b from-amber-100 to-amber-200 border-4 border-amber-800 relative`}
              >
                {/* Coffee inside */}
                <div className="absolute bottom-0 left-0 right-0 h-3/4 rounded-b-lg bg-gradient-to-b from-amber-700 to-amber-900"></div>
              </div>
              
              {/* Whipped Cream */}
              {hasWhippedCream && (
                <div className="absolute -top-4 left-1/2 h-8 w-20 -translate-x-1/2 rounded-full bg-gradient-to-b from-white to-gray-100 shadow-md"></div>
              )}
              
              {/* Cup Lid */}
              <div className="absolute -top-2 left-1/2 h-3 w-28 -translate-x-1/2 rounded-full bg-gray-800"></div>
            </div>
          </div>

          {/* Order Details */}
          <div className="space-y-2 text-sm">
            {order.name && (
              <div className="flex justify-between border-b border-gray-200 pb-2">
                <span className="font-semibold text-gray-700">Name:</span>
                <span className="text-gray-900">{order.name}</span>
              </div>
            )}
            
            {order.drinkType && (
              <div className="flex justify-between border-b border-gray-200 pb-2">
                <span className="font-semibold text-gray-700">Drink:</span>
                <span className="text-gray-900 capitalize">{order.drinkType}</span>
              </div>
            )}
            
            {order.size && (
              <div className="flex justify-between border-b border-gray-200 pb-2">
                <span className="font-semibold text-gray-700">Size:</span>
                <span className="text-gray-900 capitalize">{order.size}</span>
              </div>
            )}
            
            {order.milk && (
              <div className="flex justify-between border-b border-gray-200 pb-2">
                <span className="font-semibold text-gray-700">Milk:</span>
                <span className="text-gray-900 capitalize">{order.milk}</span>
              </div>
            )}
            
            {order.extras && order.extras.length > 0 && (
              <div className="border-b border-gray-200 pb-2">
                <span className="font-semibold text-gray-700">Extras:</span>
                <ul className="ml-4 mt-1 list-disc text-gray-900">
                  {order.extras.map((extra, idx) => (
                    <li key={idx} className="capitalize">
                      {extra}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Receipt Footer */}
          <div className="mt-4 border-t-2 border-dashed border-gray-300 pt-4 text-center">
            <p className="text-xs text-gray-600">Thank you for your order!</p>
            <p className="text-xs text-gray-500">Powered by Murf Falcon TTS</p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
