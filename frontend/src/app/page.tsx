'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AgentStatus, Post, EditorialDecision, RunLog, AgentConfigRequest } from '../lib/types';
import { getStatus, getFeed, getDecisions, getRuns, triggerCycle, updatePersona } from '../lib/api';

export default function DashboardPage() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [decisions, setDecisions] = useState<EditorialDecision[]>([]);
  const [runs, setRuns] = useState<RunLog[]>([]);
  const [activeTab, setActiveTab] = useState<'feed' | 'rejected' | 'decisions' | 'runs'>('feed');
  const [decisionFilter, setDecisionFilter] = useState<'all' | 'approved' | 'rejected'>('all');
  
  // Auto-refresh state
  const [refreshInterval, setRefreshInterval] = useState<number>(10000);
  const [countdown, setCountdown] = useState<number>(10);
  const [isTriggering, setIsTriggering] = useState<boolean>(false);
  const [openDrawers, setOpenDrawers] = useState<Record<string, boolean>>({});
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Form state
  const [formState, setFormState] = useState<AgentConfigRequest>({
    persona_name: 'Dr. Nova Sterling',
    persona_bio: 'Autonomous Principal AI Researcher specializing in reasoning models, autonomous agentic loops, and open-weights intelligence.',
    topics_of_interest: ['LLMs', 'Autonomous Agents', 'Robotics', 'AI Safety', 'Open Source AI'],
    posting_interval_minutes: 15,
    tone_traits: ['analytical', 'authoritative', 'forward-looking', 'rigorous'],
    banned_topics: ['crypto speculation', 'clickbait', 'unverified rumors'],
    daily_post_cap: 12
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadAllData = useCallback(async () => {
    try {
      const [sData, fData, dData, rData] = await Promise.all([
        getStatus().catch(() => null),
        getFeed().catch(() => ({ total: 0, posts: [] })),
        getDecisions().catch(() => []),
        getRuns().catch(() => [])
      ]);
      if (sData) setStatus(sData);
      if (fData) setPosts(fData.posts);
      if (dData) setDecisions(dData);
      if (rData) setRuns(rData);
    } catch (err) {
      console.error('Data load error:', err);
    }
  }, []);

  // Polling loop
  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  useEffect(() => {
    if (refreshInterval <= 0) return;
    setCountdown(refreshInterval / 1000);

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          loadAllData();
          return refreshInterval / 1000;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [refreshInterval, loadAllData]);

  const handleManualTrigger = async () => {
    setIsTriggering(true);
    try {
      const res = await triggerCycle();
      showToast(res.message || 'Autonomous cycle executed successfully!');
      await loadAllData();
    } catch (e: any) {
      showToast(e.message || 'Cycle execution error');
    } finally {
      setIsTriggering(false);
    }
  };

  const toggleDrawer = (id: string) => {
    setOpenDrawers(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const copyPost = (text: string) => {
    navigator.clipboard.writeText(text);
    showToast('Post copied to clipboard!');
  };

  const handlePersonaSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updatePersona(formState);
      setIsModalOpen(false);
      showToast('Persona successfully updated and scheduler re-armed!');
      await loadAllData();
    } catch (err: any) {
      alert('Error updating persona: ' + err.message);
    }
  };

  const rejectedDecisions = decisions.filter(d => !d.should_publish);
  const capPct = Math.min(100, Math.round(((status?.daily_posts_today || 0) / (status?.daily_post_cap || 10)) * 100));

  return (
    <div>
      {/* Top Bar */}
      <header>
        <div className="header-container">
          <div className="logo-group">
            <div className="logo-icon">⚡</div>
            <div>
              <h1 className="logo-title">Autonomous AI Creator</h1>
              <div className="logo-subtitle">Continuous Ingestion • Editorial Scoring • Autonomous Synthesis</div>
            </div>
          </div>

          <div className="header-controls">
            <div className="stat-pill" title="Scheduler Pulse">
              <div className="pulse-dot" style={{ background: status?.scheduler_running ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}></div>
              <span>{status?.scheduler_running ? 'Scheduler: Armed & Running' : 'Scheduler: Idle'}</span>
            </div>

            <div className="auto-refresh-group">
              <label className="control-label">Auto-Refresh:</label>
              <select 
                className="dropdown-select"
                value={refreshInterval} 
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
              >
                <option value={5000}>Every 5s</option>
                <option value={10000}>Every 10s</option>
                <option value={30000}>Every 30s</option>
                <option value={0}>Paused</option>
              </select>
              <span className="refresh-countdown">{refreshInterval > 0 ? `${countdown}s` : 'Paused'}</span>
            </div>

            <button className="btn-secondary" onClick={() => setIsModalOpen(true)}>
              <span>⚙️</span> Edit Persona
            </button>

            <button className="btn-trigger" onClick={handleManualTrigger} disabled={isTriggering}>
              <span>{isTriggering ? '⏳' : '⚡'}</span>
              <span>{isTriggering ? 'Running Cycle...' : 'Run Cycle Now'}</span>
            </button>
          </div>
        </div>
      </header>

      <div className="dashboard-wrapper">
        {/* KPI Grid */}
        <section className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-header">
              <span className="kpi-label">Published Posts</span>
              <span className="kpi-icon">📝</span>
            </div>
            <div className="kpi-value">{status?.total_posts_published || posts.length}</div>
            <div className="kpi-subtext">Velocity: {status?.daily_posts_today || 0} today</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <span className="kpi-label">Editorial Decisions</span>
              <span className="kpi-icon">⚖️</span>
            </div>
            <div className="kpi-value">{status?.total_decisions_made || decisions.length}</div>
            <div className="kpi-subtext">Scored & audited</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <span className="kpi-label">News Ingested</span>
              <span className="kpi-icon">📡</span>
            </div>
            <div className="kpi-value">{status?.total_news_items_ingested || 30}</div>
            <div className="kpi-subtext">Multi-source discovery</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <span className="kpi-label">Daily Publication Cap</span>
              <span className="kpi-icon">🛡️</span>
            </div>
            <div className="kpi-value">{status?.daily_posts_today || 0} / {status?.daily_post_cap || 10}</div>
            <div className="cap-progress-bar">
              <div className="cap-progress-fill" style={{ width: `${capPct}%` }}></div>
            </div>
          </div>
        </section>

        {/* Main 2-Column Section */}
        <main className="main-layout">
          
          {/* Left Column: Persona Details */}
          <aside className="sidebar">
            <div className="card persona-card">
              <div className="persona-header">
                <div className="persona-avatar">
                  {status?.persona_name ? status.persona_name.charAt(0).toUpperCase() : 'A'}
                </div>
                <div style={{ flex: 1 }}>
                  <div className="persona-name">{status?.persona_name || formState.persona_name}</div>
                  <span className="persona-badge">Active & Armed</span>
                </div>
              </div>

              <p className="persona-bio">{formState.persona_bio}</p>

              <div className="section-divider"></div>

              <div className="section-label">🎯 Topics of Interest</div>
              <div className="tag-cloud">
                {formState.topics_of_interest.map((t, idx) => (
                  <span key={idx} className="tag">{t}</span>
                ))}
              </div>

              <div className="section-label">🎨 Tone & Style Traits</div>
              <div className="tag-cloud">
                {formState.tone_traits.map((trait, idx) => (
                  <span key={idx} className="tag tone">{trait}</span>
                ))}
              </div>

              <div className="section-label">🚫 Banned Guardrails</div>
              <div className="tag-cloud">
                {formState.banned_topics.map((b, idx) => (
                  <span key={idx} className="tag banned">{b}</span>
                ))}
              </div>

              <div className="section-divider"></div>

              <div className="scheduler-meta">
                <div className="meta-row">
                  <span>Tick Frequency:</span>
                  <strong>{status?.posting_interval_minutes || 15} min</strong>
                </div>
                <div className="meta-row">
                  <span>Next Run:</span>
                  <strong>{status?.next_scheduled_run ? new Date(status.next_scheduled_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Active'}</strong>
                </div>
                <div className="meta-row">
                  <span>Last Cycle Status:</span>
                  <strong style={{ textTransform: 'uppercase', color: 'var(--accent-emerald)' }}>{status?.last_cycle_status || 'success'}</strong>
                </div>
              </div>
            </div>
          </aside>

          {/* Right Column: Feeds, Decisions, Rejected Topics */}
          <section className="content-area">
            
            <div className="tab-container">
              <button 
                className={`tab-btn ${activeTab === 'feed' ? 'active' : ''}`}
                onClick={() => setActiveTab('feed')}
              >
                📰 Latest Posts ({posts.length})
              </button>
              <button 
                className={`tab-btn ${activeTab === 'rejected' ? 'active' : ''}`}
                onClick={() => setActiveTab('rejected')}
              >
                🚫 Rejected Topics ({rejectedDecisions.length})
              </button>
              <button 
                className={`tab-btn ${activeTab === 'decisions' ? 'active' : ''}`}
                onClick={() => setActiveTab('decisions')}
              >
                ⚖️ Editorial Audit ({decisions.length})
              </button>
              <button 
                className={`tab-btn ${activeTab === 'runs' ? 'active' : ''}`}
                onClick={() => setActiveTab('runs')}
              >
                📊 Cycle Telemetry ({runs.length})
              </button>
            </div>

            {/* TAB 1: Live Feed */}
            {activeTab === 'feed' && (
              <div className="feed-stream">
                {posts.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">📡</div>
                    <p>No posts published yet. Click <strong>"Run Cycle Now"</strong> to trigger discovery and synthesis!</p>
                  </div>
                ) : (
                  posts.map((p, idx) => (
                    <article key={p.id || idx} className="post-card">
                      <div className="post-meta">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontWeight: 700, color: '#f8fafc' }}>Published Take</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', background: 'rgba(16,185,129,0.12)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>Live</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                          <span>{new Date(p.published_at).toLocaleString()}</span>
                          <button className="btn-copy" onClick={() => copyPost(p.content)}>📋 Copy</button>
                        </div>
                      </div>

                      <div className="post-content">{p.content}</div>

                      <div className="post-sources">
                        {(p.sources || []).map((s, sIdx) => {
                          let domain = 'Source Link';
                          try { domain = new URL(s).hostname.replace('www.', ''); } catch (e) {}
                          return (
                            <a key={sIdx} href={s} target="_blank" rel="noopener noreferrer" className="source-link">
                              🔗 {domain}
                            </a>
                          );
                        })}
                      </div>

                      <button className="rationale-toggle" onClick={() => toggleDrawer(p.id)}>
                        <span>💡</span> Reason for Publishing {openDrawers[p.id] ? '▴' : '▾'}
                      </button>

                      {openDrawers[p.id] && (
                        <div className="post-rationale-box">
                          <strong>Editorial Rationale:</strong> {p.rationale}
                        </div>
                      )}
                    </article>
                  ))
                )}
              </div>
            )}

            {/* TAB 2: Rejected Topics */}
            {activeTab === 'rejected' && (
              <div>
                <div className="view-intro-banner">
                  <div>
                    <h3>🚫 Rejected Candidate Stories & Guardrail Violations</h3>
                    <p>Auditable transparency log of items rejected due to low relevance, stale recency, topic repetition, or banned keyword guardrails.</p>
                  </div>
                </div>

                <div className="decisions-stream">
                  {rejectedDecisions.length === 0 ? (
                    <div className="empty-state">
                      <div className="empty-state-icon">🛡️</div>
                      <p>No rejected candidates found.</p>
                    </div>
                  ) : (
                    rejectedDecisions.map((d, idx) => (
                      <DecisionCard key={d.id || idx} decision={d} />
                    ))
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: Editorial Audit (All Decisions) */}
            {activeTab === 'decisions' && (
              <div>
                <div className="filter-bar">
                  <span style={{ fontSize: '0.825rem', color: 'var(--text-muted)' }}>Filter Verdict:</span>
                  <button 
                    className={`filter-chip ${decisionFilter === 'all' ? 'active' : ''}`}
                    onClick={() => setDecisionFilter('all')}
                  >
                    All Decisions
                  </button>
                  <button 
                    className={`filter-chip approved ${decisionFilter === 'approved' ? 'active' : ''}`}
                    onClick={() => setDecisionFilter('approved')}
                  >
                    Approved Only
                  </button>
                  <button 
                    className={`filter-chip rejected ${decisionFilter === 'rejected' ? 'active' : ''}`}
                    onClick={() => setDecisionFilter('rejected')}
                  >
                    Rejected Only
                  </button>
                </div>

                <div className="decisions-stream">
                  {decisions
                    .filter(d => {
                      if (decisionFilter === 'approved') return d.should_publish;
                      if (decisionFilter === 'rejected') return !d.should_publish;
                      return true;
                    })
                    .map((d, idx) => (
                      <DecisionCard key={d.id || idx} decision={d} />
                    ))}
                </div>
              </div>
            )}

            {/* TAB 4: Cycle Telemetry */}
            {activeTab === 'runs' && (
              <div>
                {runs.length === 0 ? (
                  <div className="empty-state">
                    <p>No cycle run telemetry recorded yet.</p>
                  </div>
                ) : (
                  runs.map((r, idx) => (
                    <div key={r.id || idx} className="card" style={{ marginBottom: '0.85rem', fontSize: '0.85rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                        <strong style={{ color: '#fff' }}>Cycle Run ID: {r.id.substring(0, 8)}...</strong>
                        <span style={{ color: r.status === 'success' ? 'var(--accent-emerald)' : 'var(--accent-amber)', fontWeight: 700, textTransform: 'uppercase' }}>
                          {r.status}
                        </span>
                      </div>
                      <div style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>
                        Started: <strong>{new Date(r.run_started_at).toLocaleTimeString()}</strong> | 
                        Items Fetched: <strong>{r.items_fetched}</strong> | 
                        Decisions Evaluated: <strong>{r.decisions_made}</strong> | 
                        Posts Published: <strong>{r.posts_published}</strong>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

          </section>
        </main>
      </div>

      {/* Persona Edit Modal */}
      {isModalOpen && (
        <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) setIsModalOpen(false); }}>
          <div className="modal-content">
            <div className="modal-header">
              <h2>⚙️ Configure Agent Persona</h2>
              <button className="modal-close" onClick={() => setIsModalOpen(false)}>✕</button>
            </div>

            <form onSubmit={handlePersonaSave}>
              <div className="form-group">
                <label>Persona Name</label>
                <input 
                  type="text" 
                  className="form-input"
                  required
                  value={formState.persona_name}
                  onChange={e => setFormState({ ...formState, persona_name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Persona Bio & Identity</label>
                <textarea 
                  rows={3}
                  className="form-textarea"
                  required
                  value={formState.persona_bio}
                  onChange={e => setFormState({ ...formState, persona_bio: e.target.value })}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Interval (Minutes)</label>
                  <input 
                    type="number" 
                    min={1} 
                    max={1440} 
                    className="form-input"
                    value={formState.posting_interval_minutes}
                    onChange={e => setFormState({ ...formState, posting_interval_minutes: Number(e.target.value) })}
                  />
                </div>
                <div className="form-group">
                  <label>Daily Post Cap</label>
                  <input 
                    type="number" 
                    min={1} 
                    max={100} 
                    className="form-input"
                    value={formState.daily_post_cap}
                    onChange={e => setFormState({ ...formState, daily_post_cap: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Topics of Interest (comma separated)</label>
                <input 
                  type="text" 
                  className="form-input"
                  value={formState.topics_of_interest.join(', ')}
                  onChange={e => setFormState({ ...formState, topics_of_interest: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                />
              </div>

              <div className="form-group">
                <label>Tone Traits (comma separated)</label>
                <input 
                  type="text" 
                  className="form-input"
                  value={formState.tone_traits.join(', ')}
                  onChange={e => setFormState({ ...formState, tone_traits: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                />
              </div>

              <div className="form-group">
                <label>Banned Topics / Keywords (comma separated)</label>
                <input 
                  type="text" 
                  className="form-input"
                  value={formState.banned_topics.join(', ')}
                  onChange={e => setFormState({ ...formState, banned_topics: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn-trigger">
                  <span>💾</span> Save & Re-Arm Agent
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className="toast" style={{ display: 'block' }}>
          {toastMessage}
        </div>
      )}
    </div>
  );
}

function DecisionCard({ decision }: { decision: EditorialDecision }) {
  const isApp = decision.should_publish;
  const badgeClass = isApp ? 'approved' : 'rejected';
  const badgeText = isApp ? 'Approved for Synthesis' : 'Rejected';

  const relPct = Math.round(decision.relevance_score * 100);
  const novPct = Math.round(decision.novelty_score * 100);
  const recPct = Math.round(decision.recency_score * 100);
  const compPct = Math.round(decision.composite_score * 100);

  let domain = 'Source Link';
  try { if (decision.source_url) domain = new URL(decision.source_url).hostname.replace('www.', ''); } catch (e) {}

  return (
    <div className={`decision-card ${badgeClass}`}>
      <div className="decision-top">
        <div>
          <div className="decision-title">{decision.title || 'Discovered Story'}</div>
          {decision.source_url && (
            <a href={decision.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.775rem', color: 'var(--accent-cyan)', textDecoration: 'none' }}>
              🔗 {domain}
            </a>
          )}
        </div>
        <span className={`badge-status ${badgeClass}`}>{badgeText}</span>
      </div>

      <div className="score-bars">
        <div className="score-item">
          Relevance: <strong>{relPct}%</strong>
          <div className="score-progress">
            <div className={`score-fill ${relPct < 50 ? 'low' : ''}`} style={{ width: `${relPct}%` }}></div>
          </div>
        </div>

        <div className="score-item">
          Novelty: <strong>{novPct}%</strong>
          <div className="score-progress">
            <div className={`score-fill ${novPct < 50 ? 'low' : ''}`} style={{ width: `${novPct}%` }}></div>
          </div>
        </div>

        <div className="score-item">
          Recency: <strong>{recPct}%</strong>
          <div className="score-progress">
            <div className="score-fill" style={{ width: `${recPct}%` }}></div>
          </div>
        </div>

        <div className="score-item">
          Composite: <strong>{compPct}%</strong>
          <div className="score-progress">
            <div className={`score-fill ${compPct < 60 ? 'low' : ''}`} style={{ width: `${compPct}%` }}></div>
          </div>
        </div>
      </div>

      <ul className="rationale-list">
        {(decision.rationale || []).map((r, rIdx) => (
          <li key={rIdx}>{r}</li>
        ))}
      </ul>
    </div>
  );
}
