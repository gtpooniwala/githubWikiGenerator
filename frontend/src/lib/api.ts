// Client-side API - calls Next.js API routes (not backend directly)

export interface HealthResponse {
  status: string;
}

export interface GenerateResponse {
  repo: string;
  status: string;
  message: string;
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/health');
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

export async function generateWiki(repoUrl: string): Promise<GenerateResponse> {
  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  
  return response.json();
}
