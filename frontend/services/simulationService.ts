/**
 * SimulationWebSocket — thin WebSocket client that bridges the React UI
 * to the Google ADK multi-agent backend (ws://localhost:5000/ws-simulate).
 *
 * The backend owns ALL simulation logic (orchestration, agent calls, banter, etc.).
 * This class is purely transport: send commands, receive typed events.
 */

import { SimulationConfig, Offer } from '../types';

export type SimEvent =
  | { type: 'pitch';               sender: string; senderName: string; text: string }
  | { type: 'question';            sender: string; senderName: string; text: string; waitForResponse: boolean }
  | { type: 'founder_response';    sender: string; senderName: string; text: string }
  | { type: 'banter';              sender: string; senderName: string; text: string }
  | { type: 'exit_speech';         sender: string; senderName: string; text: string }
  | { type: 'offer_speech';        sender: string; senderName: string; text: string; offer: Offer }
  | { type: 'investor_update';     investorId: string; confidence: number; trend: number;
       status: string; thoughtBubble: string; strengths: string[]; weaknesses: string[];
       risks: string[]; agentState: string; isThinking: boolean }
  | { type: 'founder_agent_state'; state: string }
  | { type: 'system_message';      text: string }
  | { type: 'bargaining_start';    offers: Offer[]; isRevision: boolean }
  | { type: 'report';              data: any }
  | { type: 'agent_log';           agentName: string; message: string; logType: string }
  | { type: 'model_update';        model: string }
  | { type: 'phase_change';        phase: string }   // "ONGOING" | "BARGAINING" | "DONE"
  | { type: 'error';               message: string }
  | { type: 'disconnected' };

// In development: http://localhost:5000
// In production:  set VITE_BACKEND_URL=https://your-service.run.app in .env
// Local dev: set VITE_BACKEND_URL=http://localhost:5000 in frontend/.env
// Production (unified): not set → uses same origin (frontend and backend are one service)
const BACKEND_BASE = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.replace(/\/$/, '')
  ?? window.location.origin;

// Convert http(s) → ws(s) for the WebSocket connection
const WS_BASE = BACKEND_BASE.replace(/^http/, 'ws');
const WS_URL  = `${WS_BASE}/ws-simulate`;

export const BACKEND_HTTP_URL = BACKEND_BASE;

export class SimulationWebSocket {
  private ws: WebSocket | null = null;
  private onEvent: (event: SimEvent) => void;

  constructor(onEvent: (event: SimEvent) => void) {
    this.onEvent = onEvent;
  }

  connect(config: SimulationConfig, apiKey: string): void {
    this.ws = new WebSocket(WS_URL);

    this.ws.onopen = () => {
      this.ws!.send(JSON.stringify({ action: 'start', config, apiKey }));
    };

    this.ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as SimEvent;
        this.onEvent(event);
      } catch {
        // ignore malformed frames
      }
    };

    this.ws.onerror = () => {
      this.onEvent({ type: 'error', message: 'WebSocket connection failed. Is the backend running?' });
    };

    this.ws.onclose = () => {
      this.onEvent({ type: 'disconnected' });
    };
  }

  sendFounderResponse(text: string): void {
    this._send({ action: 'founder_response', text });
  }

  sendSpeechDone(): void {
    this._send({ action: 'speech_done' });
  }

  sendAcceptOffer(investorId: string): void {
    this._send({ action: 'accept_offer', investorId });
  }

  sendCounterOffer(text: string, investorId?: string): void {
    this._send({ action: 'counter_offer', text, investorId });
  }

  sendWalkAway(): void {
    this._send({ action: 'walk_away' });
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  private _send(payload: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }
}
