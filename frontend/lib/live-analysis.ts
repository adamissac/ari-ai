import 'server-only';

import Anthropic from '@anthropic-ai/sdk';
import type { DemoComponent } from '@/lib/demo/data';
import { AGENT_ORDER, type AgentId, type Analysis, type DiffFile, type DiffLine } from '@/lib/demo/scenarios';
import { countLines, parsePatch, type GitHubFile } from '@/lib/live-diff';

/**
 * Live analysis of one real commit: the diff comes from GitHub, and the code review plus the
 * seven agents' reasoning come from one Claude call over that diff. Static only: nothing is
 * executed or attacked (no sandbox), proposed tests are not run, and no fix is applied. The
 * result is shaped like the demo `Analysis`, so the same commit view renders it.
 */

const MODEL = 'claude-haiku-5-5';
/** Diff text sent to the model, in characters. Larger commits are cut, and the page says so. */
const MAX_PROMPT_DIFF = 180_000;
/** USD per million tokens (input, output); unknown models use the most expensive rate. */
const PRICING: Record<string, [number, number]> = {
  'claude-haiku-5-5': [0.10, 0.50],
  'claude-sonnet-5-5': [2, 10],
  'claude-opus-5-5': [4, 20],
  'claude-fable-5-1': [10, 50],
};
const [USD_PER_MTOK_IN, USD_PER_MTOK_OUT] = PRICING[MODEL] ?? [10, 50];
const USD_PER_INPUT_TOKEN = USD_PER_MTOK_IN / 1_000_000;
const USD_PER_OUTPUT_TOKEN = USD_PER_MTOK_OUT / 1_000_000;
/** Claude Haiku has no server-side refusal fallback; the parameter is not sent for it. */
const SERVER_FALLBACK = !MODEL.startsWith('claude-haiku-');

const KINDS = ['service', 'site', 'worker', 'data', 'logging', 'identity', 'edge'] as const;
/** Analysis steps the agents may record. All are reasoning over the diff; none executes. */
const TOOLS = [
  'intel.changed_symbols', 'intel.entry_points', 'intel.call_graph', 'intel.taint', 'intel.convention', 'intel.data_classes',
  'deps.check', 'review.findings', 'record.hypothesis', 'record.attack_path', 'score.cvss', 'record.patch_candidate',
  'tests.generate', 'policy.suggest_rule', 'record.verification',
] as const;

export interface LiveCommit {
  sha: string;
  message: string;
  body: string;
  author: string;
  committedAt: string | null;
  htmlUrl: string;
  additions: number;
  deletions: number;
  files: number;
}

export interface LiveResult {
  commit: LiveCommit;
  analysis: Analysis;
  components: DemoComponent[];
  links: [string, string][];
  verdict: 'clean' | 'needs_review';
  model: string;
  truncated: boolean;
  usage: { input_tokens: number; output_tokens: number };
}

export class LiveError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) { super(message); }
}

// ------------------------------------------------------------------ GitHub

interface GitHubCommit {
  sha: string;
  html_url: string;
  commit: { message: string; author: { name: string; date: string } | null };
  author: { login: string } | null;
  stats?: { additions: number; deletions: number };
  files?: GitHubFile[];
}

async function fetchCommit(fullName: string, sha: string, signal: AbortSignal): Promise<GitHubCommit> {
  const headers: Record<string, string> = { accept: 'application/vnd.github+json', 'x-github-api-version': '2022-11-28', 'user-agent': 'ari-ai' };
  if (process.env.GITHUB_TOKEN) headers.authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  const res = await fetch(`https://api.github.com/repos/${fullName}/commits/${sha}`, { headers, signal, cache: 'no-store' });
  if (res.status === 404) throw new LiveError(404, 'NOT_FOUND', process.env.GITHUB_TOKEN ? 'GitHub could not find this commit.' : 'GitHub could not find this commit. Private repositories need GITHUB_TOKEN on the server.');
  if (res.status === 403 || res.status === 429) throw new LiveError(503, 'GITHUB_RATE_LIMITED', 'GitHub rate limit reached. Set GITHUB_TOKEN on the server or try again later.');
  if (!res.ok) throw new LiveError(502, 'GITHUB_ERROR', `GitHub returned ${res.status} for this commit.`);
  return (await res.json()) as GitHubCommit;
}

function promptDiff(files: GitHubFile[]): { text: string; truncated: boolean } {
  let text = '';
  let truncated = false;
  for (const f of files) {
    const block = `diff --git a/${f.filename} b/${f.filename}\n# status: ${f.status}, +${f.additions} -${f.deletions}\n${f.patch ?? '(no textual diff: binary or too large)'}\n\n`;
    if (text.length + block.length > MAX_PROMPT_DIFF) { truncated = true; text += `# … ${f.filename} and later files omitted (diff too large)\n`; break; }
    text += block;
  }
  return { text, truncated };
}

// ------------------------------------------------------------------ model output

const str = { type: 'string' } as const;
const obj = (properties: Record<string, unknown>) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });
const arr = (items: unknown) => ({ type: 'array', items });
const oneOf = (values: readonly string[]) => ({ type: 'string', enum: values });
const diffLine = obj({ kind: oneOf(['+', '-', ' ']), text: str });

const SCHEMA = obj({
  headline: str,
  summary: str,
  intent: str,
  review_verdict: str,
  components: arr(obj({ id: str, label: str, kind: oneOf(KINDS), critical: { type: 'boolean' } })),
  links: arr(obj({ from: str, to: str })),
  expectations: arr(obj({ id: str, text: str, source: str })),
  comments: arr(obj({ path: str, line: str, severity: oneOf(['blocker', 'major', 'note']), title: str, body: str })),
  tests: arr(obj({ name: str, expectation: str, fails_on_this_commit: { type: 'boolean' } })),
  findings: arr(obj({
    id: str, title: str, kind: oneOf(['security', 'functional']), cwe: str, severity: oneOf(['critical', 'high', 'medium', 'low']),
    cvss: str, where: str, on: oneOf(KINDS),
  })),
  false_alarms: arr(obj({ on: oneOf(KINDS), text: str })),
  agents: arr(obj({
    agent: oneOf(AGENT_ORDER.map(a => a.agent)),
    status: oneOf(['done', 'skipped']),
    outcome: str,
    evidence: arr(str),
    steps: arr(obj({ tool: oneOf(TOOLS), input: str, result: str, on: oneOf(KINDS) })),
    handoff: str,
  })),
  patch: { anyOf: [{ type: 'null' }, obj({ path: str, hunks: arr(obj({ header: str, lines: arr(diffLine) })) })] },
  guard_rule: obj({ action: str, target: str, why: str }),
});

interface ModelOutput {
  headline: string;
  summary: string;
  intent: string;
  review_verdict: string;
  components: DemoComponent[];
  links: { from: string; to: string }[];
  expectations: Analysis['review']['expectations'];
  comments: Analysis['review']['comments'];
  tests: { name: string; expectation: string; fails_on_this_commit: boolean }[];
  findings: Analysis['findings'];
  false_alarms: NonNullable<Analysis['falseAlarms']>;
  agents: { agent: AgentId; status: 'done' | 'skipped'; outcome: string; evidence: string[]; steps: { tool: string; input: string; result: string; on: string }[]; handoff: string }[];
  patch: { path: string; hunks: { header: string; lines: DiffLine[] }[] } | null;
  guard_rule: { action: string; target: string; why: string };
}

const SYSTEM = `You are ARI, an AI engineering and security team reviewing one real git commit for its owner.
You see only the commit's diff (and its message). You cannot run code, start services, send requests or run tests,
so every step you record is reasoning over the diff. Never claim that something was executed, attacked, sent, or that a test passed.

Produce, as JSON matching the schema:
- components: the 2-6 parts of the application this repository appears to contain (from paths and code), each with a kind.
  Exactly one should be the main part the commit lives in (kind "service" for a backend, "site" for a frontend). links connect component ids.
- The code review: what the change is meant to do (intent), 2-5 behavioral expectations the code should keep (source = file:line or the commit message),
  review comments anchored to real paths and line numbers from the diff (blocker = must fix before merge, major = should fix, note = tip),
  and 1-4 tests you propose (name, which expectation id it checks, and whether you expect it to fail on this commit).
- findings: only real problems you can point to in the diff (security or functional), with a CWE id (e.g. CWE-639) and a CVSS 3.1 base score as a string or "—".
  Do not invent problems to look useful: an empty list is the right answer for a clean commit. Put refuted suspicions in false_alarms.
- agents: exactly seven entries, in this order: scout, probe, trace, diagnose, patch, fortify, verify.
  scout maps what the change exposes; probe decides whether each suspicion holds up from the code; trace follows how far a confirmed problem reaches;
  diagnose names the root cause; patch proposes the smallest fix; fortify proposes a regression test and a guard rule; verify checks the proposed fix
  against the expectations and says whether a person should accept it. When nothing was confirmed, trace/diagnose/patch/fortify are "skipped"
  with a one-line outcome saying why. Each "done" agent has 1-4 steps; step input/result are short and concrete (paths, symbols, lines).
- patch: a unified-diff-style fix for the most important finding (lines with kind "+", "-" or " " context), or null when there is nothing to fix.
- headline: one plain sentence a non-engineer understands. summary: 2-3 sentences. review_verdict: one sentence.
Write plainly. Be specific to this diff.`;

// ------------------------------------------------------------------ cache

const cache = new Map<string, Promise<LiveResult>>();

/** Analyse a commit once per server instance; concurrent callers share the same run. */
export function liveAnalysis(fullName: string, sha: string): Promise<LiveResult> {
  const key = `${fullName}@${sha}`;
  let run = cache.get(key);
  if (!run) {
    run = analyse(fullName, sha);
    cache.set(key, run);
    run.catch(() => cache.delete(key));
  }
  return run;
}

async function analyse(fullName: string, sha: string): Promise<LiveResult> {
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    throw new LiveError(503, 'NOT_CONFIGURED', 'Live analysis is not configured: set ANTHROPIC_API_KEY on the server.');
  }
  const started = Date.now();
  const gh = await fetchCommit(fullName, sha, AbortSignal.timeout(20_000));
  const files = gh.files ?? [];
  const [subject = '', ...rest] = gh.commit.message.split('\n');
  const { text, truncated } = promptDiff(files);

  const client = new Anthropic();
  let message;
  try {
    const baseRequest = {
      model: MODEL,
      max_tokens: 32_000,
      ...(SERVER_FALLBACK ? { betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default' as const } : {}),
      system: SYSTEM,
      messages: [{
        role: 'user' as const,
        content: `Repository: ${fullName}\nCommit: ${gh.sha}\nAuthor: ${gh.author?.login ?? gh.commit.author?.name ?? 'unknown'}\n\nCommit message:\n${gh.commit.message}\n\nDiff${truncated ? ' (cut: the commit is larger than shown)' : ''}:\n${text || '(this commit changes no files)'}`,
      }],
    };
    try {
      message = await client.beta.messages
        .stream({ ...baseRequest, output_config: { effort: 'medium', format: { type: 'json_schema', schema: SCHEMA } } })
        .finalMessage();
    } catch (error) {
      // The full schema compiles to a grammar too large for some models (400); retry with
      // plain JSON output — the text is still JSON.parsed and shape-checked below.
      if (!(error instanceof Anthropic.APIError) || error.status !== 400) throw error;
      message = await client.beta.messages
        .stream({ ...baseRequest, output_config: { effort: 'medium' } })
        .finalMessage();
    }
  } catch (error) {
    if (error instanceof Anthropic.AuthenticationError) throw new LiveError(503, 'NOT_CONFIGURED', 'The server\'s Anthropic API key was rejected.');
    if (error instanceof Anthropic.RateLimitError) throw new LiveError(503, 'RATE_LIMITED', 'Claude is rate limited right now. Try again in a minute.');
    if (error instanceof Anthropic.APIError) throw new LiveError(502, 'MODEL_ERROR', `Claude returned an error (${error.status ?? 'network'}).`);
    throw error;
  }
  if (message.stop_reason === 'refusal') throw new LiveError(422, 'REFUSED', 'Claude declined to analyse this commit.');
  if (message.stop_reason === 'max_tokens') throw new LiveError(502, 'TRUNCATED', 'The analysis was too long and got cut off. Try again.');
  const textBlock = message.content.find(b => b.type === 'text');
  if (!textBlock || textBlock.type !== 'text') throw new LiveError(502, 'MODEL_ERROR', 'Claude returned no analysis.');
  let out: ModelOutput;
  try { out = JSON.parse(textBlock.text) as ModelOutput; } catch { throw new LiveError(502, 'MODEL_ERROR', 'Claude returned an unreadable analysis.'); }

  const usage = { input_tokens: message.usage.input_tokens, output_tokens: message.usage.output_tokens };
  const components = out.components.length ? dedupe(out.components) : [{ id: 'app', label: fullName.split('/')[1] ?? fullName, kind: 'service', critical: true }];
  if (!components.some(c => c.kind === 'service' || c.kind === 'site')) components[0] = { ...components[0]!, kind: 'service' };
  const ids = new Set(components.map(c => c.id));
  const links = out.links.filter(l => ids.has(l.from) && ids.has(l.to) && l.from !== l.to).map(l => [l.from, l.to] as [string, string]);

  const byAgent = new Map(out.agents.map(a => [a.agent, a]));
  const agents: Analysis['agents'] = AGENT_ORDER.map(role => {
    const a = byAgent.get(role.agent);
    return {
      ...role,
      status: a?.status ?? 'skipped',
      outcome: a?.outcome ?? 'No output for this agent.',
      evidence: a?.evidence ?? [],
      steps: (a?.status === 'done' ? a.steps : []).map(s => ({ tool: s.tool, input: s.input, result: s.result, ms: 0, outcome: 'ok' as const, on: s.on })),
      handoff: a?.handoff ?? '',
      seconds: 0,
      tokens: 0,
    };
  });

  const diff: DiffFile[] = files.map(parsePatch);
  const patchLines = out.patch?.hunks.flatMap(h => h.lines) ?? [];
  const patch: DiffFile | null = out.patch && patchLines.length ? { path: out.patch.path, ...countLines(patchLines), hunks: out.patch.hunks } : null;
  const seconds = Math.round((Date.now() - started) / 1000);
  const serious = out.findings.length > 0 || out.comments.some(c => c.severity === 'blocker');

  const analysis: Analysis = {
    headline: out.headline,
    summary: out.summary,
    seconds,
    usd: Math.round((usage.input_tokens * USD_PER_INPUT_TOKEN + usage.output_tokens * USD_PER_OUTPUT_TOKEN) * 100) / 100,
    findings: out.findings,
    falseAlarms: out.false_alarms,
    review: {
      intent: out.intent,
      expectations: out.expectations,
      diff,
      comments: out.comments,
      tests: out.tests.map(t => ({ name: t.name, expectation: t.expectation, before: t.fails_on_this_commit ? 'fail' : 'pass', after: 'pass' })),
      verdict: out.review_verdict,
    },
    agents,
    patch,
    // Continuous defense is not part of a commit's analysis; only Fortify's proposed guard rule is kept.
    defense: { watch: {}, checkedMinutesAgo: {}, recommendation: { ...out.guard_rule, confidence: 0 }, events: [] },
  };

  return {
    commit: {
      sha: gh.sha,
      message: subject,
      body: rest.join('\n').trim(),
      author: gh.author?.login ?? gh.commit.author?.name ?? 'unknown',
      committedAt: gh.commit.author?.date ?? null,
      htmlUrl: gh.html_url,
      additions: gh.stats?.additions ?? files.reduce((n, f) => n + f.additions, 0),
      deletions: gh.stats?.deletions ?? files.reduce((n, f) => n + f.deletions, 0),
      files: files.length,
    },
    analysis,
    components,
    links,
    verdict: serious ? 'needs_review' : 'clean',
    model: message.model,
    truncated,
    usage,
  };
}

function dedupe(components: DemoComponent[]): DemoComponent[] {
  const seen = new Set<string>();
  return components.filter(c => (seen.has(c.id) ? false : (seen.add(c.id), true)));
}
