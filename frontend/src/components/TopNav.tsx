import React from 'react';
import { Settings, Sparkles, Key, Cloud } from 'lucide-react';
import { ApiSettings, Credentials } from '../types';

interface TopNavProps {
  apiSettings: ApiSettings | null;
  customCredentials: Credentials | null;
  onOpenSettings: () => void;
}

export const TopNav: React.FC<TopNavProps> = ({
  apiSettings,
  customCredentials,
  onOpenSettings,
}) => {
  // Determine API status badge
  const renderStatusBadge = () => {
    if (customCredentials?.api_key) {
      return (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-sm transition-all">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <Key className="w-3 h-3 text-emerald-600" />
          <span>Custom Key Active</span>
        </div>
      );
    }

    if (customCredentials?.project || apiSettings?.has_vertex_project) {
      return (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-sm transition-all">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
          <Cloud className="w-3 h-3 text-indigo-600" />
          <span>Vertex AI Active</span>
        </div>
      );
    }

    if (apiSettings?.has_gemini_api_key) {
      return (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200 shadow-sm transition-all">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span>Server Key Active</span>
        </div>
      );
    }

    return (
      <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shadow-sm transition-all">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
        <span>Missing Key</span>
      </div>
    );
  };

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 py-3 px-4 sm:px-6 bg-white border-b border-slate-200/90 rounded-2xl shadow-sm mb-6">
      {/* Brand Section */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-600" />
          </span>
          <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight flex items-center gap-1.5">
            <span>Gemini 3.7 Flash Video Benchmark</span>
          </h1>
        </div>

        {/* Mode Pill Badge */}
        <div className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200/80">
          <Sparkles className="w-3 h-3 text-blue-500" />
          <span>Static vs Agentic Mode</span>
        </div>
      </div>

      {/* Right Controls Section */}
      <div className="flex items-center gap-3">
        {renderStatusBadge()}

        <button
          type="button"
          onClick={onOpenSettings}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-xl shadow-sm hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 active:scale-[0.98] transition-all cursor-pointer"
          title="Configure API credentials"
        >
          <Settings className="w-3.5 h-3.5 text-slate-500" />
          <span className="hidden xs:inline">Settings</span>
        </button>
      </div>
    </header>
  );
};
