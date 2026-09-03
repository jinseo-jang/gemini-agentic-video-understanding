import React from 'react';
import { BaselineCard } from './BaselineCard';
import { AgenticCard } from './AgenticCard';
import { SavingsCallout } from './SavingsCallout';
import { ModeResult, TokenSavings } from '../types';

interface ComparisonPanelProps {
  baselineResult: ModeResult | null;
  agenticResult: ModeResult | null;
  savings: TokenSavings | null;
  isRunning: boolean;
}

export const ComparisonPanel: React.FC<ComparisonPanelProps> = ({
  baselineResult,
  agenticResult,
  savings,
  isRunning,
}) => {
  return (
    <div className="flex flex-col gap-4 relative">
      {/* Floating Savings Callout (rendered above or between cards when ready) */}
      {savings && (
        <SavingsCallout
          savings={savings}
          baselineTokens={baselineResult?.tokens}
          agenticTokens={agenticResult?.tokens}
        />
      )}

      {/* Side-by-Side Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative">
        <BaselineCard result={baselineResult} isRunning={isRunning} />
        <AgenticCard result={agenticResult} isRunning={isRunning} />
      </div>
    </div>
  );
};
