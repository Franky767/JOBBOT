import React, { useState, useEffect } from 'react';
import Link from 'next/link';

interface Settings {
  llm_provider: string;
  llm_model: string;
  api_key: string;
}

const modelOptions = {
  openai: [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-3.5-turbo'
  ],
  anthropic: [
    'claude-3-5-sonnet-20241022',
    'claude-3-5-haiku-20241022',
    'claude-3-opus-20240229'
  ]
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({
    llm_provider: 'openai',
    llm_model: 'gpt-4o-mini',
    api_key: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await fetch('http://localhost:8000/settings');
      const data = await response.json();
      setSettings({
        llm_provider: data.llm_provider || 'openai',
        llm_model: data.llm_model || 'gpt-4o-mini',
        api_key: '' // Never load the actual key for security
      });
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setMessage('');

    try {
      const response = await fetch('http://localhost:8000/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save settings');
      }

      setMessage('Settings saved successfully! LLM initialized with new configuration.');
    } catch (error: any) {
      console.error('Error saving settings:', error);
      setMessage(`Error: ${error.message || 'Failed to save settings. Please check the console for details.'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleProviderChange = (provider: string) => {
    const defaultModel = provider === 'openai' ? 'gpt-4o-mini' : 'claude-3-5-sonnet-20241022';
    setSettings({
      ...settings,
      llm_provider: provider,
      llm_model: defaultModel
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
            <Link href="/" className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700">
              Back to Home
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold mb-6">LLM Configuration</h2>

          {message && (
            <div className={`mb-4 p-3 rounded ${message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
              {message}
            </div>
          )}

          <div className="space-y-6">
            {/* Provider Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                LLM Provider
              </label>
              <select
                value={settings.llm_provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic (Claude)</option>
              </select>
              <p className="mt-1 text-sm text-gray-500">
                Choose your preferred LLM provider for CV parsing and application tailoring.
              </p>
            </div>

            {/* Model Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Model
              </label>
              <select
                value={settings.llm_model}
                onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {modelOptions[settings.llm_provider as keyof typeof modelOptions].map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
              <p className="mt-1 text-sm text-gray-500">
                Select the specific model to use. Recommended: {settings.llm_provider === 'openai' ? 'gpt-4o-mini' : 'claude-3-5-sonnet-20241022'} for best balance of cost and performance.
              </p>
            </div>

            {/* API Key */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                API Key
              </label>
              <input
                type="password"
                value={settings.api_key}
                onChange={(e) => setSettings({ ...settings, api_key: e.target.value })}
                placeholder={settings.llm_provider === 'openai' ? 'sk-...' : 'sk-ant-...'}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-sm text-gray-500">
                Your API key is stored securely in the local database and never transmitted.
                {settings.llm_provider === 'openai' ? (
                  <> Get your key from <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">OpenAI Platform</a>.</>
                ) : (
                  <> Get your key from <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Anthropic Console</a>.</>
                )}
              </p>
            </div>

            {/* Save Button */}
            <button
              onClick={handleSave}
              disabled={loading || !settings.api_key}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {loading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>

          {/* Info Box */}
          <div className="mt-8 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">How this works:</h3>
            <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
              <li>Choose between OpenAI or Anthropic (Claude) for LLM processing</li>
              <li>Your API key is stored locally in SQLite database</li>
              <li>The LLM is used for:
                <ul className="ml-6 mt-1 list-circle list-inside">
                  <li>Parsing CVs to extract skills and titles</li>
                  <li>Analyzing job requirements</li>
                  <li>Tailoring your CV and cover letter for each application</li>
                </ul>
              </li>
              <li>Settings persist across server restarts</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
