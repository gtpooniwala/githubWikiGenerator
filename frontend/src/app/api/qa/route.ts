import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { question, repo_id, commit_sha, overview_md, features } = body;

    if (!question || typeof question !== 'string' || !question.trim()) {
      return NextResponse.json({ detail: 'question is required' }, { status: 400 });
    }
    if (!overview_md) {
      return NextResponse.json({ detail: 'overview_md is required' }, { status: 400 });
    }

    const response = await fetch(`${BACKEND_URL}/api/qa`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': BACKEND_API_KEY,
      },
      body: JSON.stringify({ question, repo_id, commit_sha: commit_sha ?? '', overview_md, features: features ?? [] }),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ detail: 'Backend request failed' }, { status: 503 });
  }
}
