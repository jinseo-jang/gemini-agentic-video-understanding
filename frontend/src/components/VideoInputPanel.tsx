import React, { useState } from 'react';
import {
  Play,
  Loader2,
  X,
  CheckCircle2,
  Sparkles,
  Film,
  FileVideo,
  Brain,
} from 'lucide-react';
import { ThinkingLevel, VideoPreset, VideoSourceType } from '../types';
import { VideoPlayer } from './VideoPlayer';
import { PROMPT_SUGGESTIONS } from '../data/presets';

interface VideoInputPanelProps {
  presets: VideoPreset[];
  selectedPreset: VideoPreset | null;
  onSelectPreset: (preset: VideoPreset) => void;
  videoUrl: string;
  onVideoUrlChange: (url: string, type: VideoSourceType) => void;
  videoSourceType: VideoSourceType;
  prompt: string;
  onPromptChange: (prompt: string) => void;
  thinkingLevel: ThinkingLevel;
  onThinkingLevelChange: (level: ThinkingLevel) => void;
  isRunning: boolean;
  onStartAnalysis: () => void;
  onCancelAnalysis: () => void;
}

export const VideoInputPanel: React.FC<VideoInputPanelProps> = ({
  presets,
  selectedPreset,
  onSelectPreset,
  videoUrl,
  onVideoUrlChange,
  videoSourceType,
  prompt,
  onPromptChange,
  thinkingLevel,
  onThinkingLevelChange,
  isRunning,
  onStartAnalysis,
  onCancelAnalysis,
}) => {
  const [activeTab, setActiveTab] = useState<'presets' | 'custom'>('presets');
  const [customInputUrl, setCustomInputUrl] = useState<string>('');

  const isStartDisabled = !videoUrl || !prompt.trim() || isRunning;

  const handleCustomUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customInputUrl.trim();
    if (!trimmed) return;
    const isYt = trimmed.includes('youtube.com') || trimmed.includes('youtu.be');
    onVideoUrlChange(trimmed, isYt ? 'youtube' : 'url');
  };

  const handleClearVideo = () => {
    onVideoUrlChange('', 'url');
    setCustomInputUrl('');
  };

  const suggestions = selectedPreset ? PROMPT_SUGGESTIONS[selectedPreset.id] || [] : [];

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm p-5 flex flex-col gap-4">
      {/* Section 1: Video Input Selection */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Video Input
          </label>
          <div className="flex bg-slate-100 p-0.5 rounded-lg">
            <button
              type="button"
              onClick={() => setActiveTab('presets')}
              className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all ${
                activeTab === 'presets'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Presets
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('custom')}
              className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all flex items-center gap-1.5 ${
                activeTab === 'custom'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <span>YouTube / URL</span>
            </button>
          </div>
        </div>

        {/* Presets Bar */}
        {activeTab === 'presets' ? (
          <div className="grid grid-cols-1 gap-2 mb-3">
            {presets.map((preset) => {
              const isSelected = selectedPreset?.id === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  disabled={isRunning}
                  onClick={() => onSelectPreset(preset)}
                  className={`w-full text-left p-2.5 rounded-xl border transition-all flex items-start gap-2.5 ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 bg-white'
                  }`}
                >
                  <div
                    className={`p-1.5 rounded-lg mt-0.5 ${
                      isSelected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    <Film className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800 truncate">
                        {preset.title}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {preset.size_mb} MB
                      </span>
                    </div>
                    {preset.subtitle && (
                      <p className="text-[11px] text-slate-500 truncate mt-0.5">
                        {preset.subtitle}
                      </p>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="mb-3">
            <form onSubmit={handleCustomUrlSubmit} className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={customInputUrl}
                  onChange={(e) => setCustomInputUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=... or https://..."
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none pr-8 bg-slate-50/50"
                />
                {customInputUrl && (
                  <button
                    type="button"
                    onClick={() => setCustomInputUrl('')}
                    className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <button
                type="submit"
                className="px-3 py-2 text-xs font-semibold bg-slate-900 text-white rounded-xl hover:bg-slate-800 transition-colors shrink-0 cursor-pointer"
              >
                Load
              </button>
            </form>
          </div>
        )}

        {/* Video Player Box */}
        <VideoPlayer
          videoUrl={videoUrl}
          sourceType={videoSourceType}
          title={selectedPreset?.title}
        />

        {/* Video Info Badge */}
        {videoUrl && (
          <div className="mt-2.5 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <FileVideo className="w-4 h-4 text-slate-500 shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-slate-800 truncate">
                    {selectedPreset?.filename_display || selectedPreset?.title || videoUrl}
                  </p>
                  <p className="text-[11px] text-slate-500 font-mono">
                    {selectedPreset
                      ? `${selectedPreset.size_mb} MB • ${selectedPreset.mime_type}`
                      : videoSourceType === 'youtube'
                      ? 'YouTube Stream'
                      : 'Remote MP4'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleClearVideo}
                disabled={isRunning}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-200/60 transition-colors cursor-pointer"
                title="Remove video"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200/80 px-2 py-0.5 rounded-md mt-2 w-fit">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              <span>Video ready for benchmark</span>
            </div>
          </div>
        )}
      </div>

      {/* Section 2: Prompt Input */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Prompt
          </label>
          {prompt && (
            <button
              type="button"
              onClick={() => onPromptChange('')}
              className="text-[11px] text-slate-400 hover:text-slate-600 flex items-center gap-0.5 cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Clear</span>
            </button>
          )}
        </div>

        <div className="relative border border-slate-200 rounded-xl bg-slate-50/50 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent transition-all shadow-sm">
          <textarea
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            disabled={isRunning}
            rows={3}
            placeholder="Ask a question about the video content..."
            className="w-full text-xs sm:text-sm text-slate-800 placeholder-slate-400 p-3 outline-none bg-transparent resize-none leading-relaxed"
          />
        </div>

        {/* Prompt Suggestions */}
        {suggestions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-[10px] text-slate-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-500" />
              Try:
            </span>
            {suggestions.map((s, idx) => (
              <button
                key={idx}
                type="button"
                disabled={isRunning}
                onClick={() => onPromptChange(s)}
                className="text-[10px] text-left px-2 py-0.5 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-600 hover:text-slate-900 border border-slate-200/60 transition-colors line-clamp-1 max-w-full cursor-pointer"
                title={s}
              >
                {s.length > 45 ? `${s.substring(0, 45)}...` : s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Section 2.5: Thinking Level Selector */}
      <div className="pt-1">
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Brain className="w-3.5 h-3.5 text-blue-600" />
            <span>Thinking Level (사고 강도)</span>
          </label>
          <span className="text-[11px] font-medium text-slate-500">
            {thinkingLevel === 'minimal' && '최소 사고 • 가장 빠른 속도'}
            {thinkingLevel === 'low' && '가벼운 사고 • 빠른 응답'}
            {thinkingLevel === 'medium' && '균형 잡힌 사고 • 추천'}
            {thinkingLevel === 'high' && '심층 추론 • 전수 프레임 스캔'}
          </span>
        </div>
        <div className="grid grid-cols-4 gap-1.5 p-1 bg-slate-100/90 rounded-xl border border-slate-200/70">
          {(['minimal', 'low', 'medium', 'high'] as ThinkingLevel[]).map((level) => {
            const isSelected = thinkingLevel === level;
            return (
              <button
                key={level}
                type="button"
                disabled={isRunning}
                onClick={() => onThinkingLevelChange(level)}
                className={`py-1.5 px-2 text-xs font-semibold rounded-lg capitalize transition-all cursor-pointer flex items-center justify-center gap-1 ${
                  isSelected
                    ? 'bg-white text-blue-600 shadow-sm border border-slate-200/80 font-bold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
                }`}
              >
                <span>{level}</span>
                {level === 'medium' && (
                  <span
                    className={`text-[9px] px-1 py-0.2 rounded font-normal ${
                      isSelected ? 'bg-blue-50 text-blue-600' : 'text-slate-400'
                    }`}
                  >
                    Rec
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Section 3: Start Analysis Dark Pill Button */}
      <div className="pt-2">
        {isRunning ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 py-3 px-4 rounded-xl bg-slate-900 text-white font-medium text-xs sm:text-sm shadow-md flex items-center justify-center gap-2.5">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
              <span>Benchmarking Both Modes...</span>
            </div>
            <button
              type="button"
              onClick={onCancelAnalysis}
              className="p-3 rounded-xl bg-slate-100 hover:bg-rose-50 text-slate-600 hover:text-rose-600 border border-slate-200 transition-colors cursor-pointer"
              title="Cancel benchmark"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            type="button"
            disabled={isStartDisabled}
            onClick={onStartAnalysis}
            className={`w-full py-3 px-5 rounded-xl font-medium text-xs sm:text-sm shadow-md transition-all flex items-center justify-center gap-2 ${
              isStartDisabled
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none'
                : 'bg-slate-900 hover:bg-slate-800 text-white active:scale-[0.99] cursor-pointer hover:shadow-lg'
            }`}
          >
            <Play className="w-4 h-4 fill-white" />
            <span>Start analysis</span>
          </button>
        )}
      </div>
    </div>
  );
};
