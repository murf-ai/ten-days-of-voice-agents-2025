'use client';

import { RoomAudioRenderer, StartAudio } from '@livekit/components-react';
import { ShoppingCart, MagnifyingGlass, MapPin, CaretDown, Bicycle, Prescription, PawPrint, Baby, Sparkle } from '@phosphor-icons/react';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  return (
    <SessionProvider appConfig={appConfig}>
      <div className="min-h-screen bg-slate-950 text-white font-sans selection:bg-yellow-500/30">
        {/* Header */}
        <header className="border-b border-white/10 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
          <div className="container mx-auto px-4 h-20 flex items-center justify-between gap-8">
            {/* Logo & Location */}
            <div className="flex items-center gap-8">
              <div className="flex flex-col">
                <h1 className="font-extrabold text-2xl tracking-tight text-yellow-400 leading-none">blinkit</h1>
                <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">Express</span>
              </div>

              <div className="hidden lg:flex flex-col leading-tight border-l border-white/10 pl-6">
                <span className="font-bold text-sm flex items-center gap-1">
                  Delivery in 8 minutes
                  <Bicycle size={16} className="text-yellow-400" />
                </span>
                <span className="text-xs text-slate-400 flex items-center gap-1 cursor-pointer hover:text-white transition-colors">
                  Home - 123, Cyber City, Gurgaon <CaretDown size={12} />
                </span>
              </div>
            </div>

            {/* Search Bar */}
            <div className="hidden md:flex flex-1 max-w-2xl relative">
              <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                <MagnifyingGlass size={20} />
              </div>
              <input
                type="text"
                placeholder="Search 'milk'"
                className="w-full bg-slate-800/50 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-sm focus:outline-none focus:border-yellow-500/50 focus:ring-1 focus:ring-yellow-500/50 transition-all placeholder:text-slate-500"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-6">
              <button className="hidden sm:block text-sm font-medium hover:text-yellow-400 transition-colors">Login</button>
              <button className="flex items-center gap-2 bg-yellow-400 hover:bg-yellow-500 text-slate-950 px-5 py-2.5 rounded-xl transition-all font-bold text-sm shadow-lg shadow-yellow-400/20">
                <ShoppingCart size={20} weight="fill" />
                <span className="hidden sm:inline">My Cart</span>
              </button>
            </div>
          </div>
        </header>

        <main className="container mx-auto px-4 py-8 space-y-12">

          {/* Hero Section: Voice Agent */}
          <div className="relative rounded-3xl overflow-hidden bg-gradient-to-r from-yellow-500/10 via-slate-900 to-slate-900 border border-yellow-500/20 min-h-[500px] flex flex-col md:flex-row items-center">
            {/* Background Pattern */}
            <div className="absolute inset-0 opacity-30 bg-[radial-gradient(#fbbf24_1px,transparent_1px)] [background-size:16px_16px]" />

            <div className="relative z-10 w-full h-full flex flex-col items-center justify-center p-8">
              <div className="absolute top-6 left-6 flex items-center gap-2 px-3 py-1 bg-yellow-500/20 rounded-full border border-yellow-500/30">
                <Sparkle size={14} weight="fill" className="text-yellow-400" />
                <span className="text-xs font-bold text-yellow-400 uppercase tracking-wider">Voice Shopping Active</span>
              </div>
              <ViewController />
            </div>
          </div>

          {/* Feature Cards (Mocked from Image) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Pharmacy */}
            <div className="bg-teal-900/20 border border-teal-500/20 rounded-2xl p-6 flex flex-col justify-between h-48 hover:border-teal-500/40 transition-colors cursor-pointer group">
              <div>
                <h3 className="font-bold text-xl text-teal-100 mb-1">Pharmacy at your doorstep!</h3>
                <p className="text-sm text-teal-400/80">Cough syrups, pain relief & more</p>
              </div>
              <div className="flex justify-between items-end">
                <button className="bg-teal-500/20 text-teal-300 px-4 py-2 rounded-lg text-xs font-bold uppercase group-hover:bg-teal-500 group-hover:text-teal-950 transition-all">Order Now</button>
                <Prescription size={48} className="text-teal-500/20 group-hover:text-teal-500/40 transition-colors" weight="duotone" />
              </div>
            </div>

            {/* Pet Care */}
            <div className="bg-yellow-900/20 border border-yellow-500/20 rounded-2xl p-6 flex flex-col justify-between h-48 hover:border-yellow-500/40 transition-colors cursor-pointer group">
              <div>
                <h3 className="font-bold text-xl text-yellow-100 mb-1">Pet Care supplies in minutes</h3>
                <p className="text-sm text-yellow-400/80">Food, treats, toys & more</p>
              </div>
              <div className="flex justify-between items-end">
                <button className="bg-yellow-500/20 text-yellow-300 px-4 py-2 rounded-lg text-xs font-bold uppercase group-hover:bg-yellow-500 group-hover:text-yellow-950 transition-all">Order Now</button>
                <PawPrint size={48} className="text-yellow-500/20 group-hover:text-yellow-500/40 transition-colors" weight="duotone" />
              </div>
            </div>

            {/* Baby Care */}
            <div className="bg-indigo-900/20 border border-indigo-500/20 rounded-2xl p-6 flex flex-col justify-between h-48 hover:border-indigo-500/40 transition-colors cursor-pointer group">
              <div>
                <h3 className="font-bold text-xl text-indigo-100 mb-1">No time for a diaper run?</h3>
                <p className="text-sm text-indigo-400/80">Get baby care essentials in minutes</p>
              </div>
              <div className="flex justify-between items-end">
                <button className="bg-indigo-500/20 text-indigo-300 px-4 py-2 rounded-lg text-xs font-bold uppercase group-hover:bg-indigo-500 group-hover:text-indigo-950 transition-all">Order Now</button>
                <Baby size={48} className="text-indigo-500/20 group-hover:text-indigo-500/40 transition-colors" weight="duotone" />
              </div>
            </div>
          </div>

          {/* Quick Categories */}
          <div>
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
              <span className="w-1 h-6 bg-yellow-400 rounded-full" />
              Shop by Category
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-4">
              {['Vegetables', 'Fruits', 'Dairy', 'Bakery', 'Snacks', 'Drinks', 'Instant Food', 'Tea & Coffee'].map((cat, i) => (
                <div key={cat} className="bg-slate-900 border border-white/5 hover:border-yellow-500/50 rounded-xl p-4 flex flex-col items-center gap-3 cursor-pointer transition-all hover:-translate-y-1 group">
                  <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-2xl group-hover:bg-yellow-500/20 group-hover:text-yellow-400 transition-colors">
                    {['🥦', '🍎', '🥛', '🍞', '🍟', '🥤', '🍜', '☕'][i]}
                  </div>
                  <span className="text-xs font-medium text-slate-300 group-hover:text-white">{cat}</span>
                </div>
              ))}
            </div>
          </div>

        </main>

        <StartAudio label="Start Audio" />
        <RoomAudioRenderer />
        <Toaster />
      </div>
    </SessionProvider>
  );
}
