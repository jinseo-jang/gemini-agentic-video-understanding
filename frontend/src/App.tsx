import React, { useState, useEffect, useRef } from 'react';
import { TopNav } from './components/TopNav';
import { SettingsModal } from './components/SettingsModal';
import { VideoInputPanel } from './components/VideoInputPanel';
import { ComparisonPanel } from './components/ComparisonPanel';
import {
  ApiSettings,
  Credentials,
  ModeResult,
  ThinkingLevel,
  TokenSavings,
  VideoPreset,
  VideoSourceType,
} from './types';
import { DEFAULT_PRESETS } from './data/presets';
import { fetchPresets, fetchSettings, runAnalysis } from './services/api';
import { AlertTriangle, ExternalLink } from 'lucide-react';

const STORAGE_KEY = 'agentic_video_benchmark_credentials';

export const App: React.FC = () => {
  // Credentials & Settings State
  const [apiSettings, setApiSettings] = useState<ApiSettings | null>(null);
  const [customCredentials, setCustomCredentials] = useState<Credentials | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Video & Prompt Input State
  const [presets, setPresets] = useState<VideoPreset[]>(DEFAULT_PRESETS);
  const [selectedPreset, setSelectedPreset] = useState<VideoPreset | null>(DEFAULT_PRESETS[0]);
  const [videoUrl, setVideoUrl] = useState<string>(DEFAULT_PRESETS[0].video_url);
  const [videoSourceType, setVideoSourceType] = useState<VideoSourceType>('preset');
  const [prompt, setPrompt] = useState<string>(DEFAULT_PRESETS[0].default_prompt);
  const [thinkingLevel, setThinkingLevel] = useState<ThinkingLevel>('medium');

  // Benchmark Execution State
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [baselineResult, setBaselineResult] = useState<ModeResult | null>(null);
  const [agenticResult, setAgenticResult] = useState<ModeResult | null>(null);
  const [savings, setSavings] = useState<TokenSavings | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Load stored credentials from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.api_key || parsed.project) {
          setCustomCredentials(parsed);
        }
      }
    } catch {
      // ignore storage parsing error
    }
  }, []);

  // Fetch backend settings and dynamic presets
  useEffect(() => {
    let isMounted = true;

    fetchSettings()
      .then((settings) => {
        if (isMounted) setApiSettings(settings);
      })
      .catch(() => {
        // Backend may still be spinning up, keep default state
      });

    fetchPresets()
      .then((serverPresets) => {
        if (isMounted && serverPresets && serverPresets.length > 0) {
          setPresets(serverPresets);
          // If no preset selected yet, default to first server preset
          setSelectedPreset((curr) => curr || serverPresets[0]);
          if (!videoUrl) {
            setVideoUrl(serverPresets[0].video_url);
            setPrompt(serverPresets[0].default_prompt);
          }
        }
      })
      .catch(() => {
        // Fallback to DEFAULT_PRESETS
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Save credentials to localStorage
  const handleSaveCredentials = (creds: Credentials | null) => {
    setCustomCredentials(creds);
    if (creds) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(creds));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  // Preset Selection Handler
  const handleSelectPreset = (preset: VideoPreset) => {
    setSelectedPreset(preset);
    setVideoUrl(preset.video_url);
    setVideoSourceType('preset');
    setPrompt(preset.default_prompt);
    setGlobalError(null);
  };

  // Custom Video URL Change Handler
  const handleVideoUrlChange = (url: string, type: VideoSourceType) => {
    setVideoUrl(url);
    setVideoSourceType(type);
    setSelectedPreset(null);
    setGlobalError(null);
  };

  // Start Benchmark Execution
  const handleStartAnalysis = async () => {
    if (!videoUrl || !prompt.trim() || isRunning) return;

    // Reset previous run metrics
    setGlobalError(null);
    setBaselineResult(null);
    setAgenticResult(null);
    setSavings(null);
    setIsRunning(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await runAnalysis(
        {
          video_url: videoUrl,
          video_source_type: videoSourceType,
          prompt: prompt.trim(),
          thinking_level: thinkingLevel,
          credentials: customCredentials || undefined,
        },
        controller.signal
      );

      setBaselineResult(response.baseline);
      setAgenticResult(response.agentic);
      setSavings(response.savings);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setGlobalError('Benchmark cancelled by user.');
      } else {
        const errorMsg = err instanceof Error ? err.message : 'Unknown error during benchmark execution';
        setGlobalError(errorMsg);
      }
    } finally {
      setIsRunning(false);
      abortControllerRef.current = null;
    }
  };

  // Cancel Benchmark Execution
  const handleCancelAnalysis = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsRunning(false);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-between">
      <div className="max-w-[1600px] w-full mx-auto p-4 sm:p-6 lg:p-8 flex-1 flex flex-col">
        {/* Top Navigation */}
        <TopNav
          apiSettings={apiSettings}
          customCredentials={customCredentials}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />

        {/* Global Error Banner */}
        {globalError && (
          <div className="mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs sm:text-sm flex items-start gap-3 shadow-sm animate-in fade-in duration-200">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-bold">Benchmark Notice</p>
              <p className="mt-0.5 leading-relaxed">{globalError}</p>
            </div>
            <button
              type="button"
              onClick={() => setGlobalError(null)}
              className="text-rose-500 hover:text-rose-800 font-bold px-2 py-1"
            >
              ✕
            </button>
          </div>
        )}

        {/* Main Content: Two-Column Split Layout */}
        <main className="grid grid-cols-12 gap-6 items-start flex-1">
          {/* Left Column: Video & Prompt Controls */}
          <div className="col-span-12 lg:col-span-4 xl:col-span-4 sticky top-6">
            <VideoInputPanel
              presets={presets}
              selectedPreset={selectedPreset}
              onSelectPreset={handleSelectPreset}
              videoUrl={videoUrl}
              onVideoUrlChange={handleVideoUrlChange}
              videoSourceType={videoSourceType}
              prompt={prompt}
              onPromptChange={setPrompt}
              thinkingLevel={thinkingLevel}
              onThinkingLevelChange={setThinkingLevel}
              isRunning={isRunning}
              onStartAnalysis={handleStartAnalysis}
              onCancelAnalysis={handleCancelAnalysis}
            />
          </div>

          {/* Right Column: Benchmark Side-by-Side Comparison */}
          <div className="col-span-12 lg:col-span-8 xl:col-span-8">
            <ComparisonPanel
              baselineResult={baselineResult}
              agenticResult={agenticResult}
              savings={savings}
              isRunning={isRunning}
            />
          </div>
        </main>
      </div>

      {/* Footer */}
      <footer className="w-full border-t border-slate-200/80 bg-white py-4 px-6 mt-8">
        <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-500">
          <p>
            Gemini 3.7 Flash Video Understanding Benchmark • Static vs Agentic Processing
          </p>
          <a
            href="https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/video-understanding#agentic-video-processing"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium transition-colors"
          >
            <span>Google Cloud Documentation</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </footer>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        apiSettings={apiSettings}
        savedCredentials={customCredentials}
        onSaveCredentials={handleSaveCredentials}
      />
    </div>
  );
};

export default App;
