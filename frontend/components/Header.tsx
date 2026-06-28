import React from 'react';
import { Sparkles, RotateCcw } from 'lucide-react';
import { Language } from '../types';

interface Props {
  step: 'SETUP' | 'SIMULATION' | 'REPORT';
  language: Language;
  apiConnected: boolean;
  isVerifyingKey: boolean;
  title: string;
  subtitle: string;
  apiActiveLabel: string;
  apiMissingLabel: string;
  restartLabel: string;
  onLanguageChange: (lang: Language) => void;
  onOpenApiModal: () => void;
  onRestartClick: () => void;
}

// Sticky top navigation bar.
// Language switcher is disabled during active simulation to avoid mid-pitch state conflicts.
// API badge shows live verification status and reopens the key modal on click.
export default function Header({
  step, language, apiConnected, isVerifyingKey,
  title, subtitle, apiActiveLabel, apiMissingLabel, restartLabel,
  onLanguageChange, onOpenApiModal, onRestartClick
}: Props) {
  const duringSimulation = step !== 'SETUP';

  return (
    <header className="sticky top-0 z-40 bg-slate-900/60 backdrop-blur-xl border-b border-white/10 px-6 py-4 flex items-center justify-between print:hidden">

      {/* Logo + title */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gradient-to-tr from-indigo-600 to-violet-500 rounded-xl shadow-lg shadow-indigo-500/30">
          <Sparkles className="w-6 h-6 text-white animate-pulse" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
            {title}
          </h1>
          <p className="text-xs text-slate-400 hidden sm:block">{subtitle}</p>
        </div>
      </div>

      <div className="flex items-center gap-4">

        {/* Language switcher — grayed out and non-interactive during simulation */}
        <div
          className={`flex bg-slate-800/80 p-1 rounded-lg border border-white/5 ${duringSimulation ? 'opacity-40 cursor-not-allowed' : ''}`}
          title={duringSimulation ? 'Language cannot be changed during an active simulation' : undefined}
        >
          <button
            onClick={() => !duringSimulation && onLanguageChange(Language.EN)}
            disabled={duringSimulation}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${language === Language.EN ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'} disabled:pointer-events-none`}
          >
            EN
          </button>
          <button
            onClick={() => !duringSimulation && onLanguageChange(Language.JA)}
            disabled={duringSimulation}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${language === Language.JA ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-white'} disabled:pointer-events-none`}
          >
            JA
          </button>
        </div>

        {/* API status badge — click to open key modal */}
        <button
          onClick={onOpenApiModal}
          className="flex items-center gap-2 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-white/5 text-xs hover:border-indigo-500/50 transition-all"
        >
          {isVerifyingKey ? (
            <span className="w-2.5 h-2.5 border-2 border-slate-400/40 border-t-slate-300 rounded-full animate-spin" />
          ) : (
            <span className={`w-2.5 h-2.5 rounded-full ${apiConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          )}
          <span className="text-slate-300 hidden md:inline">
            {isVerifyingKey ? 'Verifying...' : apiConnected ? apiActiveLabel : apiMissingLabel}
          </span>
        </button>

        {/* Restart button — only visible during simulation or report */}
        {duringSimulation && (
          <button
            onClick={onRestartClick}
            className="p-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 rounded-lg transition-all text-xs flex items-center gap-1.5"
          >
            <RotateCcw className="w-4 h-4" />
            <span className="hidden sm:inline">{restartLabel}</span>
          </button>
        )}

      </div>
    </header>
  );
}
