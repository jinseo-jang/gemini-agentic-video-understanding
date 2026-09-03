import React from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  TrendingDown,
  TrendingUp,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import { TokenSavings, TokenUsage } from '../types';

interface SavingsCalloutProps {
  savings: TokenSavings | null;
  baselineTokens?: TokenUsage;
  agenticTokens?: TokenUsage;
}

export const SavingsCallout: React.FC<SavingsCalloutProps> = ({
  savings,
  baselineTokens,
  agenticTokens,
}) => {
  if (!savings && !baselineTokens && !agenticTokens) return null;

  const bTotal = baselineTokens?.total ?? 0;
  const aTotal = agenticTokens?.total ?? 0;
  const diff = bTotal - aTotal;

  // Case 1: Agentic consumed fewer total tokens (Savings)
  if (diff > 0 && bTotal > 0) {
    const totalPercent = Math.round((diff / bTotal) * 100);

    return (
      <div className="w-full flex justify-center -my-2 sm:-my-3 z-20 pointer-events-none">
        <div className="pointer-events-auto bg-white border-2 border-blue-500 rounded-2xl shadow-xl px-5 py-3 text-center max-w-md transition-all duration-500 animate-in fade-in zoom-in-95 hover:scale-[1.02]">
          {/* Main Badge */}
          <div className="flex items-center justify-center gap-2">
            <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
              <TrendingDown className="w-4 h-4 text-blue-600" />
            </div>
            <span className="text-xl sm:text-2xl font-black text-blue-600 tracking-tight">
              {totalPercent}% Total Token Reduction
            </span>
          </div>

          <p className="text-xs font-medium text-slate-500 mt-1">
            Using agentic video understanding
          </p>

          {/* Total Token Usage Comparison */}
          <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 font-semibold px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 shadow-sm">
              <Sparkles className="w-3 h-3 text-blue-600" />
              <span>{totalPercent}% Total Token Savings</span>
            </span>

            <span className="text-[11px] font-mono text-slate-500 flex items-center gap-1">
              <span>({bTotal.toLocaleString()}</span>
              <ArrowDownRight className="w-3 h-3 text-blue-500" />
              <span className="font-semibold text-blue-600">{aTotal.toLocaleString()} total</span>
              <span>)</span>
            </span>
          </div>

          <p className="text-[10px] text-slate-400 font-mono mt-1">
            {diff.toLocaleString()} fewer total tokens consumed vs static baseline
          </p>
        </div>
      </div>
    );
  }

  // Case 2: Agentic consumed more total tokens (e.g. exhaustive search with multiple tool loops)
  if (diff < 0 && bTotal > 0) {
    const increasePercent = Math.round((Math.abs(diff) / bTotal) * 100);

    return (
      <div className="w-full flex justify-center -my-2 sm:-my-3 z-20 pointer-events-none">
        <div className="pointer-events-auto bg-white border-2 border-amber-500 rounded-2xl shadow-xl px-5 py-3 text-center max-w-md transition-all duration-500 animate-in fade-in zoom-in-95 hover:scale-[1.02]">
          {/* Main Badge */}
          <div className="flex items-center justify-center gap-2">
            <div className="w-7 h-7 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
              <TrendingUp className="w-4 h-4 text-amber-600" />
            </div>
            <span className="text-xl sm:text-2xl font-black text-amber-600 tracking-tight">
              +{increasePercent}% Total Tokens Consumed
            </span>
          </div>

          <p className="text-xs font-medium text-slate-500 mt-1">
            Multi-turn tool calls & thoughts exceeded static baseline
          </p>

          {/* Total Token Usage Comparison */}
          <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 shadow-sm">
              <AlertTriangle className="w-3 h-3 text-amber-600" />
              <span>+{increasePercent}% Total Token Increase</span>
            </span>

            <span className="text-[11px] font-mono text-slate-500 flex items-center gap-1">
              <span>({bTotal.toLocaleString()}</span>
              <ArrowUpRight className="w-3 h-3 text-amber-500" />
              <span className="font-semibold text-amber-600">{aTotal.toLocaleString()} total</span>
              <span>)</span>
            </span>
          </div>

          <p className="text-[10px] text-slate-400 font-mono mt-1">
            {Math.abs(diff).toLocaleString()} additional total tokens consumed
          </p>
        </div>
      </div>
    );
  }

  // Case 3: Exact match or zero baseline
  return null;
};
