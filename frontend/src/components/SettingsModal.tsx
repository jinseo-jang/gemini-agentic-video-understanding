import React, { useState, useEffect } from 'react';
import { X, Key, Cloud, Check, Eye, EyeOff, ShieldCheck, RefreshCw } from 'lucide-react';
import { Credentials, ApiSettings } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiSettings: ApiSettings | null;
  savedCredentials: Credentials | null;
  onSaveCredentials: (creds: Credentials | null) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  apiSettings,
  savedCredentials,
  onSaveCredentials,
}) => {
  const [activeTab, setActiveTab] = useState<'gemini' | 'vertex'>('gemini');
  const [apiKey, setApiKey] = useState<string>('');
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [project, setProject] = useState<string>('');
  const [location, setLocation] = useState<string>('global');
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (savedCredentials) {
      if (savedCredentials.api_key) {
        setApiKey(savedCredentials.api_key);
        setActiveTab('gemini');
      }
      if (savedCredentials.project) {
        setProject(savedCredentials.project);
        setLocation(savedCredentials.location || 'global');
        if (!savedCredentials.api_key) {
          setActiveTab('vertex');
        }
      }
    } else {
      setApiKey('');
      setProject('');
      setLocation('global');
    }
  }, [savedCredentials, isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    if (activeTab === 'gemini') {
      if (apiKey.trim()) {
        onSaveCredentials({ api_key: apiKey.trim() });
      } else {
        onSaveCredentials(null);
      }
    } else {
      if (project.trim()) {
        onSaveCredentials({
          project: project.trim(),
          location: location.trim() || 'global',
        });
      } else {
        onSaveCredentials(null);
      }
    }
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 600);
  };

  const handleClear = () => {
    setApiKey('');
    setProject('');
    setLocation('global');
    onSaveCredentials(null);
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Key className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">API & Model Settings</h3>
              <p className="text-xs text-slate-500">Configure custom Gemini 3.7 credentials</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Server Status Banner */}
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-100 text-xs text-slate-600 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>
              Server Status:{' '}
              {apiSettings?.has_gemini_api_key ? (
                <strong className="text-emerald-700 font-semibold">Server Key Present</strong>
              ) : apiSettings?.has_vertex_project ? (
                <strong className="text-indigo-700 font-semibold">Vertex AI Configured</strong>
              ) : (
                <strong className="text-amber-700 font-semibold">No Default Key on Host</strong>
              )}
            </span>
          </div>
          {savedCredentials && (
            <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
              Custom Override Active
            </span>
          )}
        </div>

        {/* Mode Switch Tabs */}
        <div className="p-6">
          <div className="flex p-1 bg-slate-100 rounded-xl mb-5">
            <button
              type="button"
              onClick={() => setActiveTab('gemini')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'gemini'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <Key className="w-3.5 h-3.5" />
              <span>Gemini Developer API</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('vertex')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeTab === 'vertex'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <Cloud className="w-3.5 h-3.5" />
              <span>Google Cloud Vertex AI</span>
            </button>
          </div>

          {/* Tab Content */}
          {activeTab === 'gemini' ? (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Gemini API Key
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="AIzaSy..."
                    className="w-full px-3.5 py-2.5 text-xs font-mono border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-slate-50/50 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 p-1"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-slate-500 mt-1.5 leading-normal">
                  Obtain your key from Google AI Studio. Stored locally in your browser and used for benchmark calls.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Google Cloud Project ID
                </label>
                <input
                  type="text"
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  placeholder="e.g. my-gcp-project-123"
                  className="w-full px-3.5 py-2.5 text-xs font-mono border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-slate-50/50"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Vertex AI Location / Region
                </label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. global or us-central1"
                  className="w-full px-3.5 py-2.5 text-xs font-mono border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-slate-50/50"
                />
                <p className="text-[11px] text-slate-500 mt-1.5 leading-normal">
                  Requires application default credentials (ADC) or service account on the host environment.
                </p>
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-between gap-3 mt-6 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={handleClear}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reset to Defaults</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={savedSuccess}
                className="flex items-center gap-1.5 px-5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.98] rounded-xl shadow-sm hover:shadow transition-all cursor-pointer"
              >
                {savedSuccess ? (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>Saved!</span>
                  </>
                ) : (
                  <span>Apply Settings</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
