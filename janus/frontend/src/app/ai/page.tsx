'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Bot, User, RotateCcw, AlertCircle,
  Loader2, Send, Wrench
} from 'lucide-react'
import { useSession } from 'next-auth/react'
import { useActiveCompany } from '@/lib/tenant'
import { useI18n } from '@/lib/i18n'
import { dictionaries } from '@/locales'
import { api } from '@/lib/api'

import ValuationScenarioReport, {
  type ValuationScenarioPayload,
} from '@/components/dashboard/ValuationScenarioReport';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type OllamaStatus = 'checking' | 'online' | 'offline' | 'model_missing';

interface OllamaHealth {
  online: boolean;
  model_ready?: boolean;
  model?: string;
  hint?: string;
  error?: string;
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface ToolCall { tool: string; label: string }

interface ProposedAction {
  action: string;
  target_id: number;
  inputs: Record<string, unknown>;
  preview?: {
    success?: boolean;
    diff?: Record<string, { before: unknown; after: unknown }>;
    warnings?: string[];
    dry_run_error?: string;
  };
  next_step?: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  proposedActions?: ProposedAction[];
  valuation?: ValuationScenarioPayload;
}

interface SSEEvent {
  type: 'text' | 'tool_call' | 'error' | 'proposed_action' | 'valuation_result';
  content?: string;
  tool?: string;
  label?: string;
  message?: string;
  data?: ValuationScenarioPayload;
  // proposed_action fields
  action?: string;
  target_id?: number;
  inputs?: Record<string, unknown>;
  preview?: ProposedAction['preview'];
  next_step?: string;
}

// ── Quick questions ────────────────────────────────────────────────────────────
// ── Helpers ───────────────────────────────────────────────────────────────────
function ToolBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-[#0A2342]/10 text-[#0A2342] border border-[#0A2342]/20 px-2 py-0.5 rounded-full">
      <Wrench size={10} />
      {label.replace('...', '')}
    </span>
  );
}

function ProposedActionCard({ proposal }: { proposal: ProposedAction }) {
  const { data: session } = useSession();
  const [status, setStatus] = useState<'pending' | 'confirming' | 'confirmed' | 'cancelled' | 'error'>('pending');
  const [errorMsg, setErrorMsg] = useState('');
  const [auditId, setAuditId] = useState<number | null>(null);
  const diff = proposal.preview?.diff ?? {};
  const dryError = proposal.preview?.dry_run_error;
  const warnings = proposal.preview?.warnings ?? [];

  const handleConfirm = async () => {
    setStatus('confirming');
    setErrorMsg('');
    try {
      // O next_step do backend traz {target_type} entre placeholders; o frontend
      // resolve substituindo pelo tipo do target. Por enquanto inferimos a partir
      // do prefixo da action (heuristica simples — proximo passo: emitir target_type).
      const url = proposal.next_step?.replace('{target_type}', inferTargetType(proposal.action))
        ?? `${API}/api/v1/ontology/${inferTargetType(proposal.action)}/${proposal.target_id}/actions/${proposal.action}`;
      const fullUrl = url.startsWith('http') ? url : `${API}${url}`;
      const res = await fetch(fullUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
        },
        body: JSON.stringify({
          inputs: proposal.inputs,
          actor_type: 'ai_coordinator',
          confirmed_by: Number(session?.user?.id ?? 0),
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`HTTP ${res.status}: ${body}`);
      }
      const data = await res.json();
      setAuditId(data.audit_id ?? null);
      setStatus('confirmed');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStatus('error');
    }
  };

  return (
    <div className="border border-[#C9A959]/60 bg-[#FBF8F0] rounded-xl p-4 my-3 shadow-sm">
      <div className="flex items-center gap-2 mb-2">
        <Wrench size={14} className="text-[#C9A959]" />
        <span className="text-xs font-bold uppercase tracking-wider text-[#0A2342]">
          A&ccedil;&atilde;o proposta pela IA
        </span>
        <span className="ml-auto text-xs font-mono text-gray-500">
          {proposal.action} #{proposal.target_id}
        </span>
      </div>

      {dryError ? (
        <div className="text-xs text-red-700 bg-red-50 rounded p-2 mb-2">
          <span className="font-bold">Pr&eacute;-valida&ccedil;&atilde;o falhou:</span> {dryError}
        </div>
      ) : (
        <>
          {Object.keys(diff).length > 0 && (
            <div className="text-xs mb-2">
              <p className="font-semibold text-gray-700 mb-1">Diff (dry-run):</p>
              <table className="w-full text-xs">
                <tbody>
                  {Object.entries(diff).map(([field, change]) => (
                    <tr key={field} className="border-t border-gray-100">
                      <td className="py-1 pr-2 font-mono text-gray-600">{field}</td>
                      <td className="py-1 pr-2 text-red-600 line-through">{String(change.before)}</td>
                      <td className="py-1 pr-2 text-green-600 font-semibold">&rarr; {String(change.after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="text-xs bg-yellow-50 border border-yellow-200 rounded p-2 mb-2">
              {warnings.map((w, i) => <p key={i} className="text-yellow-900">⚠ {w}</p>)}
            </div>
          )}
        </>
      )}

      <div className="flex items-center gap-2 mt-3">
        {status === 'pending' && (
          <>
            <button
              onClick={handleConfirm}
              disabled={!!dryError}
              className="bg-[#0A2342] text-white text-xs font-bold px-3 py-1.5 rounded-md hover:bg-[#0c2d54] disabled:opacity-40"
            >
              Confirmar e executar
            </button>
            <button
              onClick={() => setStatus('cancelled')}
              className="text-xs font-semibold text-gray-600 hover:text-[#0A2342] px-3 py-1.5"
            >
              Cancelar
            </button>
          </>
        )}
        {status === 'confirming' && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Loader2 size={12} className="animate-spin" /> Executando...
          </span>
        )}
        {status === 'confirmed' && (
          <span className="text-xs text-green-700 font-bold">
            ✓ A&ccedil;&atilde;o executada{auditId ? ` (audit #${auditId})` : ''}
          </span>
        )}
        {status === 'cancelled' && (
          <span className="text-xs text-gray-500 italic">cancelada pelo usu&aacute;rio</span>
        )}
        {status === 'error' && (
          <span className="text-xs text-red-700">{errorMsg}</span>
        )}
      </div>
    </div>
  );
}

function inferTargetType(actionName: string): string {
  // Mapa simples: nomes de actions -> ObjectTypes. Atualizar quando criar novas actions.
  const map: Record<string, string> = {
    atualizarPreco: 'Produto', desativarProduto: 'Produto',
    reagendarOrdem: 'OrdemProducao', cancelarOrdem: 'OrdemProducao',
    registrarConclusao: 'OrdemProducao',
    aprovarPedido: 'PedidoVenda', aplicarDesconto: 'PedidoVenda',
  };
  return map[actionName] ?? 'Produto';
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 px-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-[#C9A959] animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function AIPage() {
  const { data: session } = useSession();
  const { companyId } = useActiveCompany();
  const { t, locale } = useI18n();
  const quick = dictionaries[locale].ai.quick;
  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState('');
  const [streaming, setStreaming] = useState(false);
  const [liveText, setLiveText]   = useState('');
  const [liveTools, setLiveTools] = useState<ToolCall[]>([]);
  const [error, setError]         = useState('');
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus>('checking');
  const [ollamaHint, setOllamaHint] = useState('');
  const bottomRef                 = useRef<HTMLDivElement>(null);
  const inputRef                  = useRef<HTMLInputElement>(null);

  const loadOllamaHealth = useCallback(async () => {
    setOllamaStatus('checking');
    try {
      const res = await api.get<OllamaHealth>('/ai/ollama/health');
      const data = res.data;
      if (!data.online) {
        setOllamaStatus('offline');
        setOllamaHint(data.hint ?? data.error ?? 'Ollama indisponivel.');
        return;
      }
      if (!data.model_ready) {
        setOllamaStatus('model_missing');
        setOllamaHint(`Modelo ${data.model ?? 'qwen3:8b'} nao encontrado. Execute: ollama pull qwen3:8b`);
        return;
      }
      setOllamaStatus('online');
      setOllamaHint('');
    } catch {
      setOllamaStatus('offline');
      setOllamaHint('Nao foi possivel verificar o Ollama. Confirme backend e Ollama Desktop.');
    }
  }, []);

  useEffect(() => {
    // loadOllamaHealth e' async; o setState inicial e' intencional (estado "checking").
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadOllamaHealth();
  }, [loadOllamaHealth]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveText, liveTools]);

  const buildHistory = () =>
    messages.map(m => ({ role: m.role, content: m.content }));

  const handleSubmit = async (question: string) => {
    if (!question.trim() || streaming) return;
    if (ollamaStatus !== 'online') {
      setError(ollamaHint || 'Ollama indisponivel. Inicie o servico antes de perguntar.');
      return;
    }
    setError('');
    setInput('');

    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setStreaming(true);
    setLiveText('');
    setLiveTools([]);

    let fullText = '';
    const toolsUsed: ToolCall[] = [];
    const proposedActions: ProposedAction[] = [];
    let valuationResult: ValuationScenarioPayload | undefined;

    try {
      const res = await fetch(`${API}/ai/coordinator`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
        },
        body: JSON.stringify({ question, history: buildHistory(), company_id: companyId, lang: locale }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('Sem stream no response');

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;

          try {
            const ev: SSEEvent = JSON.parse(raw);
            if (ev.type === 'text' && ev.content) {
              fullText += ev.content;
              setLiveText(fullText);
            } else if (ev.type === 'tool_call' && ev.tool) {
              const tc = { tool: ev.tool, label: ev.label ?? ev.tool };
              toolsUsed.push(tc);
              setLiveTools([...toolsUsed]);
            } else if (ev.type === 'proposed_action' && ev.action) {
              proposedActions.push({
                action: ev.action,
                target_id: ev.target_id ?? 0,
                inputs: ev.inputs ?? {},
                preview: ev.preview,
                next_step: ev.next_step,
              });
            } else if (ev.type === 'valuation_result' && ev.data) {
              valuationResult = ev.data;
            } else if (ev.type === 'error') {
              setError(ev.message ?? 'Erro desconhecido');
            }
          } catch { /* linha parcial, ignora */ }
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao conectar ao coordinator.');
    } finally {
      setStreaming(false);
      setLiveText('');
      setLiveTools([]);
      if (fullText || proposedActions.length > 0 || valuationResult) {
        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: fullText,
            toolCalls: toolsUsed,
            proposedActions: proposedActions.length ? proposedActions : undefined,
            valuation: valuationResult,
          },
        ]);
      }
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] max-w-4xl">

      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 pb-4 mb-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-[#0A2342]">{t('ai.title')}</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {t('ai.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {ollamaStatus === 'checking' && (
            <span className="flex items-center gap-1.5 text-xs text-gray-600 bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-full font-semibold">
              <Loader2 size={12} className="animate-spin" />
              {t('ai.checking')}
            </span>
          )}
          {ollamaStatus === 'online' && (
            <span className="flex items-center gap-1.5 text-xs text-green-700 bg-green-50 border border-green-200 px-3 py-1.5 rounded-full font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              {t('ai.online')}
            </span>
          )}
          {ollamaStatus === 'offline' && (
            <button
              type="button"
              onClick={() => void loadOllamaHealth()}
              className="flex items-center gap-1.5 text-xs text-red-700 bg-red-50 border border-red-200 px-3 py-1.5 rounded-full font-semibold hover:bg-red-100"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
              {t('ai.offlineReload')}
            </button>
          )}
          {ollamaStatus === 'model_missing' && (
            <span className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-full font-semibold">
              {t('ai.modelMissing')}
            </span>
          )}
          {messages.length > 0 && (
            <button
              onClick={() => { setMessages([]); setError(''); }}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[#0A2342] border border-gray-200 hover:border-[#0A2342] px-3 py-1.5 rounded-full transition-colors"
            >
              <RotateCcw size={12} /> {t('ai.newChat')}
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-1 min-h-0">

        {/* Empty state */}
        {messages.length === 0 && !streaming && (
          <div className="flex flex-col items-center justify-center h-full gap-8 text-center py-8">
            <div>
              <div className="w-16 h-16 rounded-full bg-[#0A2342] flex items-center justify-center mx-auto mb-4">
                <Bot size={32} className="text-[#C9A959]" />
              </div>
              <h2 className="text-lg font-bold text-[#0A2342]">{t('ai.coordinatorTitle')}</h2>
              <p className="text-gray-500 text-sm mt-1 max-w-sm">
                {t('ai.emptyHint')}
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-2xl">
              {quick.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSubmit(q)}
                  className="text-left text-sm text-gray-700 bg-white border border-gray-100 hover:border-[#C9A959] hover:bg-[#C9A959]/5 px-4 py-3 rounded-xl transition-all shadow-sm"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message history */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-[#0A2342] flex items-center justify-center shrink-0 mt-1">
                <Bot size={16} className="text-[#C9A959]" />
              </div>
            )}
            <div className="max-w-[78%]">
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {msg.toolCalls.map((tc, j) => <ToolBadge key={j} label={tc.label} />)}
                </div>
              )}
              <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-[#0A2342] text-white rounded-tr-sm'
                  : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-sm'
              }`}>
                {msg.content}
              </div>
              {msg.proposedActions && msg.proposedActions.length > 0 && (
                <div className="mt-2">
                  {msg.proposedActions.map((p, k) => (
                    <ProposedActionCard key={k} proposal={p} />
                  ))}
                </div>
              )}
              {msg.valuation && (
                <ValuationScenarioReport data={msg.valuation} compact />
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center shrink-0 mt-1">
                <User size={16} className="text-gray-600" />
              </div>
            )}
          </div>
        ))}

        {/* Live streaming */}
        {streaming && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-[#0A2342] flex items-center justify-center shrink-0 mt-1">
              <Bot size={16} className="text-[#C9A959]" />
            </div>
            <div className="max-w-[78%]">
              {liveTools.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {liveTools.map((tc, j) => <ToolBadge key={j} label={tc.label} />)}
                </div>
              )}
              <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-800 leading-relaxed">
                {liveText
                  ? <><span className="whitespace-pre-wrap">{liveText}</span><TypingDots /></>
                  : <span className="text-gray-400 flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" />
                      {liveTools.length > 0
                        ? liveTools[liveTools.length - 1].label
                        : t('ai.analyzing')}
                    </span>
                }
              </div>
            </div>
          </div>
        )}

        {/* Ollama offline */}
        {ollamaStatus !== 'online' && ollamaStatus !== 'checking' && ollamaHint && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-900">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">{t('ai.unavailable')}</p>
              <p className="mt-1">{ollamaHint}</p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
            <AlertCircle size={16} className="shrink-0" />
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="pt-4 border-t border-gray-200 mt-4 shrink-0">
        {messages.length > 0 && !streaming && (
          <div className="flex flex-wrap gap-2 mb-3">
            {quick.slice(0, 3).map((q, i) => (
              <button
                key={i}
                onClick={() => handleSubmit(q)}
                className="text-xs text-gray-500 bg-gray-50 hover:bg-gray-100 border border-gray-100 px-3 py-1.5 rounded-full transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSubmit(input)}
            placeholder={t('ai.placeholder')}
            disabled={streaming}
            className="flex-1 px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-[#0A2342] focus:border-transparent text-sm disabled:opacity-50 bg-white shadow-sm"
          />
          <button
            onClick={() => handleSubmit(input)}
            disabled={!input.trim() || streaming}
            className="w-12 h-12 rounded-xl bg-[#0A2342] text-white flex items-center justify-center hover:bg-[#0d2d57] transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm shrink-0"
          >
            {streaming
              ? <Loader2 size={18} className="animate-spin" />
              : <Send size={18} />
            }
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 text-center">
          {t('ai.footer')}
        </p>
      </div>
    </div>
  );
}
