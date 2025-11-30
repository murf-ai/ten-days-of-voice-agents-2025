'use client';

import React from 'react';
import { GameMaster } from '@/components/app/game-master';

export default function Day8GameMasterPage() {
  React.useEffect(() => {
    document.title = 'Day 8: Voice Game Master - Eldoria Adventure';
  }, []);

  return <GameMaster />;
}
