import React from 'react';
import { TrendingUp, TrendingDown, Info } from 'lucide-react';
import { InvestorId, InvestorState, InvestorStatus } from '../types';
import { INVESTOR_PROFILES } from '../constants';

interface Props {
  investor: InvestorState;
  activeSpeaker: 'founder' | InvestorId | 'system' | null;
  rounds: number;
  confidenceLabel: string;
  questionsCountLabel: string;
  analyzeNotesLabel: string;
  onAnalyzeNotes: (id: InvestorId) => void;
}

// Single shark investor card shown in the simulation dashboard.
// Shows: confidence bar, trend arrow, internal thought bubble, question count.
// Glows when this investor is the active speaker.
// Shows a scanning animation while the investor is evaluating the founder's response.
export default function InvestorCard({
  investor: inv,
  activeSpeaker,
  rounds,
  confidenceLabel,
  questionsCountLabel,
  analyzeNotesLabel,
  onAnalyzeNotes
}: Props) {
  const profile = INVESTOR_PROFILES[inv.id];
  const isSpeaker = activeSpeaker === inv.id;

  return (
    <div
      className={`relative bg-slate-900/40 backdrop-blur-xl border rounded-2xl p-5 flex flex-col justify-between gap-4 transition-all duration-300 overflow-hidden ${
        isSpeaker ? 'ring-2 ring-indigo-500 shadow-lg shadow-indigo-500/10' : 'border-white/10'
      }`}
      style={{ borderTop: `4px solid hsl(${profile.color})` }}
    >
      {/* Hologram scanning line that plays while investor is evaluating */}
      {inv.isThinking && (
        <div className="absolute inset-0 bg-indigo-500/5 pointer-events-none overflow-hidden">
          <div className="laser-scan-line" />
        </div>
      )}

      {/* Name, emoji, focus, and status badge */}
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{profile.emoji}</span>
          <div>
            <h4 className="font-bold text-slate-200 text-sm">{profile.name}</h4>
            <span className="text-[10px] text-slate-400 block">{profile.focus}</span>
          </div>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
          inv.status === InvestorStatus.INVEST
            ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
            : inv.status === InvestorStatus.OUT
            ? 'bg-red-500/10 border border-red-500/20 text-red-400'
            : 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-400'
        }`}>
          {inv.status}
        </span>
      </div>

      {/* Confidence percentage bar with trend indicator */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">{confidenceLabel}</span>
          <div className="flex items-center gap-1">
            <span className="font-bold" style={{ color: `hsl(${profile.color})` }}>
              {inv.confidence}%
            </span>
            {inv.trend !== 0 && (
              <span className={`text-[10px] flex items-center ${inv.trend > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {inv.trend > 0
                  ? <TrendingUp className="w-3 h-3" />
                  : <TrendingDown className="w-3 h-3" />}
                {inv.trend > 0 ? `+${inv.trend}` : inv.trend}%
              </span>
            )}
          </div>
        </div>
        <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full transition-all duration-500"
            style={{ width: `${inv.confidence}%`, backgroundColor: `hsl(${profile.color})` }}
          />
        </div>
      </div>

      {/* Thought bubble: bouncing dots while thinking, internal critique when idle */}
      <div className="bg-slate-950/50 border border-white/5 rounded-xl p-3 min-h-[60px] flex items-center justify-center text-center">
        {inv.isThinking ? (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.2s]" />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.4s]" />
          </div>
        ) : (
          <p className="text-xs text-slate-300 italic">
            {inv.thoughtBubble ? `"${inv.thoughtBubble}"` : '...'}
          </p>
        )}
      </div>

      {/* Footer: questions asked + analyze notes button */}
      <div className="flex justify-between items-center text-xs border-t border-white/5 pt-3">
        <span className="text-slate-400">{questionsCountLabel}: {inv.questionsAsked}/{rounds}</span>
        <button
          onClick={() => onAnalyzeNotes(inv.id)}
          className="text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1"
        >
          <Info className="w-3.5 h-3.5" />
          {analyzeNotesLabel}
        </button>
      </div>
    </div>
  );
}
