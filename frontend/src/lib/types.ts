export interface Post {
  id: string;
  news_item_id?: string;
  content: string;
  rationale: string;
  sources: string[];
  status: string;
  published_at: string;
  created_at: string;
}

export interface EditorialDecision {
  id: string;
  news_item_id: string;
  title: string;
  source_url: string;
  relevance_score: number;
  novelty_score: number;
  recency_score: number;
  composite_score: number;
  should_publish: boolean;
  rationale: string[];
  decided_at: string;
}

export interface AgentStatus {
  agent_active: boolean;
  persona_name: string | null;
  scheduler_running: boolean;
  next_scheduled_run: string | null;
  posting_interval_minutes: number;
  total_posts_published: number;
  total_decisions_made: number;
  total_news_items_ingested: number;
  daily_posts_today: number;
  daily_post_cap: number;
  last_cycle_status: string | null;
  last_cycle_time: string | null;
}

export interface RunLog {
  id: string;
  run_started_at: string;
  run_ended_at: string | null;
  status: string;
  items_fetched: number;
  decisions_made: number;
  posts_published: number;
  error_message: string | null;
}

export interface AgentConfigRequest {
  persona_name: string;
  persona_bio: string;
  topics_of_interest: string[];
  posting_interval_minutes: number;
  tone_traits: string[];
  banned_topics: string[];
  daily_post_cap: number;
  force_restart?: boolean;
}
