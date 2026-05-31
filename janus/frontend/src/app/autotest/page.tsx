'use client';

import { useState, useRef } from 'react';
import {
  ShieldAlert, CheckCircle2, XCircle, Loader2,
  BarChart3, Bot, Cpu, Database, TrendingUp,
  Clock, Zap, AlertTriangle, MessageSquare,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────
interface TestResult {
  id: string;
  name: string;
  category: string;
  status: 'running' | 'pass' | 'fail';
  duration_ms: number;
  detail: string;
}

interface Summary {
  total: number;
  passed: number;
  failed: number;
  avg_duration_ms: number;
  total_duration_ms: number;
  failures: TestResult[];
}

type RunState = 'idle' | 'running' | 'done';
type StreamTestEvent = TestResult | Summary;
type AiStreamEvent = { type?: string; content?: string };

// ── Config ─────────────────────────────────────────────────────────────────
const CATEGORY_META: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  'Sistema':         { color: 'text-blue-700',   bg: 'bg-blue-100',   icon: <Database size={13} /> },
  'Minha Empresa':   { color: 'text-indigo-700', bg: 'bg-indigo-100', icon: <BarChart3 size={13} /> },
  // Aliases legados (backend ainda pode emitir essas categorias) → mesma cor de "Minha Empresa"
  'Empresa A':       { color: 'text-indigo-700', bg: 'bg-indigo-100', icon: <BarChart3 size={13} /> },
  'Empresa B':       { color: 'text-indigo-700', bg: 'bg-indigo-100', icon: <BarChart3 size={13} /> },
  'IA Coordinator':  { color: 'text-amber-700',  bg: 'bg-amber-100',  icon: <Bot size={13} /> },
  'Demonstrações':   { color: 'text-teal-700',   bg: 'bg-teal-100',   icon: <TrendingUp size={13} /> },
};

const TOTAL_TESTS = 30; // keep in sync with autotest.py (5 sistema + 7×2 empresas + 7 ia + 4 financeiro)

// ── Sub-components ─────────────────────────────────────────────────────────
function CategoryBadge({ category }: { category: string }) {
  const m = CATEGORY_META[category] ?? { color: 'text-gray-600', bg: 'bg-gray-100', icon: <Cpu size={13} /> };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${m.color} ${m.bg}`}>
      {m.icon}
      {category}
    </span>
  );
}

function StatusIcon({ status }: { status: TestResult['status'] }) {
  if (status === 'running') return <Loader2 size={16} className="animate-spin text-blue-500 shrink-0" />;
  if (status === 'pass')    return <CheckCircle2 size={16} className="text-green-500 shrink-0" />;
  return <XCircle size={16} className="text-red-500 shrink-0" />;
}

function TestRow({ test, isNew }: { test: TestResult; isNew: boolean }) {
  return (
    <div className={`flex items-center gap-3 py-2.5 px-4 border-b border-gray-50 transition-all
      ${isNew ? 'animate-pulse bg-blue-50/40' : test.status === 'fail' ? 'bg-red-50' : 'bg-white'}
    `}>
      <StatusIcon status={test.status} />
      <span className="flex-1 text-sm text-gray-800 font-medium truncate">{test.name}</span>
      <CategoryBadge category={test.category} />
      <span className="text-xs text-gray-400 w-16 text-right shrink-0">
        {test.status === 'running' ? '...' : `${test.duration_ms} ms`}
      </span>
      {test.status === 'fail' && test.detail && (
        <span className="text-xs text-red-600 max-w-[220px] truncate" title={test.detail}>
          {test.detail}
        </span>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function AutoTestPage() {
  const [state, setState]       = useState<RunState>('idle');
  const [tests, setTests]       = useState<TestResult[]>([]);
  const [summary, setSummary]   = useState<Summary | null>(null);
  const [newIds, setNewIds]     = useState<Set<string>>(new Set());
  const [aiResult, setAiResult] = useState<string>('');
  const [aiRunning, setAiRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const API_URL  = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  const progress = summary
    ? 100
    : tests.length > 0
    ? Math.min(Math.round((tests.length / TOTAL_TESTS) * 100), 99)
    : 0;

  const handleStart = async () => {
    setState('running');
    setTests([]);
    setSummary(null);
    setAiResult('');
    setNewIds(new Set());

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch(`${API_URL}/autotest`, { signal: ctrl.signal });
      if (!res.ok || !res.body) throw new Error('Backend não respondeu');
      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') { setState('done'); break; }
          try {
            const evt = JSON.parse(raw) as StreamTestEvent & { id?: string };
            if (evt.id === '__summary__') {
              setSummary(evt as Summary);
              setState('done');
            } else {
              const result = evt as TestResult;
              setTests(prev => {
                const idx = prev.findIndex(t => t.id === result.id);
                if (idx >= 0) {
                  const next = [...prev];
                  next[idx] = result;
                  return next;
                }
                return [...prev, result];
              });
              setNewIds(prev => {
                const next = new Set(prev);
                next.add(result.id);
                setTimeout(() => setNewIds(p => { const n = new Set(p); n.delete(result.id); return n; }), 800);
                return next;
              });
            }
          } catch {}
        }
      }
    } catch (err: unknown) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setState('done');
      }
    }
  };

  const handleAiAnalysis = async () => {
    if (!summary) return;
    setAiRunning(true);
    setAiResult('');

    const failList = summary.failures.map(f => `• ${f.name}: ${f.detail}`).join('\n');
    const question = `Auto Teste concluído. Resultados:
- Total: ${summary.total} testes
- Aprovados: ${summary.passed}
- Falhou: ${summary.failed}
- Tempo médio por teste: ${summary.avg_duration_ms}ms

${summary.failed > 0 ? `Falhas detectadas:\n${failList}` : 'Nenhuma falha detectada.'}

Analise esses resultados, identifique riscos e recomende ações corretivas se necessário. /no_think`;

    try {
      const res = await fetch(`${API_URL}/ai/coordinator`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history: [] }),
      });
      if (!res.ok || !res.body) throw new Error('Coordinator não respondeu');

      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;
          try {
            const evt = JSON.parse(raw) as AiStreamEvent;
            if (evt.type === 'text') {
              setAiResult(prev => prev + evt.content);
            }
          } catch {}
        }
      }
    } catch {}
    setAiRunning(false);
  };

  const passedCount  = tests.filter(t => t.status === 'pass').length;
  const failedCount  = tests.filter(t => t.status === 'fail').length;
  const slowest      = [...tests].sort((a, b) => b.duration_ms - a.duration_ms)[0];

  return (
    <div className="space-y-8 max-w-4xl">

      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center gap-3">
          <ShieldAlert size={28} className="text-red-600" />
          <div>
            <h1 className="text-2xl font-bold text-[#0A2342]">Auto Teste do Sistema</h1>
            <p className="text-gray-500 text-sm mt-0.5">
              Verifica todos os módulos, ferramentas da IA e demonstrações financeiras em tempo real.
            </p>
          </div>
        </div>
      </div>

      {/* Launch card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex-1">
            <h2 className="font-bold text-[#0A2342] text-lg">Diagnóstico completo</h2>
            <p className="text-sm text-gray-500 mt-1">
              Executa <strong>{TOTAL_TESTS} testes</strong> cobrindo banco de dados, dashboard de Minha Empresa,
              todas as 7 ferramentas do Coordinator e módulo de demonstrações financeiras.
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              {Object.entries(CATEGORY_META).map(([cat, m]) => (
                <span key={cat} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${m.color} ${m.bg}`}>
                  {m.icon} {cat}
                </span>
              ))}
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={state === 'running'}
            className={`flex items-center gap-2 px-8 py-4 rounded-xl font-bold text-white text-base shadow-lg transition-all
              ${state === 'running'
                ? 'bg-red-400 cursor-not-allowed'
                : 'bg-red-600 hover:bg-red-700 active:scale-95'
              }`}
          >
            {state === 'running'
              ? <><Loader2 size={20} className="animate-spin" /> Testando...</>
              : <><ShieldAlert size={20} /> Iniciar Auto Teste</>
            }
          </button>
        </div>

        {/* Progress bar */}
        {(state === 'running' || state === 'done') && (
          <div className="mt-5">
            <div className="flex justify-between text-xs text-gray-400 mb-1.5">
              <span>{tests.length} / {TOTAL_TESTS} testes</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  summary?.failed ?? 0 > 0 ? 'bg-red-500' : 'bg-green-500'
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Summary stats */}
      {(state === 'running' || state === 'done') && tests.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className="text-3xl font-extrabold text-green-600">{passedCount}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Aprovados</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className={`text-3xl font-extrabold ${failedCount > 0 ? 'text-red-600' : 'text-gray-300'}`}>
              {failedCount}
            </div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Falhas</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className="text-3xl font-extrabold text-[#0A2342]">{tests.length}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Executados</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className="text-xl font-extrabold text-gray-600 flex items-center justify-center gap-1">
              <Clock size={16} />
              {slowest ? `${slowest.duration_ms}ms` : '—'}
            </div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Mais lento</div>
          </div>
        </div>
      )}

      {/* Test results list */}
      {tests.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              Resultados ({tests.length})
            </span>
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="flex items-center gap-1"><CheckCircle2 size={12} className="text-green-500" /> Aprovado</span>
              <span className="flex items-center gap-1"><XCircle size={12} className="text-red-500" /> Falha</span>
            </div>
          </div>
          <div className="max-h-[480px] overflow-y-auto divide-y divide-gray-50">
            {tests.map(t => (
              <TestRow key={t.id} test={t} isNew={newIds.has(t.id)} />
            ))}
          </div>
        </div>
      )}

      {/* Final summary + AI analysis */}
      {summary && state === 'done' && (
        <div className={`rounded-xl border-2 p-6 space-y-4 ${
          summary.failed === 0 ? 'border-green-400 bg-green-50' : 'border-red-400 bg-red-50'
        }`}>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              {summary.failed === 0
                ? <CheckCircle2 size={24} className="text-green-600" />
                : <AlertTriangle size={24} className="text-red-600" />
              }
              <div>
                <h3 className={`font-extrabold text-lg ${summary.failed === 0 ? 'text-green-800' : 'text-red-800'}`}>
                  {summary.failed === 0
                    ? 'Todos os sistemas operacionais'
                    : `${summary.failed} falha${summary.failed > 1 ? 's' : ''} detectada${summary.failed > 1 ? 's' : ''}`
                  }
                </h3>
                <p className="text-sm opacity-75">
                  {summary.passed}/{summary.total} testes aprovados ·{' '}
                  {(summary.total_duration_ms / 1000).toFixed(1)}s no total ·{' '}
                  média {summary.avg_duration_ms}ms/teste
                </p>
              </div>
            </div>

            {!aiResult && (
              <button
                onClick={handleAiAnalysis}
                disabled={aiRunning}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#0A2342] text-white rounded-lg font-bold text-sm hover:bg-[#0d2d57] transition-colors disabled:opacity-50"
              >
                {aiRunning
                  ? <><Loader2 size={16} className="animate-spin" /> Analisando...</>
                  : <><MessageSquare size={16} /> Analisar com IA</>
                }
              </button>
            )}
          </div>

          {summary.failed > 0 && (
            <div>
              <p className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2">
                Falhas detectadas
              </p>
              <ul className="space-y-1.5">
                {summary.failures.map(f => (
                  <li key={f.id} className="flex items-start gap-2 bg-white rounded-lg px-3 py-2 border border-red-200 text-sm">
                    <XCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-red-800">{f.name}</span>
                      <span className="text-red-600 ml-2 text-xs">{f.detail}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* AI analysis result */}
      {(aiRunning || aiResult) && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Bot size={18} className="text-[#C9A959]" />
            <h3 className="font-bold text-[#0A2342] text-sm uppercase tracking-wider">
              Análise da IA
            </h3>
            {aiRunning && <Loader2 size={14} className="animate-spin text-gray-400" />}
          </div>
          <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap leading-relaxed">
            {aiResult || <span className="text-gray-400 italic">Aguardando resposta do coordinator...</span>}
          </div>
        </div>
      )}

      {/* Speed note */}
      <div className="flex items-start gap-2 text-xs text-gray-400">
        <Zap size={13} className="shrink-0 mt-0.5" />
        <span>
          Os testes são executados diretamente no processo backend (sem overhead HTTP).
          As 7 ferramentas do IA Coordinator são chamadas em modo direto, sem LLM — o botão &quot;Analisar com IA&quot;
          aciona o Coordinator com os resultados consolidados.
        </span>
      </div>
    </div>
  );
}
