import React from 'react';
import { Sparkles, CheckCircle, XCircle } from 'lucide-react';

interface Props {
  show: boolean;
  apiKeyInput: string;
  apiKeyError: string;
  isVerifyingKey: boolean;
  apiConnected: boolean;
  onKeyChange: (val: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

// Blocking modal that appears on first load (or when user clicks API badge).
// User must enter and verify a real Gemini API key before accessing the app.
export default function ApiKeyModal({
  show, apiKeyInput, apiKeyError, isVerifyingKey, apiConnected,
  onKeyChange, onSave, onCancel
}: Props) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-white/10 rounded-2xl p-8 max-w-lg w-full space-y-6 shadow-2xl">

        {/* Title */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-indigo-600 to-violet-500 rounded-xl shadow-lg shadow-indigo-500/30">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Configure Gemini API Key</h3>
            <p className="text-xs text-slate-400">Required to power the AI simulation</p>
          </div>
        </div>

        {/* Instructions */}
        <div className="space-y-3 bg-slate-800/40 border border-white/5 rounded-xl p-4 text-sm text-slate-300">
          <p>To use this simulator you need a free Gemini API key:</p>
          <ol className="list-decimal list-inside space-y-1 text-slate-400 text-xs">
            <li>Go to <span className="text-indigo-400 font-mono">aistudio.google.com</span></li>
            <li>Sign in with your Google account</li>
            <li>Click <strong className="text-slate-300">"Get API key"</strong> and create a new key</li>
            <li>Paste it below</li>
          </ol>
        </div>

        {/* Key input */}
        <div className="space-y-2">
          <label className="text-xs text-slate-400 font-medium">Your Gemini API Key</label>
          <input
            type="password"
            value={apiKeyInput}
            onChange={(e) => { onKeyChange(e.target.value); }}
            onKeyDown={(e) => e.key === 'Enter' && onSave()}
            placeholder="AIza..."
            className="w-full bg-slate-800/50 border border-white/10 rounded-xl px-4 py-3 text-sm font-mono focus:outline-none focus:border-indigo-500 transition-colors"
            autoFocus
          />
          {apiKeyError && (
            <p className="text-xs text-red-400 flex items-center gap-1.5">
              <XCircle className="w-3.5 h-3.5" />
              {apiKeyError}
            </p>
          )}
          <p className="text-xs text-slate-500">
            Your key is stored only in your browser's local storage and never sent anywhere except Google's API.
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={onSave}
            disabled={isVerifyingKey}
            className="flex-1 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
          >
            {isVerifyingKey ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Verifying with Gemini...
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4" />
                Save & Continue
              </>
            )}
          </button>

          {/* Cancel only shown if a valid key is already configured */}
          {apiConnected && (
            <button
              onClick={onCancel}
              disabled={isVerifyingKey}
              className="px-4 py-3 bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-300 rounded-xl transition-all text-sm font-medium disabled:opacity-50"
            >
              Cancel
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
