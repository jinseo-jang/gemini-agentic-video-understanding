import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Zap, AlertCircle, Brain } from 'lucide-react';
import { ModeResult } from '../types';
import { Stopwatch } from './Stopwatch';

interface AgenticCardProps {
  result: ModeResult | null;
  isRunning: boolean;
}

export const AgenticCard: React.FC<AgenticCardProps> = ({ result, isRunning }) => {
  const totalTokens = result?.tokens?.total ?? 0;
  const promptTokens = result?.tokens?.prompt ?? 0;
  const candidatesTokens = result?.tokens?.candidates ?? 0;
  const thoughtTokens = result?.tokens?.thoughts ?? 0;
  const toolTokens = result?.tokens?.tool_use ?? 0;

  return (
    <div className="bg-white rounded-2xl border-2 border-blue-500 shadow-md p-5 sm:p-6 flex flex-col justify-between min-h-[540px] transition-all relative">
      <div>
        {/* Top Header */}
        <div className="flex items-center justify-between mb-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wider uppercase bg-blue-50 text-blue-600 border border-blue-200/90 shadow-sm">
            <Zap className="w-3 h-3 fill-blue-600" />
            AGENTIC
          </span>
          <div className="flex items-center gap-2">
            {result?.thinking_level && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-100/70 text-blue-700 border border-blue-200 uppercase font-semibold flex items-center gap-1">
                <Brain className="w-2.5 h-2.5" />
                {result.thinking_level} thinking
              </span>
            )}
            <span className="text-[11px] font-mono text-blue-600 font-medium">media_processing="agentic"</span>
          </div>
        </div>

        {/* Model Title & Subtitle */}
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">
          Gemini 3.7 Flash
        </h2>
        <p className="text-sm font-semibold text-blue-600 mt-0.5">
          with Agentic Video Understanding
        </p>

        {/* Token Metrics Section */}
        <div className="mt-5 p-4 rounded-xl bg-blue-50/40 border border-blue-200/70 flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-sm">
            <Zap className="w-5 h-5 fill-white" />
          </div>
          <div>
            <div className="flex items-baseline gap-1.5">
              {isRunning && !result ? (
                <span className="text-lg font-bold text-blue-600 animate-pulse">Calculating...</span>
              ) : (
                <span className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-mono">
                  {totalTokens.toLocaleString()}
                </span>
              )}
              <span className="text-xs font-semibold text-slate-500 uppercase">TOKENS</span>
            </div>
            <p className="text-xs font-mono text-slate-600 mt-0.5 flex flex-wrap items-center gap-1">
              <span>({promptTokens.toLocaleString()} in /</span>
              {toolTokens > 0 && (
                <span className="text-indigo-600 font-medium">
                  {toolTokens.toLocaleString()} tool /
                </span>
              )}
              {thoughtTokens > 0 && (
                <span className="text-blue-700 font-semibold">
                  {thoughtTokens.toLocaleString()} thought /
                </span>
              )}
              <span>{candidatesTokens.toLocaleString()} out)</span>
            </p>
          </div>
        </div>

        {/* Response Container */}
        <div className="bg-slate-50/60 border border-slate-200/70 rounded-xl p-4 sm:p-5 my-4 min-h-[260px] max-h-[380px] overflow-y-auto text-sm text-slate-800 leading-relaxed">
          {isRunning && !result ? (
            <div className="space-y-3 py-4 animate-pulse">
              <div className="h-4 bg-blue-200/60 rounded w-3/4" />
              <div className="h-4 bg-blue-100/60 rounded w-full" />
              <div className="h-4 bg-blue-100/60 rounded w-5/6" />
              <div className="h-4 bg-blue-200/50 rounded w-2/3" />
              <div className="h-4 bg-blue-100/40 rounded w-1/2" />
            </div>
          ) : result?.error ? (
            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Analysis Error</p>
                <p className="mt-0.5">{result.error}</p>
              </div>
            </div>
          ) : result?.text ? (
            <div className="prose prose-sm prose-slate max-w-none prose-p:my-1.5 prose-headings:my-2 prose-ul:my-1.5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {result.text}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-12 text-center">
              <Brain className="w-8 h-8 stroke-[1.5] text-blue-300 mb-2" />
              <p className="text-xs font-medium text-slate-600">Agentic video understanding response</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Autonomous targeted video frame inspection with massive token reduction</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer Timer */}
      <div className="pt-3 border-t border-slate-100">
        <Stopwatch
          isRunning={isRunning && !result}
          finalTimeSeconds={result?.execution_time_seconds}
          label="Execution Time"
        />
      </div>
    </div>
  );
};
