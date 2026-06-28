/**
 * geminiService — browser-side Gemini utilities.
 *
 * All simulation AI calls (pitch, questions, evaluation, report) now run on the
 * Python backend via Google ADK agents.  This file only keeps the two functions
 * that must stay in the browser:
 *   - verifyApiKey()  — validates the key before persisting it
 *   - setApiKey()     — stores the key so verifyApiKey() can use it
 */

import { GoogleGenAI } from '@google/genai';

let runtimeApiKey: string | null = null;

export function setApiKey(key: string): void {
  runtimeApiKey = key.trim();
}

export function hasApiKey(): boolean {
  return !!runtimeApiKey;
}

export async function verifyApiKey(key: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const client = new GoogleGenAI({ apiKey: key.trim() });
    await client.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: { role: 'user', parts: [{ text: 'hi' }] },
    });
    return { ok: true };
  } catch (e: any) {
    const msg = e?.message || String(e);
    if (msg.includes('API_KEY_INVALID') || msg.includes('invalid') || msg.includes('401')) {
      return { ok: false, error: 'Invalid API key. Please check and try again.' };
    }
    if (msg.includes('quota') || msg.includes('429')) {
      return { ok: false, error: 'Quota exceeded for this key.' };
    }
    return { ok: false, error: 'Could not connect to Gemini. Check your key and internet connection.' };
  }
}
