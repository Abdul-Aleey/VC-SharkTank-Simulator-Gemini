import React, { useState } from 'react';
import {
  MessageSquare, Volume2, Sparkles, Send, Mic, MicOff,
  VolumeX, AlertTriangle, Cpu, X, CheckCircle
} from 'lucide-react';
import {
  InvestorId, InvestorState, AgentState, Message,
  Offer, SimulationConfig, AgentLog, SimMode
} from '../types';
import { INVESTOR_PROFILES } from '../constants';
import InvestorCard from './InvestorCard';

interface Props {
  config: SimulationConfig;
  investors: Record<InvestorId, InvestorState>;
  founderAgentState: AgentState;
  agentLogs: AgentLog[];
  chat: Message[];
  currentRound: number;
  activeSpeaker: 'founder' | InvestorId | 'system' | null;
  isProcessing: boolean;
  isMuted: boolean;
  isAutoplay: boolean;
  isListening: boolean;
  inputText: string;
  activeOffers: Offer[];
  chatEndRef: React.RefObject<HTMLDivElement>;
  onInputChange: (val: string) => void;
  onToggleMute: () => void;
  onToggleAutoplay: () => void;
  onToggleListening: () => void;
  onResponseSubmit: (text?: string) => void;
  onAIAssist: () => void;
  onAcceptOffer: (offer: Offer) => void;
  onCounterOffer: (counterText: string, investorId?: string) => void;
  onWalkAway: () => void;
  onSpeakText: (text: string, speaker: 'founder' | InvestorId | 'system') => void;
  t: any; // translation object
}

// Full active simulation view:
// - Multi-agent SDK monitor strip at the top
// - Metadata bar (startup name, ask, round progress)
// - 4-column investor card grid
// - Chat feed + input dock side-by-side
// - SDK orchestrator logs at the bottom
// - Inline modals for investor notes and counter-offer
export default function SimulationScreen({
  config, investors, founderAgentState, agentLogs,
  chat, currentRound, activeSpeaker, isProcessing,
  isMuted, isAutoplay, isListening, inputText, activeOffers,
  chatEndRef, onInputChange, onToggleMute, onToggleAutoplay,
  onToggleListening, onResponseSubmit, onAIAssist,
  onAcceptOffer, onCounterOffer, onWalkAway,
  onSpeakText, t
}: Props) {
  // Local UI state — doesn't need to live in App because it's only relevant here
  const [notesModal, setNotesModal] = useState<InvestorId | null>(null);
  const [counterOfferTarget, setCounterOfferTarget] = useState<Offer | null>(null);
  const [counterText, setCounterText] = useState('');

  const handleSubmitCounter = () => {
    if (!counterText.trim()) return;
    onCounterOffer(counterText.trim(), counterOfferTarget?.investors[0]);
    setCounterOfferTarget(null);
    setCounterText('');
  };

  // Color class for agent state badges in the monitor strip
  const agentStateClass = (state: AgentState) => {
    switch (state) {
      case AgentState.ASKING:     return 'bg-amber-500/20 text-amber-400 animate-pulse';
      case AgentState.EVALUATING: return 'bg-indigo-500/20 text-indigo-400 animate-pulse';
      case AgentState.PITCHING:   return 'bg-indigo-500/20 text-indigo-400 animate-pulse';
      case AgentState.OUT:        return 'bg-red-500/20 text-red-400';
      case AgentState.INVESTED:   return 'bg-emerald-500/20 text-emerald-400';
      default:                    return 'bg-slate-800 text-slate-400';
    }
  };

  const totalQuestionsAsked = Object.values(investors).reduce((sum, i) => sum + i.questionsAsked, 0);
  const totalExpectedQuestions = config.rounds * 4;

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Multi-Agent SDK Monitor Strip ── */}
      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-2xl p-4 shadow-xl">
        <div className="flex items-center gap-2 border-b border-white/5 pb-3 mb-3">
          <Cpu className="w-5 h-5 text-indigo-400 animate-spin" />
          <h3 className="font-bold text-sm tracking-wider uppercase text-slate-300">{t.agentMonitor}</h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {/* Founder agent */}
          <div className="bg-slate-950/50 border border-white/5 rounded-xl p-3 flex flex-col items-center text-center">
            <span className="text-xs text-slate-400 block mb-1">{t.agentFounder}</span>
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${agentStateClass(founderAgentState)}`}>
              {founderAgentState}
            </span>
          </div>
          {/* One cell per investor agent */}
          {([
            [InvestorId.VINCENT,  t.agentVincent],
            [InvestorId.MARCUS,   t.agentMarcus],
            [InvestorId.BEATRICE, t.agentBeatrice],
            [InvestorId.LEONA,    t.agentLeona],
          ] as [InvestorId, string][]).map(([id, label]) => (
            <div key={id} className="bg-slate-950/50 border border-white/5 rounded-xl p-3 flex flex-col items-center text-center">
              <span className="text-xs text-slate-400 block mb-1">{label}</span>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${agentStateClass(investors[id].agentState)}`}>
                {investors[id].agentState}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Simulation metadata bar ── */}
      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-xs text-slate-400 uppercase tracking-wider block">{t.startupName}</span>
            <span className="font-bold text-lg text-white">{config.startupName}</span>
          </div>
          <div className="h-8 w-px bg-white/10" />
          <div>
            <span className="text-xs text-slate-400 uppercase tracking-wider block">{t.fundingAsk}</span>
            <span className="font-bold text-lg text-indigo-400">{config.askAmount} / {config.askEquity}%</span>
          </div>
          <div className="h-8 w-px bg-white/10 hidden sm:block" />
          <div className="hidden sm:block">
            <span className="text-xs text-slate-400 uppercase tracking-wider block">{t.sector}</span>
            <span className="font-medium text-slate-300">{config.sector}</span>
          </div>
        </div>

        {/* Round progress bar */}
        <div className="flex items-center gap-4 w-full md:w-auto">
          <div className="flex-1 md:w-48">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">{t.round} {currentRound} / {config.rounds}</span>
              <span className="text-indigo-400 font-semibold">
                {totalQuestionsAsked} / {totalExpectedQuestions} {t.questions}
              </span>
            </div>
            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500"
                style={{ width: `${(totalQuestionsAsked / totalExpectedQuestions) * 100}%` }}
              />
            </div>
          </div>
          <span className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs px-2.5 py-1 rounded-full font-semibold">
            {config.model.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ')}
          </span>
        </div>
      </div>

      {/* ── 4-column investor card grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.values(investors).map(inv => (
          <InvestorCard
            key={inv.id}
            investor={inv}
            activeSpeaker={activeSpeaker}
            rounds={config.rounds}
            confidenceLabel={t.confidence}
            questionsCountLabel={t.questionsCount}
            analyzeNotesLabel={t.analyzeNotes}
            onAnalyzeNotes={setNotesModal}
          />
        ))}
      </div>

      {/* ── Chat feed + input dock ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Chat feed */}
        <div className="lg:col-span-8 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 flex flex-col h-[500px] shadow-xl">
          <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-indigo-400" />
              <h3 className="font-semibold">{t.chatFeed}</h3>
            </div>
            {isProcessing && (
              <span className="text-xs text-indigo-400 animate-pulse flex items-center gap-1.5">
                <span className="w-2 h-2 bg-indigo-500 rounded-full animate-ping" />
                {t.thinking}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto space-y-4 pr-2">
            {chat.map((msg) => {
              const isFounder = msg.sender === 'founder';
              const isSystem = msg.sender === 'system';
              const profile = !isFounder && !isSystem ? INVESTOR_PROFILES[msg.sender as InvestorId] : null;
              const isSpeaker = activeSpeaker === msg.sender;

              if (isSystem) {
                return (
                  <div key={msg.id} className="flex justify-center my-2">
                    <div className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs px-4 py-1.5 rounded-full flex items-center gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-indigo-400" />
                      <span>{msg.text}</span>
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 max-w-[85%] ${isFounder ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
                >
                  {/* Speaker avatar — glows when actively speaking */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-all ${
                    isFounder ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200'
                  } ${isSpeaker ? 'ring-2 ring-indigo-500 animate-pulse' : ''}`}>
                    {isFounder ? 'F' : profile?.emoji}
                  </div>

                  {/* Message bubble */}
                  <div className={`rounded-2xl p-4 space-y-1 relative group ${
                    isFounder
                      ? 'bg-indigo-600/20 border border-indigo-500/30 text-slate-100 rounded-tr-none'
                      : 'bg-slate-800/40 border border-white/5 text-slate-200 rounded-tl-none'
                  }`}>
                    <div className="flex justify-between items-center gap-4">
                      <span className="text-xs font-bold text-slate-300">{msg.senderName}</span>
                      {/* Re-play audio button — appears on hover */}
                      <button
                        onClick={() => onSpeakText(msg.text, msg.sender as any)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-white/5 rounded text-slate-400 hover:text-white"
                      >
                        <Volume2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                  </div>
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* ── Input dock ── */}
        <div className="lg:col-span-4 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 flex flex-col justify-between gap-6 shadow-xl">

          {/* Audio controls */}
          <div className="flex items-center justify-between border-b border-white/5 pb-4">
            <div className="flex items-center gap-4">
              <button
                onClick={onToggleAutoplay}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                  isAutoplay
                    ? 'bg-indigo-600/20 border-indigo-500 text-indigo-400'
                    : 'bg-slate-800/50 border-white/5 text-slate-400 hover:text-white'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                {t.autoplay}
              </button>
              <button
                onClick={onToggleMute}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                  isMuted
                    ? 'bg-red-500/20 border-red-500/30 text-red-400'
                    : 'bg-slate-800/50 border-white/5 text-slate-400 hover:text-white'
                }`}
              >
                {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                {isMuted ? t.mute : t.unmute}
              </button>
            </div>
          </div>

          {/* Bargaining phase: show offer cards */}
          {activeOffers.length > 0 ? (
            <div className="space-y-4 flex-1 overflow-y-auto">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{t.activeOffers}</h4>
              <div className="space-y-3">
                {activeOffers.map(offer => {
                  const names = offer.investors.map(id => INVESTOR_PROFILES[id].name).join(' & ');
                  return (
                    <div
                      key={offer.id}
                      className={`border rounded-xl p-4 space-y-3 transition-all ${
                        offer.revised
                          ? 'bg-amber-900/10 border-amber-500/30 hover:border-amber-400/50'
                          : 'bg-slate-800/40 border-white/5 hover:border-indigo-500/30'
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-indigo-400 font-bold">
                              {offer.isJoint ? t.jointOffer : 'Offer'}
                            </span>
                            {offer.revised && (
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                Revised ✓
                              </span>
                            )}
                          </div>
                          <span className="font-bold text-sm text-slate-200">{names}</span>
                        </div>
                        <span className="text-lg font-extrabold text-emerald-400">{offer.cash}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-slate-400">Equity</span>
                        <span className="font-bold text-white text-sm">{offer.equity}%</span>
                      </div>
                      <div className="bg-slate-900/60 rounded-lg px-3 py-2 text-xs text-slate-300 leading-relaxed border border-white/5">
                        {offer.terms}
                      </div>
                      {/* Action buttons — REAL mode only; AI mode negotiates autonomously */}
                      {config.mode === SimMode.REAL && (
                        <div className="grid grid-cols-2 gap-2 pt-2">
                          <button
                            onClick={() => onAcceptOffer(offer)}
                            className="py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-all"
                          >
                            {t.acceptDeal}
                          </button>
                          <button
                            onClick={() => { setCounterOfferTarget(offer); setCounterText(''); }}
                            className="py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg transition-all"
                          >
                            {t.counterOffer}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Walk away — REAL mode only */}
                {config.mode === SimMode.REAL && (
                  <button
                    onClick={onWalkAway}
                    className="w-full py-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 rounded-xl transition-all text-xs font-bold flex flex-col items-center justify-center gap-1"
                  >
                    <span>{t.walkAway}</span>
                    <span className="text-[10px] text-red-400/60 font-normal">{t.walkAwayDesc}</span>
                  </button>
                )}

                {/* AI mode: show that negotiation is happening autonomously */}
                {config.mode === SimMode.AI && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs">
                    <Sparkles className="w-3.5 h-3.5 animate-pulse shrink-0" />
                    AI Founder is negotiating…
                  </div>
                )}
              </div>
            </div>
          ) : (
            // Standard pitch input controls
            <div className="space-y-4 flex-1 flex flex-col justify-end">
              {config.mode === SimMode.REAL ? (
                <div className="space-y-3">
                  <div className="relative">
                    <textarea
                      rows={3}
                      value={inputText}
                      onChange={(e) => onInputChange(e.target.value)}
                      placeholder={t.typePlaceholder}
                      disabled={isProcessing}
                      className="w-full bg-slate-800/50 border border-white/10 rounded-xl pl-4 pr-12 py-3 text-sm focus:outline-none focus:border-indigo-500 resize-none disabled:opacity-50"
                    />
                    <button
                      onClick={onToggleListening}
                      className={`absolute right-3 bottom-4 p-2 rounded-lg transition-all ${
                        isListening
                          ? 'bg-red-500 text-white animate-pulse'
                          : 'bg-slate-700 text-slate-300 hover:text-white'
                      }`}
                    >
                      {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                    </button>
                  </div>
                  <button
                    onClick={() => onResponseSubmit()}
                    disabled={isProcessing || !inputText.trim()}
                    className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
                  >
                    <Send className="w-4 h-4" />
                    {t.speakBtn}
                  </button>
                </div>
              ) : (
                // AI autopilot status display
                <div className="bg-slate-800/30 border border-white/5 rounded-xl p-4 text-center space-y-2">
                  <Sparkles className="w-8 h-8 text-indigo-400 mx-auto animate-pulse" />
                  <h4 className="font-bold text-sm text-slate-200">AI Autopilot Active</h4>
                  <p className="text-xs text-slate-400">
                    The AI founder is pitching and answering questions autonomously. Sit back and watch the simulation unfold.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── SDK orchestrator logs ── */}
      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-xl">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          System Logs (Google ADK Orchestrator)
        </h4>
        <div className="bg-slate-950/80 rounded-xl p-4 h-40 overflow-y-auto font-mono text-xs space-y-2 border border-white/5">
          {agentLogs.length === 0 ? (
            <span className="text-slate-600">No logs recorded yet. Launch simulation to begin.</span>
          ) : (
            agentLogs.map(log => (
              <div key={log.id} className="flex gap-2">
                <span className="text-slate-500">[{log.timestamp}]</span>
                <span className="text-indigo-400 font-bold shrink-0">{log.agentName}:</span>
                <span className={
                  log.type === 'success' ? 'text-emerald-400' :
                  log.type === 'warning' ? 'text-amber-400' :
                  log.type === 'error'   ? 'text-red-400'    : 'text-slate-300'
                }>{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Investor Notes Modal ── */}
      {notesModal && (() => {
        const inv = investors[notesModal];
        const profile = INVESTOR_PROFILES[notesModal];
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
            <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-lg w-full space-y-4 shadow-2xl">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{profile.emoji}</span>
                  <h3 className="text-lg font-bold text-white">{profile.name} — {t.analyzeNotes}</h3>
                </div>
                <button onClick={() => setNotesModal(null)} className="p-1.5 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2">{t.strengths}</h4>
                  {inv.strengths.length > 0
                    ? inv.strengths.map((s, i) => <p key={i} className="text-sm text-slate-300">• {s}</p>)
                    : <p className="text-xs text-slate-500">None recorded yet.</p>}
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">{t.weaknesses}</h4>
                  {inv.weaknesses.length > 0
                    ? inv.weaknesses.map((w, i) => <p key={i} className="text-sm text-slate-300">• {w}</p>)
                    : <p className="text-xs text-slate-500">None recorded yet.</p>}
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2">{t.risks}</h4>
                  {inv.risks.length > 0
                    ? inv.risks.map((r, i) => <p key={i} className="text-sm text-slate-300">• {r}</p>)
                    : <p className="text-xs text-slate-500">None recorded yet.</p>}
                </div>
              </div>

              <button
                onClick={() => setNotesModal(null)}
                className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-xl transition-all"
              >
                {t.close}
              </button>
            </div>
          </div>
        );
      })()}

      {/* ── Counter-Offer Modal ── */}
      {counterOfferTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-white">{t.counterOffer}</h3>
                <p className="text-xs text-indigo-400 mt-0.5">
                  Negotiating with{' '}
                  <strong>{INVESTOR_PROFILES[counterOfferTarget.investors[0] as InvestorId]?.name}</strong>
                  {counterOfferTarget.isJoint && counterOfferTarget.investors[1] &&
                    <> &amp; <strong>{INVESTOR_PROFILES[counterOfferTarget.investors[1] as InvestorId]?.name}</strong></>
                  }
                </p>
              </div>
              <button onClick={() => setCounterOfferTarget(null)} className="p-1.5 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-all">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Their offer: <strong className="text-slate-200">{counterOfferTarget.cash}</strong> for{' '}
              <strong className="text-slate-200">{counterOfferTarget.equity}%</strong> equity.
            </p>
            <textarea
              rows={3}
              value={counterText}
              onChange={(e) => setCounterText(e.target.value)}
              placeholder={t.counterPlaceholder}
              className="w-full bg-slate-800/50 border border-white/10 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 resize-none"
            />
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={handleSubmitCounter}
                disabled={!counterText.trim()}
                className="py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
              >
                <CheckCircle className="w-4 h-4" />
                {t.submitCounter}
              </button>
              <button
                onClick={() => setCounterOfferTarget(null)}
                className="py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-xl transition-all"
              >
                {t.close}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
