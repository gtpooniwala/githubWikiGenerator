'use client';

import { useState } from 'react';
import { checkHealth, generateWiki } from '@/lib/api';

export function ConnectionTest() {
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [generateResult, setGenerateResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const testHealth = async () => {
    setLoading(true);
    setError(null);
    setHealthStatus(null);
    try {
      const result = await checkHealth();
      setHealthStatus(JSON.stringify(result, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Health check failed');
    } finally {
      setLoading(false);
    }
  };

  const testGenerate = async () => {
    setLoading(true);
    setError(null);
    setGenerateResult(null);
    try {
      const result = await generateWiki('https://github.com/tastejs/todomvc');
      setGenerateResult(JSON.stringify(result, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generate request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6 bg-white rounded-lg shadow-md max-w-md w-full">
      <h2 className="text-xl font-semibold text-gray-800">Backend Connection Test</h2>
      
      <div className="space-y-3">
        <button
          onClick={testHealth}
          disabled={loading}
          className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Testing...' : '1. Test Health Endpoint'}
        </button>
        
        <button
          onClick={testGenerate}
          disabled={loading}
          className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Testing...' : '2. Test Generate Endpoint'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-100 border border-red-300 rounded text-red-700">
          <strong>❌ Error:</strong> {error}
        </div>
      )}

      {healthStatus && (
        <div className="p-3 bg-green-100 border border-green-300 rounded">
          <strong className="text-green-800">✅ Health Check Passed!</strong>
          <pre className="mt-2 text-sm text-green-700 overflow-auto">
            {healthStatus}
          </pre>
        </div>
      )}

      {generateResult && (
        <div className="p-3 bg-blue-100 border border-blue-300 rounded">
          <strong className="text-blue-800">✅ Generate Response:</strong>
          <pre className="mt-2 text-sm text-blue-700 overflow-auto">
            {generateResult}
          </pre>
        </div>
      )}
    </div>
  );
}
