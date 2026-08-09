import { AgentStatus, Post, EditorialDecision, RunLog, AgentConfigRequest } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function getStatus(): Promise<AgentStatus> {
  const res = await fetch(`${API_BASE}/api/agent/status`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch agent status');
  return res.json();
}

export async function getFeed(limit = 30): Promise<{ total: number; posts: Post[] }> {
  const res = await fetch(`${API_BASE}/api/agent/feed?limit=${limit}&status=published`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch posts feed');
  return res.json();
}

export async function getDecisions(limit = 40): Promise<EditorialDecision[]> {
  const res = await fetch(`${API_BASE}/api/agent/decisions?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch editorial decisions');
  return res.json();
}

export async function getRuns(limit = 15): Promise<RunLog[]> {
  const res = await fetch(`${API_BASE}/api/agent/runs?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch run logs');
  return res.json();
}

export async function triggerCycle(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/agent/trigger`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to trigger autonomous cycle');
  return res.json();
}

export async function updatePersona(config: AgentConfigRequest): Promise<any> {
  const res = await fetch(`${API_BASE}/api/agent/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...config, force_restart: true })
  });
  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(errorData.detail || 'Failed to update agent persona');
  }
  return res.json();
}
