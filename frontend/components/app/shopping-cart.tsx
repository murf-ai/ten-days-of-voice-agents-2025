'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useChatMessages } from '@/hooks/useChatMessages';
import type { ReceivedChatMessage } from '@livekit/components-react';
import { cn } from '@/lib/utils';

interface CartItem {
  id: string;
  name: string;
  price: number;
  quantity: number;
  size?: string;
}

interface ShoppingCartProps {
  className?: string;
}

export function ShoppingCart({ className }: ShoppingCartProps) {
  const messages = useChatMessages();
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const lastProcessedMessageId = useRef<string | null>(null);

  useEffect(() => {
    // Debug: Log all messages to see what we're receiving
    console.log('ShoppingCart: All messages:', messages.map(m => ({
      id: m.id,
      isLocal: m.from?.isLocal,
      message: m.message.substring(0, 100),
      timestamp: m.timestamp
    })));

    // Parse cart information from agent messages
    // Look for messages that contain cart information
    const agentMessages = messages.filter((msg) => {
      // Only process messages from the agent (not the user)
      // In LiveKit, agent messages have isLocal = false
      const isAgent = !msg.from?.isLocal;
      if (isAgent) {
        console.log('ShoppingCart: Found agent message:', msg.message.substring(0, 150));
      }
      return isAgent;
    });

    console.log('ShoppingCart: Agent messages count:', agentMessages.length);

    // Find the most recent message that contains cart information
    // Process all cart-related messages to catch updates
    let latestCartMessage: ReceivedChatMessage | null = null;
    let latestCartMessageText = '';
    
    for (let i = agentMessages.length - 1; i >= 0; i--) {
      const msg = agentMessages[i];
      const text = msg.message.toLowerCase();
      const hasCartInfo = 
        text.includes('your cart:') ||
        (text.includes('cart') && (text.includes('added') || text.includes('updated') || text.includes('total'))) ||
        text.includes('added') ||
        text.includes('updated') ||
        (text.includes('quantity') && text.includes('₹'));
      
      if (hasCartInfo) {
        console.log('ShoppingCart: Found cart-related message:', msg.message.substring(0, 200));
        // If this message has "Your cart:" it's likely the most complete cart state
        if (text.includes('your cart:')) {
          latestCartMessage = msg;
          latestCartMessageText = msg.message;
          console.log('ShoppingCart: Using message with "Your cart:"');
          break; // This is the definitive cart message
        } else if (!latestCartMessage) {
          // Otherwise, keep the most recent one
          latestCartMessage = msg;
          latestCartMessageText = msg.message;
          console.log('ShoppingCart: Using first cart-related message found');
        }
      }
    }

    // Process the latest cart message (even if it's the same ID, in case it's been updated/streamed)
    if (latestCartMessage && latestCartMessageText) {
      const text = latestCartMessageText;
      const messageKey = `${latestCartMessage.id}-${text.length}`; // Include length to detect updates
      const isNewOrUpdated = messageKey !== lastProcessedMessageId.current;
      
      console.log('ShoppingCart: Message processing check:', {
        hasMessage: !!latestCartMessage,
        messageKey,
        lastKey: lastProcessedMessageId.current,
        isNewOrUpdated,
        fullText: text
      });
      
      // Always process if it's new, or if the text has changed (streaming update)
      const lastLength = lastProcessedMessageId.current ? parseInt(lastProcessedMessageId.current.split('-')[1] || '0') : 0;
      if (isNewOrUpdated || text.length > lastLength) {
        lastProcessedMessageId.current = messageKey;
        
        // Debug logging
        console.log('ShoppingCart: Processing cart message:', { 
          id: latestCartMessage.id, 
          length: text.length,
          fullText: text
        });

      // Try multiple patterns to extract cart items
      const items: CartItem[] = [];
      let match;
      
      // Pattern 1: "Your cart:" section with lines like "- quantity x name @ ₹price = ₹total"
      if (text.includes('your cart:') || text.includes('Your cart:')) {
        // Extract the cart section - everything after "Your cart:" until "Total:"
        const cartMatch = text.match(/your cart:\s*\n?(.*?)(?:\n\s*Total:|$)/is);
        const cartSection = cartMatch ? cartMatch[1] : text.split(/your cart:/i)[1] || '';
        
        // Match lines like: "- 2 x Product Name @ ₹100.00 = ₹200.00"
        // Also handle lines without the equals sign: "- 2 x Product Name @ ₹100.00"
        // Handle both with and without size info
        const linePattern = /[-•]\s*(\d+)\s+x\s+([^@\n]+?)\s+@\s+₹([\d.]+)(?:\s*=\s*₹[\d.]+)?/g;
        while ((match = linePattern.exec(cartSection)) !== null) {
          const quantity = parseInt(match[1]);
          let name = match[2].trim();
          // Remove size info if present: "Product Name (Size: M)"
          const sizeMatch = name.match(/^(.+?)\s*\(Size:\s*([^)]+)\)$/);
          let size: string | undefined;
          if (sizeMatch) {
            name = sizeMatch[1].trim();
            size = sizeMatch[2].trim();
          }
          const price = parseFloat(match[3]);
          const productId = name.toLowerCase().replace(/\s+/g, '-').substring(0, 30);

          items.push({
            id: productId,
            name,
            price,
            quantity,
            size,
          });
        }
        
        console.log('ShoppingCart: Parsed items from cart section:', items);
      }
      
      // If we still don't have items but the message contains "Your cart:", try a more lenient pattern
      if (items.length === 0 && (text.includes('your cart:') || text.includes('Your cart:'))) {
        console.log('ShoppingCart: Trying alternative parsing for cart section');
        // Try to extract all lines that look like cart items
        const lines = text.split('\n');
        for (const line of lines) {
          // Match: "- 1 x Product Name @ ₹100.00 = ₹100.00"
          const match = line.match(/[-•]\s*(\d+)\s+x\s+(.+?)\s+@\s+₹([\d.]+)/);
          if (match) {
            const quantity = parseInt(match[1]);
            let name = match[2].trim();
            const sizeMatch = name.match(/^(.+?)\s*\(Size:\s*([^)]+)\)$/);
            let size: string | undefined;
            if (sizeMatch) {
              name = sizeMatch[1].trim();
              size = sizeMatch[2].trim();
            }
            const price = parseFloat(match[3]);
            const productId = name.toLowerCase().replace(/\s+/g, '-').substring(0, 30);
            
            items.push({
              id: productId,
              name,
              price,
              quantity,
              size,
            });
          }
        }
        console.log('ShoppingCart: Alternative parsing found items:', items);
      }

      // Pattern 2: "Added quantity x name to your cart. Cart total: ₹total"
      if (items.length === 0) {
        const addPattern = /added\s+(\d+)\s+x\s+([^.]+?)(?:\s+to\s+your\s+cart|\.)/gi;
        const allAddMatches: Array<{quantity: number; name: string}> = [];
        while ((match = addPattern.exec(text)) !== null) {
          allAddMatches.push({
            quantity: parseInt(match[1]),
            name: match[2].trim(),
          });
        }
        
        // Also look for "Updated" messages
        const updatePattern = /updated\s+['"]([^'"]+)['"]\s+quantity\s+to\s+(\d+)/gi;
        while ((match = updatePattern.exec(text)) !== null) {
          allAddMatches.push({
            quantity: parseInt(match[2]),
            name: match[1].trim(),
          });
        }

        // For added items, we need to fetch prices from products API
        if (allAddMatches.length > 0) {
          // Store items temporarily - we'll fetch prices separately
          allAddMatches.forEach(({ quantity, name }) => {
            const productId = name.toLowerCase().replace(/\s+/g, '-').substring(0, 30);
            items.push({
              id: productId,
              name,
              price: 0, // Will be updated when we fetch from API
              quantity,
            });
          });
        }
      }

      // Pattern 3: Direct format "quantity x name @ ₹price = ₹total" (without "Your cart:")
      if (items.length === 0) {
        const directPattern = /(\d+)\s+x\s+([^@]+?)\s+@\s+₹([\d.]+)\s*=\s*₹([\d.]+)/g;
        while ((match = directPattern.exec(text)) !== null) {
          const quantity = parseInt(match[1]);
          let name = match[2].trim();
          const sizeMatch = name.match(/^(.+?)\s*\(Size:\s*([^)]+)\)$/);
          let size: string | undefined;
          if (sizeMatch) {
            name = sizeMatch[1].trim();
            size = sizeMatch[2].trim();
          }
          const price = parseFloat(match[3]);
          const productId = name.toLowerCase().replace(/\s+/g, '-').substring(0, 30);

          items.push({
            id: productId,
            name,
            price,
            quantity,
            size,
          });
        }
      }

      if (items.length > 0) {
        console.log('ShoppingCart: ✅ Successfully parsed items:', items);
        // If any items have price 0, try to fetch from products API
        const itemsNeedingPrice = items.filter(item => item.price === 0);
        if (itemsNeedingPrice.length > 0) {
          fetch('/api/products')
            .then(res => res.json())
            .then(products => {
              const updatedItems = items.map(item => {
                if (item.price === 0) {
                  const product = products.find((p: any) => 
                    p.name.toLowerCase() === item.name.toLowerCase() ||
                    p.id.toLowerCase() === item.id.toLowerCase()
                  );
                  if (product) {
                    return { ...item, price: product.price };
                  }
                }
                return item;
              });
              console.log('ShoppingCart: Setting cart items with prices:', updatedItems);
              setCartItems(updatedItems);
            })
            .catch((err) => {
              console.error('ShoppingCart: Error fetching products:', err);
              setCartItems(items); // Fallback to items without prices
            });
        } else {
          console.log('ShoppingCart: Setting cart items directly:', items);
          setCartItems(items);
        }
      } else if (text.toLowerCase().includes('cart is empty') || text.toLowerCase().includes('empty')) {
        console.log('ShoppingCart: Cart is empty - clearing items');
        setCartItems([]);
      } else {
        // If no items parsed but message contains cart info, log for debugging
        console.warn('ShoppingCart: ⚠️ No items parsed from message!', {
          messageText: text,
          hasYourCart: text.includes('your cart:'),
          hasAdded: text.includes('added'),
          hasUpdated: text.includes('updated'),
          hasQuantity: text.includes('quantity'),
          hasRupee: text.includes('₹')
        });
        // Don't clear existing cart - keep what we have
      }
      } // Close if (isNewOrUpdated)
    } // Close if (latestCartMessage && latestCartMessageText)
  }, [messages]);

  const total = cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);

  return (
    <div
      className={cn(
        'bg-muted/50 border-border rounded-lg border p-4 h-full flex flex-col',
        className
      )}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold mb-1">BUILT WITH LIVEKIT AGENTS</h3>
        <p className="text-xs text-muted-foreground mb-2">VOICE_INTERFACE_ACTIVE</p>
        <h2 className="text-lg font-semibold">Your Cart</h2>
        <p className="text-xs text-muted-foreground">
          ({cartItems.length} {cartItems.length === 1 ? 'item' : 'items'})
        </p>
      </div>

      {cartItems.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-muted-foreground text-center">
            Your cart is empty.
            <br />
            <span className="text-xs">Say "Add [product] to cart" to shop!</span>
          </p>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto space-y-3 mb-4">
            {cartItems.map((item, idx) => (
              <div key={`${item.id}-${idx}`} className="text-sm">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-medium">{item.name}</span>
                  <span className="text-muted-foreground">
                    Qty: {item.quantity} x ₹{item.price.toLocaleString()}
                  </span>
                </div>
                {item.size && (
                  <p className="text-xs text-muted-foreground">Size: {item.size}</p>
                )}
                <p className="text-xs font-semibold mt-1">
                  ₹{(item.price * item.quantity).toLocaleString()}
                </p>
              </div>
            ))}
          </div>

          <div className="border-t border-border pt-3">
            <div className="flex justify-between items-center mb-2">
              <span className="font-semibold">Total</span>
              <span className="font-bold text-lg">₹{total.toLocaleString()}</span>
            </div>
            <p className="text-xs text-muted-foreground text-center mt-2">
              Say 'Checkout' to place order
            </p>
          </div>
        </>
      )}
    </div>
  );
}

