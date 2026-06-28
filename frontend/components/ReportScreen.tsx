import React from 'react';
import {
  Award, FileText, ShieldAlert, CheckCircle, TrendingUp,
  RotateCcw, Printer, Download
} from 'lucide-react';
import { InvestorId, InvestorState, InvestorStatus, ReportData, SimulationConfig } from '../types';
import { INVESTOR_PROFILES } from '../constants';

interface Props {
  report: ReportData;
  config: SimulationConfig;
  investors: Record<InvestorId, InvestorState>;
  onRestart: () => void;
  onDownload: () => void;
  t: any; // translation object
}

// Post-simulation VC Evaluation Memo.
// Shows: readiness score, verdict, executive summary, agreed term sheet,
// per-shark feedback cards, risk grid, strategic strengths, and growth roadmap.
export default function ReportScreen({ report, config, investors, onRestart, onDownload, t }: Props) {
  return (
    <div id="print-report-area" className="space-y-6 animate-fade-in print:bg-white print:text-black">

      {/* ── Score card + Executive Summary ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">

        {/* Readiness score + verdict badge */}
        <div className="lg:col-span-4 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 flex flex-col items-center justify-center text-center shadow-xl relative overflow-hidden print:border-slate-300">
          <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/5 to-violet-500/5 pointer-events-none" />
          <Award className="w-12 h-12 text-indigo-400 mb-3 animate-bounce print:hidden" />
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider print:text-slate-700">
            {t.readinessScore}
          </h3>
          <div className="my-4 relative">
            <div className="absolute inset-0 bg-indigo-500/20 blur-2xl rounded-full print:hidden" />
            <span className="text-7xl font-extrabold bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent relative z-10 print:text-slate-900">
              {report.readinessScore}
            </span>
            <span className="text-xl text-slate-400 font-bold print:text-slate-600">/10</span>
          </div>
          <span className="px-4 py-1.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm font-bold rounded-full print:text-slate-900 print:border-slate-400">
            {report.verdict}
          </span>
        </div>

        {/* Executive summary + agreed term sheet */}
        <div className="lg:col-span-8 bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 flex flex-col justify-between shadow-xl print:border-slate-300">
          <div className="space-y-3">
            <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2 print:text-slate-900">
              <FileText className="w-5 h-5 text-indigo-400 print:hidden" />
              {t.executiveSummary}
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed print:text-slate-800">
              {report.executiveSummary}
            </p>
          </div>

          <div className="mt-6 pt-6 border-t border-white/5 print:border-slate-300">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 print:text-slate-700">
              {t.agreedTermSheet}
            </h4>
            {report.agreedTermSheet ? (
              <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-4 space-y-3 print:border-slate-300">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <span className="text-xs text-emerald-400 font-bold block print:text-emerald-700">DEAL SEALED</span>
                    <span className="font-bold text-slate-200 print:text-slate-900">
                      {report.agreedTermSheet.investors.map((id: string) => INVESTOR_PROFILES[id as InvestorId]?.name ?? id).join(' & ')}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-lg font-extrabold text-emerald-400 block print:text-emerald-700">
                      {report.agreedTermSheet.cash}
                    </span>
                    <span className="text-xs text-slate-400 print:text-slate-600">
                      for {report.agreedTermSheet.equity}% Equity
                    </span>
                  </div>
                </div>
                {report.agreedTermSheet.terms && (
                  <div className="bg-slate-900/60 rounded-lg px-3 py-2 text-xs text-slate-300 leading-relaxed border border-white/5 print:bg-slate-100 print:text-slate-800 print:border-slate-200">
                    {report.agreedTermSheet.terms}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-red-500/5 border border-red-500/10 rounded-xl p-4 text-center print:border-slate-300">
                <span className="text-sm font-bold text-red-400 print:text-red-700">{t.noDeal}</span>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* ── Per-shark feedback cards ── */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider print:text-slate-700">
          {t.investorPanel} Analysis
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.values(investors).map(inv => {
            const profile = INVESTOR_PROFILES[inv.id];
            const feedback = report.detailedSharkFeedback?.[inv.id] || {
              pros: 'N/A', cons: 'N/A', recommendation: 'N/A'
            };
            return (
              <div key={inv.id} className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-5 space-y-3 print:border-slate-300">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{profile.emoji}</span>
                    <h4 className="font-bold text-slate-200 print:text-slate-900">{profile.name}</h4>
                  </div>
                  <span className="text-xs font-bold text-indigo-400 print:text-slate-800">
                    Confidence: {inv.confidence}%
                  </span>
                </div>
                <div className="space-y-1 text-xs">
                  <p className="text-slate-300 print:text-slate-800">
                    <strong className="text-emerald-400 print:text-emerald-700">Pros:</strong> {feedback.pros}
                  </p>
                  <p className="text-slate-300 print:text-slate-800">
                    <strong className="text-red-400 print:text-red-700">Cons:</strong> {feedback.cons}
                  </p>
                  <p className="text-slate-300 print:text-slate-800">
                    <strong className="text-amber-400 print:text-amber-700">Recommendation:</strong> {feedback.recommendation}
                  </p>
                  <p className="text-slate-300 print:text-slate-800">
                    <strong className="text-indigo-400 print:text-indigo-700">Verdict:</strong>{' '}
                    {inv.status === InvestorStatus.OUT ? 'Out' : inv.status === InvestorStatus.INVEST ? 'Invested' : 'Interested'}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Risk grid + Strategic strengths ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-xl space-y-4 print:border-slate-300">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2 print:text-slate-700">
            <ShieldAlert className="w-4 h-4 text-red-400 print:hidden" />
            {t.riskAssessment}
          </h3>
          <div className="space-y-3">
            {report.risks.map((risk, idx) => (
              <div key={idx} className="flex items-center justify-between bg-slate-800/30 border border-white/5 rounded-xl p-3 print:border-slate-300">
                <span className="text-sm text-slate-300 print:text-slate-800">{risk.flag}</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  risk.weight === 'High'
                    ? 'bg-red-500/10 text-red-400 border border-red-500/20 print:text-red-700'
                    : risk.weight === 'Medium'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 print:text-amber-700'
                    : 'bg-blue-500/10 text-blue-400 border border-blue-500/20 print:text-blue-700'
                }`}>
                  {risk.weight}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-xl space-y-4 print:border-slate-300">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2 print:text-slate-700">
            <CheckCircle className="w-4 h-4 text-emerald-400 print:hidden" />
            {t.strategicStrengths}
          </h3>
          <div className="space-y-3">
            {report.strengths.map((strength, idx) => (
              <div key={idx} className="flex items-center gap-3 bg-slate-800/30 border border-white/5 rounded-xl p-3 print:border-slate-300">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full shrink-0 print:bg-slate-800" />
                <span className="text-sm text-slate-300 print:text-slate-800">{strength}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Actionable growth roadmap ── */}
      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-xl space-y-4 print:border-slate-300">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2 print:text-slate-700">
          <TrendingUp className="w-4 h-4 text-indigo-400 print:hidden" />
          {t.growthRoadmap}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {report.roadmap.map((stepText, idx) => (
            <div key={idx} className="flex items-start gap-3 bg-slate-800/30 border border-white/5 rounded-xl p-3 print:border-slate-300">
              <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded shrink-0 print:text-slate-800">
                {idx + 1}
              </span>
              <span className="text-sm text-slate-300 print:text-slate-800">
                {stepText.replace(/^\d+\.\s*/, '')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Export + restart controls ── */}
      <div className="flex items-center justify-end gap-4 print:hidden">
        <button
          onClick={onDownload}
          className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          Download Memo
        </button>
        <button
          onClick={() => window.print()}
          className="px-6 py-3 bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 font-semibold rounded-xl transition-all flex items-center gap-2"
        >
          <Printer className="w-4 h-4" />
          {t.printReport}
        </button>
        <button
          onClick={onRestart}
          className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/20 transition-all flex items-center gap-2"
        >
          <RotateCcw className="w-4 h-4" />
          {t.backToSetup}
        </button>
      </div>

    </div>
  );
}
