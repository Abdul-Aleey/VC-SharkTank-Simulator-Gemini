import React from 'react';
import { Play, Layers, Users, Sparkles, Cpu } from 'lucide-react';
import { Language, SimMode, Personality, SimulationConfig } from '../types';
import { INVESTOR_PROFILES, PERSONALITY_DESCRIPTIONS } from '../constants';

const MODELS = [
  {
    id: 'gemini-2.5-flash',
    label: 'Gemini 2.5 Flash',
    badge: 'Balanced',
    badgeColor: 'bg-slate-700 text-slate-400',
    desc: 'Fast responses, lower cost. Works in all deployment modes.',
    vertexAI: true,
  },
  {
    id: 'gemini-2.5-pro',
    label: 'Gemini 2.5 Pro',
    badge: 'Highest Quality',
    badgeColor: 'bg-violet-500/20 text-violet-400',
    desc: 'Best reasoning and dialogue depth. Works in all deployment modes.',
    vertexAI: true,
  },
  {
    id: 'gemini-3.5-flash',
    label: 'Gemini 3.5 Flash',
    badge: 'Latest',
    badgeColor: 'bg-emerald-500/20 text-emerald-400',
    desc: 'Frontier model. May not be available on Vertex AI yet — backend falls back to 2.5 Flash if needed.',
    vertexAI: false,
  },
];

interface Props {
  config: SimulationConfig;
  onChange: (config: SimulationConfig) => void;
  onStart: () => void;
  vertexAIMode?: boolean;
  t: any;
}

export default function SetupScreen({ config, onChange, onStart, vertexAIMode = false, t }: Props) {
  // Helper to partially update config without repeating the spread everywhere
  const set = (patch: Partial<SimulationConfig>) => onChange({ ...config, ...patch });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start animate-fade-in">

      {/* ── Left column: simulation config form ── */}
      <div className="lg:col-span-7 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl shadow-black/40 space-y-6">
        <div className="flex items-center gap-3 border-b border-white/5 pb-4">
          <Layers className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-semibold">{t.setupTitle}</h2>
        </div>

        {/* Mode: Real Entrepreneur vs AI Autopilot */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <button
            onClick={() => set({ mode: SimMode.REAL })}
            className={`p-4 rounded-xl border text-left transition-all ${
              config.mode === SimMode.REAL
                ? 'bg-indigo-600/10 border-indigo-500 shadow-lg shadow-indigo-500/10'
                : 'bg-slate-800/30 border-white/5 hover:border-white/10'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Users className="w-4 h-4 text-indigo-400" />
              <span className="font-semibold text-sm">{t.realMode}</span>
            </div>
            <p className="text-xs text-slate-400">{t.realModeDesc}</p>
          </button>

          <button
            onClick={() => set({ mode: SimMode.AI })}
            className={`p-4 rounded-xl border text-left transition-all ${
              config.mode === SimMode.AI
                ? 'bg-indigo-600/10 border-indigo-500 shadow-lg shadow-indigo-500/10'
                : 'bg-slate-800/30 border-white/5 hover:border-white/10'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span className="font-semibold text-sm">{t.aiMode}</span>
            </div>
            <p className="text-xs text-slate-400">{t.aiModeDesc}</p>
          </button>
        </div>

        {/* Model selector */}
        <div className="space-y-2 pt-2 border-t border-white/5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400" />
              <label className="text-sm font-semibold text-slate-300">Gemini Model</label>
            </div>
            {vertexAIMode && (
              <span className="text-xs text-sky-400 bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-full">
                Vertex AI
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {MODELS.map(({ id, label, badge, badgeColor, desc, vertexAI }) => {
              const unavailableOnVertex = vertexAIMode && !vertexAI;
              return (
                <button
                  key={id}
                  onClick={() => set({ model: id })}
                  className={`p-3 rounded-xl border text-left transition-all relative ${
                    config.model === id
                      ? 'bg-indigo-600/10 border-indigo-500 shadow-lg shadow-indigo-500/10'
                      : 'bg-slate-800/30 border-white/5 hover:border-white/10'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1 gap-1 flex-wrap">
                    <span className="font-semibold text-xs">{label}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${badgeColor}`}>
                      {badge}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{desc}</p>
                  {unavailableOnVertex && (
                    <p className="text-xs text-amber-400 mt-1">Auto-fallback to 2.5 Flash if unavailable</p>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Number of Q&A rounds (1–10) */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <label className="text-slate-300 font-medium">{t.rounds}</label>
            <span className="text-indigo-400 font-bold">{config.rounds} Rounds</span>
          </div>
          <input
            type="range" min="1" max="10" value={config.rounds}
            onChange={(e) => set({ rounds: parseInt(e.target.value) })}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
          />
          <p className="text-xs text-slate-400">{t.roundsDesc}</p>
        </div>

        {/* Startup detail fields */}
        <div className="space-y-4 pt-4 border-t border-white/5">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">{t.startupDetails}</h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400">{t.startupName}</label>
              <input type="text" value={config.startupName}
                onChange={(e) => set({ startupName: e.target.value })}
                className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400">{t.founderName}</label>
              <input type="text" value={config.founderName}
                onChange={(e) => set({ founderName: e.target.value })}
                className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400">{t.sector}</label>
              <input type="text" value={config.sector}
                onChange={(e) => set({ sector: e.target.value })}
                className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400">{t.fundingAsk}</label>
              <input type="text" value={config.askAmount}
                onChange={(e) => set({ askAmount: e.target.value })}
                className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400">{t.equityOffer}</label>
              <input type="number" value={config.askEquity}
                onChange={(e) => set({ askEquity: parseInt(e.target.value) || 0 })}
                className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-slate-400">{t.description}</label>
            <textarea rows={3} value={config.description}
              onChange={(e) => set({ description: e.target.value })}
              className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500 resize-none" />
          </div>
        </div>

        {/* AI founder personality — only visible in AI mode */}
        {config.mode === SimMode.AI && (
          <div className="space-y-4 pt-4 border-t border-white/5">
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-slate-300">{t.aiPersonality}</label>
              <select
                value={config.personality}
                onChange={(e) => set({ personality: e.target.value as Personality })}
                className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
              >
                {Object.values(Personality).map(p => (
                  <option key={p} value={p} className="bg-slate-900">{p.toUpperCase()}</option>
                ))}
              </select>
              <p className="text-xs text-indigo-400 mt-1">
                {PERSONALITY_DESCRIPTIONS[config.language][config.personality]}
              </p>
            </div>
          </div>
        )}

        {/* Launch simulation */}
        <button
          onClick={onStart}
          className="w-full py-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/20 transition-all flex items-center justify-center gap-2 group"
        >
          <Play className="w-5 h-5 fill-current group-hover:scale-110 transition-transform" />
          {t.startSim}
        </button>
      </div>

      {/* ── Right column: investor profile preview ── */}
      <div className="lg:col-span-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider px-1">{t.investorPanel}</h3>
        <div className="grid grid-cols-1 gap-4">
          {Object.values(INVESTOR_PROFILES).map(profile => (
            <div
              key={profile.id}
              className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-xl p-4 flex gap-4 hover:border-white/20 transition-all"
              style={{ borderLeft: `4px solid hsl(${profile.color})` }}
            >
              <div className="text-3xl p-2 bg-slate-800/50 rounded-lg h-fit">{profile.emoji}</div>
              <div className="space-y-1">
                <h4 className="font-bold text-slate-200">{profile.name}</h4>
                <p className="text-xs text-indigo-400 font-medium">{profile.focus}</p>
                <p className="text-xs text-slate-400 line-clamp-2">{profile.bio}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
