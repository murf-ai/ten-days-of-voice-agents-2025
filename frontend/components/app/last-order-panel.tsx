'use client';

import { useEffect, useState } from 'react';
import { motion } from 'motion/react';

interface Order {
  order_id: string;
  customer: string;
  timestamp: string;
  total: number;
  currency: string;
  items: Array<{
    id: string;
    name: string;
    price: number;
    quantity: number;
    size?: string;
  }>;
  status: string;
}

interface LastOrderPanelProps {
  className?: string;
}

export function LastOrderPanel({ className }: LastOrderPanelProps) {
  const [lastOrder, setLastOrder] = useState<Order | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Fetch last order from backend API
    const checkLastOrder = async () => {
      try {
        const response = await fetch('/api/orders');
        if (response.ok) {
          const orders = await response.json();
          if (orders && orders.length > 0) {
            const latest = orders[orders.length - 1];
            setLastOrder(latest);
            setIsVisible(true);
          }
        }
      } catch (error) {
        console.error('Failed to fetch last order:', error);
      }
    };

    // Check every 3 seconds for new orders
    const interval = setInterval(checkLastOrder, 3000);
    checkLastOrder();

    return () => clearInterval(interval);
  }, []);

  // This component can be enhanced to listen to chat messages
  // and extract order information when the agent mentions it

  if (!lastOrder && !isVisible) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className={`bg-muted/50 border-border rounded-lg border p-4 ${className || ''}`}
    >
      <h3 className="text-sm font-semibold mb-2">Last Order Summary</h3>
      {lastOrder ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Order ID:</span>
            <span className="font-mono text-xs">{lastOrder.order_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total:</span>
            <span className="font-semibold">
              ₹{lastOrder.total.toFixed(2)} {lastOrder.currency}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Status:</span>
            <span className="capitalize">{lastOrder.status}</span>
          </div>
          <div className="mt-2 pt-2 border-t border-border">
            <div className="text-muted-foreground text-xs mb-1">Items:</div>
            <ul className="space-y-1">
              {lastOrder.items.map((item, idx) => (
                <li key={idx} className="text-xs">
                  {item.quantity}x {item.name}
                  {item.size && ` (${item.size})`} - ₹{item.price.toFixed(2)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No orders yet</p>
      )}
    </motion.div>
  );
}


