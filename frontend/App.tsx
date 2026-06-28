import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Language, SimMode, InvestorId, InvestorStatus,
  InvestorState, Message, Offer, SimulationConfig, ReportData, AgentState, AgentLog
} from './types';
import { INVESTOR_PROFILES, STARTUP_PRESETS, TRANSLATIONS } from './constants';
import { setApiKey, verifyApiKey } from './services/geminiService';
import { SimulationWebSocket, SimEvent, BACKEND_HTTP_URL } from './services/simulationService';

import Header from './components/Header';
import ApiKeyModal from './components/ApiKeyModal';
import SetupScreen from './components/SetupScreen';
import SimulationScreen from './components/SimulationScreen';
import ReportScreen from './components/ReportScreen';

const LS_KEY = 'gemini_api_key';

const makeInitialInvestors = (): Record<InvestorId, InvestorState> => ({
  [InvestorId.VINCENT]:  { id: InvestorId.VINCENT,  status: InvestorStatus.ACTIVE, confidence: 50, trend: 0, questionsAsked: 0, thoughtBubble: '', strengths: [], weaknesses: [], risks: [], isThinking: false, agentState: AgentState.IDLE },
  [InvestorId.MARCUS]:   { id: InvestorId.MARCUS,   status: InvestorStatus.ACTIVE, confidence: 50, trend: 0, questionsAsked: 0, thoughtBubble: '', strengths: [], weaknesses: [], risks: [], isThinking: false, agentState: AgentState.IDLE },
  [InvestorId.BEATRICE]: { id: InvestorId.BEATRICE, status: InvestorStatus.ACTIVE, confidence: 50, trend: 0, questionsAsked: 0, thoughtBubble: '', strengths: [], weaknesses: [], risks: [], isThinking: false, agentState: AgentState.IDLE },
  [InvestorId.LEONA]:    { id: InvestorId.LEONA,    status: InvestorStatus.ACTIVE, confidence: 50, trend: 0, questionsAsked: 0, thoughtBubble: '', strengths: [], weaknesses: [], risks: [], isThinking: false, agentState: AgentState.IDLE },
});

export default function App() {

  const [step, setStep]         = useState<'SETUP' | 'SIMULATION' | 'REPORT'>('SETUP');
  const [config, setConfig]     = useState<SimulationConfig>({
    mode: SimMode.REAL, model: 'gemini-2.5-flash', rounds: 3, language: Language.EN,
    startupName: STARTUP_PRESETS[Language.EN].startupName,
    founderName: STARTUP_PRESETS[Language.EN].founderName,
    sector:      STARTUP_PRESETS[Language.EN].sector,
    askAmount:   STARTUP_PRESETS[Language.EN].askAmount,
    askEquity:   STARTUP_PRESETS[Language.EN].askEquity,
    description: STARTUP_PRESETS[Language.EN].description,
    personality: 'excellent' as any, customTraits: '',
  });

  const [investors, setInvestors]             = useState<Record<InvestorId, InvestorState>>(makeInitialInvestors());
  const [founderAgentState, setFounderAgentState] = useState<AgentState>(AgentState.IDLE);
  const [agentLogs, setAgentLogs]             = useState<AgentLog[]>([]);
  const [chat, setChat]                       = useState<Message[]>([]);
  const [currentRound, setCurrentRound]       = useState<number>(1);
  const [activeSpeaker, setActiveSpeaker]     = useState<'founder' | InvestorId | 'system' | null>(null);
  const [inputText, setInputText]             = useState<string>('');
  const [isProcessing, setIsProcessing]       = useState<boolean>(false);
  const [isMuted, setIsMuted]                 = useState<boolean>(false);
  const [isAutoplay, setIsAutoplay]           = useState<boolean>(false);
  const [isListening, setIsListening]         = useState<boolean>(false);
  const [activeOffers, setActiveOffers]       = useState<Offer[]>([]);
  const [report, setReport]                   = useState<ReportData | null>(null);
  const [showRestartConfirm, setShowRestartConfirm] = useState<boolean>(false);

  // API key modal state
  const [apiConnected, setApiConnected]     = useState<boolean>(false);
  const [showApiModal, setShowApiModal]     = useState<boolean>(false);
  const [apiKeyInput, setApiKeyInput]       = useState<string>('');
  const [apiKeyError, setApiKeyError]       = useState<string>('');
  const [isVerifyingKey, setIsVerifyingKey] = useState<boolean>(false);
  const [vertexAIMode, setVertexAIMode]     = useState<boolean>(false);

  const speechTokenRef  = useRef<number>(0);
  const speechQueueRef  = useRef<Promise<void>>(Promise.resolve());
  const recognitionRef  = useRef<any>(null);
  const chatEndRef      = useRef<HTMLDivElement>(null);
  const wsRef           = useRef<SimulationWebSocket | null>(null);

  const t = TRANSLATIONS[config.language];

  // ── On mount: check backend config, then handle API key ──────────────────
  useEffect(() => {
    fetch(`${BACKEND_HTTP_URL}/config`)
      .then(r => r.json())
      .then((cfg: { requiresApiKey: boolean; vertexAI: boolean }) => {
        setVertexAIMode(cfg.vertexAI);
        if (!cfg.requiresApiKey) {
          // Vertex AI mode — backend uses its own GCP credentials, no key needed
          setApiConnected(true);
          return;
        }
        // Google AI Studio mode — restore key from localStorage
        const stored = localStorage.getItem(LS_KEY);
        if (!stored) { setShowApiModal(true); return; }
        setIsVerifyingKey(true);
        verifyApiKey(stored).then(result => {
          setIsVerifyingKey(false);
          if (result.ok) { setApiKey(stored); setApiConnected(true); }
          else { localStorage.removeItem(LS_KEY); setShowApiModal(true); }
        });
      })
      .catch(() => {
        // Backend unreachable — still show the key modal so the user can see the error
        setShowApiModal(true);
      });
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat]);

  // ── API key handlers ──────────────────────────────────────────────────────
  const handleSaveApiKey = async () => {
    const trimmed = apiKeyInput.trim();
    if (!trimmed) { setApiKeyError('API key cannot be empty.'); return; }
    setIsVerifyingKey(true); setApiKeyError('');
    const result = await verifyApiKey(trimmed);
    setIsVerifyingKey(false);
    if (!result.ok) { setApiKeyError(result.error || 'Connection failed.'); setApiConnected(false); return; }
    setApiKey(trimmed);
    localStorage.setItem(LS_KEY, trimmed);
    setApiConnected(true);
    setShowApiModal(false);
  };

  const handleLanguageChange = (lang: Language) => {
    const preset = STARTUP_PRESETS[lang];
    setConfig(prev => ({ ...prev, language: lang, ...preset }));
  };

  // ── Agent log ─────────────────────────────────────────────────────────────
  const addAgentLog = useCallback((agentName: string, message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info') => {
    setAgentLogs(prev => [{
      id: Math.random().toString(), timestamp: new Date().toLocaleTimeString(),
      agentName, message, type,
    }, ...prev].slice(0, 30));
  }, []);

  // ── Speech synthesis ──────────────────────────────────────────────────────
  const speakText = useCallback((text: string, speakerId: 'founder' | InvestorId | 'system'): Promise<void> => {
    if (isMuted) return Promise.resolve();
    return new Promise<void>((resolve) => {
      const currentToken = ++speechTokenRef.current;
      window.speechSynthesis.cancel();
      setTimeout(() => {
        if (currentToken !== speechTokenRef.current) { resolve(); return; }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.volume = 1.0;
        utterance.lang = config.language === Language.JA ? 'ja-JP' : 'en-US';
        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0) {
          if (config.language === Language.JA) {
            const jaVoices = voices.filter(v => v.lang.startsWith('ja'));
            if (jaVoices.length > 0) {
              const voiceMap: Record<string, number> = { founder: 1, [InvestorId.VINCENT]: 0, [InvestorId.MARCUS]: 1, [InvestorId.BEATRICE]: 2, [InvestorId.LEONA]: 3 };
              utterance.voice = jaVoices[voiceMap[speakerId] ?? 0] || jaVoices[0];
              utterance.pitch = speakerId === 'founder' ? 1.1 : speakerId === InvestorId.VINCENT ? 0.65 : speakerId === InvestorId.BEATRICE ? 1.25 : 1.0;
              utterance.rate  = speakerId === InvestorId.VINCENT ? 0.85 : speakerId === InvestorId.BEATRICE ? 0.9 : 1.05;
            }
          } else {
            const enVoices     = voices.filter(v => v.lang.startsWith('en'));
            const maleVoices   = enVoices.filter(v => v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('david') || v.name.toLowerCase().includes('google us english'));
            const femaleVoices = enVoices.filter(v => v.name.toLowerCase().includes('female') || v.name.toLowerCase().includes('zira') || v.name.toLowerCase().includes('google uk english female'));
            if      (speakerId === 'founder')           { utterance.voice = maleVoices[1]   || enVoices[0]; utterance.pitch = 1.1;  utterance.rate = 1.1; }
            else if (speakerId === InvestorId.VINCENT)  { utterance.voice = maleVoices[0]   || enVoices[0]; utterance.pitch = 0.65; utterance.rate = 0.85; }
            else if (speakerId === InvestorId.MARCUS)   { utterance.voice = maleVoices[1]   || enVoices[1] || enVoices[0]; utterance.pitch = 1.0;  utterance.rate = 1.15; }
            else if (speakerId === InvestorId.BEATRICE) { utterance.voice = femaleVoices[0] || enVoices[2] || enVoices[0]; utterance.pitch = 1.2;  utterance.rate = 0.9; }
            else if (speakerId === InvestorId.LEONA)    { utterance.voice = femaleVoices[1] || femaleVoices[0] || enVoices[3] || enVoices[0]; utterance.pitch = 1.05; utterance.rate = 1.05; }
            else                                         { utterance.voice = enVoices[0]; }
          }
        }
        setActiveSpeaker(speakerId);
        setChat(prev => prev.map(m => m.text === text ? { ...m, isAudioPlaying: true } : m));
        let isFinished = false;
        const cleanUp = () => {
          if (isFinished) return; isFinished = true;
          clearTimeout(safetyTimeout);
          if (currentToken === speechTokenRef.current) {
            setActiveSpeaker(null);
            setChat(prev => prev.map(m => m.text === text ? { ...m, isAudioPlaying: false } : m));
            resolve();
          }
        };
        utterance.onend  = cleanUp;
        utterance.onerror = cleanUp;
        const wordCount = text.split(/\s+/).length;
        const charCount = text.length;
        const rate = utterance.rate || 1.0;
        const timeoutDuration = config.language === Language.EN
          ? Math.max(5000, ((wordCount * 600) / rate) + 8000)
          : Math.max(5000, ((charCount * 350) / rate) + 8000);
        const safetyTimeout = setTimeout(() => { window.speechSynthesis.cancel(); cleanUp(); }, timeoutDuration);
        window.speechSynthesis.speak(utterance);
      }, 100);
    });
  }, [config.language, isMuted]);

  // Enqueues a chat message so text and audio advance together.
  // The next message (text + speech) only starts after the current speech finishes,
  // keeping what you see and what you hear in sync.
  // onAfter fires after speech ends (used in REAL mode to unlock the input after the
  // question is read aloud).
  const queueMessage = useCallback((
    msg: Message,
    speakerId: 'founder' | InvestorId | 'system',
    onAfter?: () => void,
  ) => {
    speechQueueRef.current = speechQueueRef.current.then(async () => {
      setChat(prev => [...prev, msg]);
      await speakText(msg.text, speakerId);
      onAfter?.();
    });
  }, [speakText]);

  // Non-spoken messages (system alerts) are also routed through the queue so they
  // appear in the right order relative to the speech happening around them.
  const queueSystemMessage = useCallback((text: string) => {
    speechQueueRef.current = speechQueueRef.current.then(() => {
      setChat(prev => [...prev, {
        id: Math.random().toString(), sender: 'system' as any, senderName: t.systemAlert,
        text, timestamp: Date.now(),
      }]);
    });
  }, [t.systemAlert]);

  // ── Speech recognition ────────────────────────────────────────────────────
  const toggleListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    if (isListening) { recognitionRef.current?.stop(); setIsListening(false); return; }
    const recognition = new SpeechRecognition();
    recognition.lang = config.language === Language.JA ? 'ja-JP' : 'en-US';
    recognition.interimResults = false;
    recognition.onresult = (e: any) => { const t = e.results[0][0].transcript; setInputText(prev => prev ? `${prev} ${t}` : t); };
    recognition.onend  = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  // ── WebSocket event handler (the new "orchestrator" on the frontend) ──────
  const handleSimEvent = useCallback((event: SimEvent) => {
    switch (event.type) {

      // Spoken messages: text appears and audio plays together, one at a time.
      case 'pitch':
      case 'founder_response':
      case 'banter':
      case 'exit_speech':
      case 'offer_speech': {
        queueMessage(
          { id: Math.random().toString(), sender: event.sender as any,
            senderName: event.senderName, text: event.text, timestamp: Date.now() },
          event.sender as any,
        );
        break;
      }

      case 'question': {
        // In REAL mode, unlock the input only after the question has been read aloud
        // so the user hears the full question before they start typing.
        queueMessage(
          { id: Math.random().toString(), sender: event.sender as any,
            senderName: event.senderName, text: event.text, timestamp: Date.now() },
          event.sender as any,
          event.waitForResponse ? () => setIsProcessing(false) : undefined,
        );
        break;
      }

      // Non-spoken: also routed through the queue so ordering is preserved.
      case 'system_message': {
        queueSystemMessage(event.text);
        break;
      }

      // State updates are immediate — no speech involved.
      case 'investor_update': {
        const invId = event.investorId as InvestorId;
        setInvestors(prev => {
          const cur = prev[invId];
          const wasAsking = cur.agentState === 'ASKING';
          const nowIdle   = event.agentState === 'IDLE' || event.agentState === 'EVALUATING';
          return {
            ...prev,
            [invId]: {
              ...cur,
              confidence:    event.confidence,
              trend:         event.trend,
              status:        event.status as InvestorStatus,
              thoughtBubble: event.thoughtBubble,
              strengths:     event.strengths,
              weaknesses:    event.weaknesses,
              risks:         event.risks,
              agentState:    event.agentState as AgentState,
              isThinking:    event.isThinking,
              questionsAsked: (wasAsking && nowIdle)
                ? cur.questionsAsked + 1
                : cur.questionsAsked,
            },
          };
        });
        break;
      }

      case 'founder_agent_state': {
        setFounderAgentState(event.state as AgentState);
        break;
      }

      case 'agent_log': {
        addAgentLog(event.agentName, event.message, event.logType as any);
        break;
      }

      case 'bargaining_start': {
        setActiveOffers(event.offers);
        setIsProcessing(false);
        break;
      }

      case 'report': {
        setReport(event.data as ReportData);
        setStep('REPORT');
        setIsProcessing(false);
        wsRef.current?.disconnect();
        break;
      }

      case 'error': {
        console.error('[ADK Simulation Error]', event.message);
        addAgentLog('Google ADK Orchestrator', `Error: ${event.message}`, 'error');
        setIsProcessing(false);
        break;
      }

      case 'disconnected':
        break;
    }
  }, [queueMessage, queueSystemMessage, addAgentLog]);

  // ── Simulation start ──────────────────────────────────────────────────────
  const handleStartSimulation = () => {
    const apiKey = vertexAIMode ? '' : (localStorage.getItem(LS_KEY) || '');
    if (!vertexAIMode && !apiKey) { setShowApiModal(true); return; }

    // Reset state
    setStep('SIMULATION');
    setChat([]);
    setCurrentRound(1);
    setIsProcessing(true);
    setFounderAgentState(AgentState.PITCHING);
    setAgentLogs([]);
    setActiveOffers([]);
    setInvestors(makeInitialInvestors());

    addAgentLog('Google ADK Orchestrator', 'Initializing 5-agent multi-agent system...', 'info');

    // Connect to the ADK backend
    const ws = new SimulationWebSocket(handleSimEvent);
    wsRef.current = ws;
    ws.connect(config, apiKey);
  };

  // ── Bargaining actions (sent to backend via WebSocket) ────────────────────
  const handleAcceptOffer = (offer: Offer) => {
    wsRef.current?.sendAcceptOffer(offer.id);
    setIsProcessing(true);
  };

  const handleCounterOffer = (counterText: string) => {
    if (!counterText.trim()) return;
    wsRef.current?.sendCounterOffer(counterText);
    setIsProcessing(true);
  };

  const handleWalkAway = () => {
    wsRef.current?.sendWalkAway();
    setIsProcessing(true);
  };

  const handleAIFounderBargainDecision = () => {
    wsRef.current?.sendAIBargain(activeOffers);
    setIsProcessing(true);
  };

  // ── REAL mode: founder submits a typed response ───────────────────────────
  const handleResponseSubmit = (text?: string) => {
    const responseText = text || inputText;
    if (!responseText.trim() || isProcessing) return;
    setInputText('');
    setIsProcessing(true);
    wsRef.current?.sendFounderResponse(responseText);
  };

  // ── AI Assist: ask backend to suggest a response for the founder ──────────
  // In the new architecture, the user can just toggle to AI mode,
  // but we keep a no-op here so SimulationScreen's prop types don't break.
  const handleAIAssist = () => {
    // No-op: backend drives everything in AI mode; REAL mode users type themselves.
  };

  // ── Restart ───────────────────────────────────────────────────────────────
  const handleRestart = () => {
    wsRef.current?.disconnect();
    wsRef.current = null;
    // Cancel any in-flight speech and drain the queue instantly.
    // Incrementing the token causes every queued speakText to short-circuit.
    window.speechSynthesis.cancel();
    speechTokenRef.current++;
    speechQueueRef.current = Promise.resolve();
    setShowRestartConfirm(false);
    setStep('SETUP');
    setChat([]);
    setReport(null);
    setInvestors(makeInitialInvestors());
    setActiveOffers([]);
    setIsProcessing(false);
    setFounderAgentState(AgentState.IDLE);
    setAgentLogs([]);
  };

  // ── Report download ───────────────────────────────────────────────────────
  const handleDownloadReport = () => {
    if (!report) return;
    const htmlContent = `<!DOCTYPE html><html><head>
<meta charset="utf-8">
<title>VC Evaluation Memo - ${config.startupName}</title>
<style>
  body { font-family: sans-serif; color: #1e293b; line-height: 1.6; padding: 40px; max-width: 800px; margin: 0 auto; }
  h1 { color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
  h2 { color: #1e3a8a; margin-top: 30px; }
  .score { font-size: 24px; font-weight: bold; color: #4f46e5; }
  .badge { display: inline-block; padding: 4px 12px; background: #e0e7ff; color: #4f46e5; border-radius: 9999px; font-size: 14px; font-weight: bold; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
  .card { border: 1px solid #e2e8f0; padding: 20px; border-radius: 12px; background: #f8fafc; }
  ul { padding-left: 20px; } li { margin-bottom: 8px; }
</style></head><body>
<h1>VC Evaluation Memo: ${config.startupName}</h1>
<p><strong>Founder:</strong> ${config.founderName} | <strong>Sector:</strong> ${config.sector}</p>
<p><strong>Original Ask:</strong> ${config.askAmount} for ${config.askEquity}% Equity</p>
<h2>Executive Summary</h2><p>${report.executiveSummary}</p>
<div class="grid">
  <div class="card"><h3>Readiness Score</h3><p class="score">${report.readinessScore} / 10</p><span class="badge">${report.verdict}</span></div>
  <div class="card"><h3>Term Sheet</h3><p>${report.agreedTermSheet
    ? `Deal with ${report.agreedTermSheet.investors.map(id => INVESTOR_PROFILES[id as InvestorId]?.name ?? id).join(' & ')} for ${report.agreedTermSheet.cash} at ${report.agreedTermSheet.equity}% equity.`
    : 'No Deal Reached'}</p></div>
</div>
<h2>Strategic Strengths</h2><ul>${(report.strengths || []).map(s => `<li>${s}</li>`).join('')}</ul>
<h2>Risk Assessment</h2><ul>${(report.risks || []).map(r => `<li><strong>[${r.weight} Risk]</strong> ${r.flag}</li>`).join('')}</ul>
<h2>Growth Roadmap</h2><ol>${(report.roadmap || []).map(s => `<li>${s.replace(/^\d+\.\s*/, '')}</li>`).join('')}</ol>
</body></html>`;
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `VC_Memo_${config.startupName.replace(/\s+/g, '_')}.html`;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">

      <Header
        step={step}
        language={config.language}
        apiConnected={apiConnected}
        isVerifyingKey={isVerifyingKey}
        title={t.title}
        subtitle={t.subtitle}
        apiActiveLabel={t.apiActive}
        apiMissingLabel={t.apiMissing}
        restartLabel={t.restart}
        onLanguageChange={handleLanguageChange}
        onOpenApiModal={() => { if (!vertexAIMode) { setApiKeyInput(''); setApiKeyError(''); setShowApiModal(true); } }}
        onRestartClick={() => setShowRestartConfirm(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 flex flex-col gap-6">

        {step === 'SETUP' && (
          <SetupScreen config={config} onChange={setConfig} onStart={handleStartSimulation} vertexAIMode={vertexAIMode} t={t} />
        )}

        {step === 'SIMULATION' && (
          <SimulationScreen
            config={config}
            investors={investors}
            founderAgentState={founderAgentState}
            agentLogs={agentLogs}
            chat={chat}
            currentRound={currentRound}
            activeSpeaker={activeSpeaker}
            isProcessing={isProcessing}
            isMuted={isMuted}
            isAutoplay={isAutoplay}
            isListening={isListening}
            inputText={inputText}
            activeOffers={activeOffers}
            chatEndRef={chatEndRef}
            onInputChange={setInputText}
            onToggleMute={() => setIsMuted(v => !v)}
            onToggleAutoplay={() => setIsAutoplay(v => !v)}
            onToggleListening={toggleListening}
            onResponseSubmit={handleResponseSubmit}
            onAIAssist={handleAIAssist}
            onAcceptOffer={handleAcceptOffer}
            onCounterOffer={handleCounterOffer}
            onWalkAway={handleWalkAway}
            onAIBargain={handleAIFounderBargainDecision}
            onSpeakText={speakText}
            t={t}
          />
        )}

        {step === 'REPORT' && report && (
          <ReportScreen
            report={report}
            config={config}
            investors={investors}
            onRestart={handleRestart}
            onDownload={handleDownloadReport}
            t={t}
          />
        )}

      </main>

      <footer className="bg-slate-950 border-t border-white/5 py-6 text-center text-xs text-slate-500 print:hidden">
        <p>© {new Date().getFullYear()} VC Shark Tank Simulator. Powered by Google ADK + Gemini 2.5 Flash.</p>
      </footer>

      <ApiKeyModal
        show={showApiModal}
        apiKeyInput={apiKeyInput}
        apiKeyError={apiKeyError}
        isVerifyingKey={isVerifyingKey}
        apiConnected={apiConnected}
        onKeyChange={(val) => { setApiKeyInput(val); setApiKeyError(''); }}
        onSave={handleSaveApiKey}
        onCancel={() => { setShowApiModal(false); setApiKeyError(''); }}
      />

      {showRestartConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">{t.restart}</h3>
            <p className="text-sm text-slate-300">{t.confirmRestart}</p>
            <div className="grid grid-cols-2 gap-3 pt-2">
              <button onClick={handleRestart} className="py-2.5 bg-red-600 hover:bg-red-500 text-white text-xs font-bold rounded-lg transition-all">{t.restart}</button>
              <button onClick={() => setShowRestartConfirm(false)} className="py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg transition-all">{t.close}</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
