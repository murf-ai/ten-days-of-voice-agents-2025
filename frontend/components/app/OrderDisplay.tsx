// components/OrderDisplay.tsx
// Displays the coffee order with visual drink representation

import React from 'react';
import { useOrderReceiver, CoffeeOrder } from '@/hooks/useOrderReceiver';

interface CoffeeCupProps {
  order: CoffeeOrder;
}

const CoffeeCup: React.FC<CoffeeCupProps> = ({ order }) => {
  // Size mappings
  const sizeConfig = {
    small: { height: 120, width: 80 },
    medium: { height: 160, width: 100 },
    large: { height: 200, width: 120 }
  };

  const size = sizeConfig[order.size?.toLowerCase() as keyof typeof sizeConfig] || sizeConfig.medium;

  // Milk color mappings
  const milkColors: Record<string, string> = {
    'whole milk': '#F5DEB3',
    'oat milk': '#E8D5C4',
    'almond milk': '#F0E6D2',
    'soy milk': '#F5E6D3',
    'no milk': '#3E2723'
  };

  const coffeeColor = milkColors[order.milk?.toLowerCase()] || '#8B4513';

  // Check if order has whipped cream
  const hasWhippedCream = order.extras?.some(extra => 
    extra.toLowerCase().includes('whipped cream')
  );

  return (
    <div className="flex flex-col items-center gap-5 p-10 bg-gradient-to-br from-purple-600 to-purple-800 rounded-3xl shadow-2xl">
      <h2 className="text-white text-2xl font-bold">
        Your {order.size} {order.drinkType}
      </h2>

      {/* Coffee Cup SVG */}
      <div className="relative">
        <svg 
          width={size.width + 60} 
          height={size.height + 80} 
          viewBox={`0 0 ${size.width + 60} ${size.height + 80}`}
        >
          {/* Cup Body */}
          <path
            d={`M 20 30 
                L 10 ${size.height + 20}
                Q 10 ${size.height + 30} 20 ${size.height + 30}
                L ${size.width + 40} ${size.height + 30}
                Q ${size.width + 50} ${size.height + 30} ${size.width + 50} ${size.height + 20}
                L ${size.width + 40} 30
                Z`}
            fill="white"
            stroke="#333"
            strokeWidth="2"
          />
          
          {/* Coffee Liquid */}
          <path
            d={`M 22 50
                L 12 ${size.height + 15}
                Q 12 ${size.height + 25} 22 ${size.height + 25}
                L ${size.width + 38} ${size.height + 25}
                Q ${size.width + 48} ${size.height + 25} ${size.width + 48} ${size.height + 15}
                L ${size.width + 38} 50
                Z`}
            fill={coffeeColor}
            opacity="0.9"
          />

          {/* Whipped Cream */}
          {hasWhippedCream && (
            <>
              <ellipse
                cx={size.width / 2 + 30}
                cy={45}
                rx={size.width / 2.5}
                ry={15}
                fill="#FFFACD"
                stroke="#F5DEB3"
                strokeWidth="1"
              />
              <ellipse
                cx={size.width / 2 + 25}
                cy={35}
                rx={size.width / 3}
                ry={12}
                fill="#FFFDD0"
                stroke="#F5DEB3"
                strokeWidth="1"
              />
              <ellipse
                cx={size.width / 2 + 35}
                cy={32}
                rx={size.width / 3.5}
                ry={10}
                fill="#FFFEF0"
                stroke="#F5DEB3"
                strokeWidth="1"
              />
            </>
          )}

          {/* Cup Handle */}
          <path
            d={`M ${size.width + 50} 60
                Q ${size.width + 70} 60 ${size.width + 70} 80
                Q ${size.width + 70} 100 ${size.width + 50} 100`}
            fill="none"
            stroke="#333"
            strokeWidth="3"
            strokeLinecap="round"
          />

          {/* Steam Animation */}
          <g opacity="0.6">
            <path
              d={`M ${size.width / 2 + 15} 25 Q ${size.width / 2 + 10} 15 ${size.width / 2 + 15} 5`}
              fill="none"
              stroke="#AAA"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <animate
                attributeName="opacity"
                values="0.6;0.2;0.6"
                dur="2s"
                repeatCount="indefinite"
              />
            </path>
            <path
              d={`M ${size.width / 2 + 30} 25 Q ${size.width / 2 + 35} 15 ${size.width / 2 + 30} 5`}
              fill="none"
              stroke="#AAA"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <animate
                attributeName="opacity"
                values="0.4;0.8;0.4"
                dur="2.5s"
                repeatCount="indefinite"
              />
            </path>
            <path
              d={`M ${size.width / 2 + 45} 25 Q ${size.width / 2 + 50} 15 ${size.width / 2 + 45} 5`}
              fill="none"
              stroke="#AAA"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <animate
                attributeName="opacity"
                values="0.5;0.3;0.5"
                dur="3s"
                repeatCount="indefinite"
              />
            </path>
          </g>
        </svg>
      </div>

      {/* Order Details Card */}
      <div className="bg-white/90 p-5 rounded-xl w-full max-w-sm">
        <div className="flex flex-col gap-2 text-sm text-gray-800">
          <div className="flex justify-between">
            <span className="font-bold">Drink:</span>
            <span>{order.drinkType}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-bold">Size:</span>
            <span className="capitalize">{order.size}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-bold">Milk:</span>
            <span>{order.milk}</span>
          </div>
          {order.extras && order.extras.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-300">
              <span className="font-bold">Extras:</span>
              <ul className="mt-1 pl-5 list-disc">
                {order.extras.map((extra, i) => (
                  <li key={i}>{extra}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-3 pt-3 border-t-2 border-purple-600 text-center">
            <span className="font-bold text-base text-purple-600">
              For: {order.name}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export const OrderDisplay: React.FC = () => {
  const { order, error } = useOrderReceiver();

  if (error) {
    return (
      <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
        <p className="font-bold">Error receiving order:</p>
        <p>{error}</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-8">
        <div className="w-12 h-12 border-4 border-purple-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-600 text-lg">Waiting for your order...</p>
      </div>
    );
  }

  return <CoffeeCup order={order} />;
};