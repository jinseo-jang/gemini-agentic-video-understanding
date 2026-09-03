import React, { useEffect, useState, useRef } from 'react';
import { Clock } from 'lucide-react';

interface StopwatchProps {
  isRunning: boolean;
  finalTimeSeconds?: number | null;
  className?: string;
  showIcon?: boolean;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const Stopwatch: React.FC<StopwatchProps> = ({
  isRunning,
  finalTimeSeconds,
  className = '',
  showIcon = true,
  label = 'Execution Time',
  size = 'md'
}) => {
  const [elapsed, setElapsed] = useState<number>(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    let intervalId: number | undefined;

    if (isRunning) {
      startRef.current = performance.now();
      setElapsed(0);

      // 10Hz high-precision ticker using delta timestamps to prevent drift
      intervalId = window.setInterval(() => {
        if (startRef.current !== null) {
          const deltaMs = performance.now() - startRef.current;
          setElapsed(deltaMs / 1000);
        }
      }, 100);
    } else {
      if (finalTimeSeconds !== undefined && finalTimeSeconds !== null) {
        setElapsed(finalTimeSeconds);
      }
      startRef.current = null;
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isRunning, finalTimeSeconds]);

  // Display time: prioritize server-reported final time when available
  const displayTime = finalTimeSeconds !== undefined && finalTimeSeconds !== null && !isRunning
    ? (Number.isInteger(finalTimeSeconds) ? `${finalTimeSeconds}s` : `${finalTimeSeconds.toFixed(1)}s`)
    : (elapsed > 0 ? `${elapsed.toFixed(1)}s` : '0s');

  const textSizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base font-semibold'
  };

  return (
    <div className={`flex items-center justify-between w-full text-slate-500 ${className}`}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        {showIcon && <Clock className="w-3.5 h-3.5 text-slate-400" />}
        <span>{label}</span>
      </div>
      <div className={`font-mono font-bold text-slate-800 ${textSizes[size]}`}>
        {isRunning && (
          <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-ping mr-1.5 align-middle" />
        )}
        <span>{displayTime}</span>
      </div>
    </div>
  );
};
