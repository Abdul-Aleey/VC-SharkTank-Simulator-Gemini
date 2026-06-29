export enum Language {
  EN = 'en',
  JA = 'ja'
}

export enum SimMode {
  REAL = 'real',
  AI = 'ai'
}

export enum Personality {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  AVERAGE = 'average',
  WEAK = 'weak',
  POOR = 'poor',
  VERY_POOR = 'very_poor'
}

export enum InvestorId {
  VINCENT = 'vincent',
  MARCUS = 'marcus',
  BEATRICE = 'beatrice',
  LEONA = 'leona'
}

export enum InvestorStatus {
  ACTIVE = 'ACTIVE',
  OUT = 'OUT',
  INVEST = 'INVEST'
}

export enum AgentState {
  IDLE = 'IDLE',
  PITCHING = 'PITCHING',
  ASKING = 'ASKING',
  EVALUATING = 'EVALUATING',
  BANTERING = 'BANTERING',
  OUT = 'OUT',
  INVESTED = 'INVESTED'
}

export interface InvestorProfile {
  id: InvestorId;
  name: string;
  emoji: string;
  color: string; // HSL color string
  focus: string;
  bio: string;
  specializations: string[];
}

export interface InvestorState {
  id: InvestorId;
  status: InvestorStatus;
  confidence: number; // 0 to 100
  trend: number; // e.g. +15 or -10
  questionsAsked: number;
  thoughtBubble: string;
  strengths: string[];
  weaknesses: string[];
  risks: string[];
  isThinking: boolean;
  agentState: AgentState;
}

export interface Message {
  id: string;
  sender: 'founder' | 'system' | InvestorId;
  senderName: string;
  text: string;
  timestamp: number;
  isAudioPlaying?: boolean;
}

export interface Offer {
  id: string;
  investors: InvestorId[];
  cash: string;
  equity: number; // percentage
  terms: string;
  isJoint: boolean;
  revised?: boolean; // true after shark counter-counters with updated terms
}

export interface SimulationConfig {
  mode: SimMode;
  model: string;
  rounds: number;
  language: Language;
  startupName: string;
  founderName: string;
  sector: string;
  askAmount: string;
  askEquity: number;
  description: string;
  personality: Personality;
  customTraits: string;
}

export interface ReportData {
  readinessScore?: number; // 1-10, averaged from all 4 investor agents; absent if all agents failed
  verdict: 'Angel' | 'Accelerator' | 'Seed' | 'Series A' | 'Institutional VC' | 'Rejected';
  executiveSummary: string;
  agreedTermSheet: Offer | null;
  risks: { flag: string; weight: 'High' | 'Medium' | 'Low' }[];
  strengths: string[];
  roadmap: string[];
  detailedSharkFeedback: Record<InvestorId, {
    readinessScore?: number;
    pros: string;
    cons: string;
    recommendation: string;
  }>;
}

export interface AgentLog {
  id: string;
  timestamp: string;
  agentName: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}