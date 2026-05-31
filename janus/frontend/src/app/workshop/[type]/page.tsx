'use client';

import { useEffect, useState, use } from 'react';
import Link from 'next/link';
import { ArrowLeft, Loader2, Play, Eye } from 'lucide-react';
import { api } from '@/lib/api';

interface Field {
  name: string;
  label: string;
  widget: string;
  type: string;
  required: boolean;
  readonly?: boolean;
  marking?: string | null;
  max_length?: number;
  min?: number;
  max?: number;
  options?: string[];
  hint_options?: string[];
  currency?: string;
  help?: string;
}

interface ActionDef {
  name: string;
  label: string;
  description?: string;
  inputs: Field[];
  require_confirmation: boolean;
  roles: string[];
  dry_run_supported: boolean;
}

interface FormSpec {
  object_type: string;
  title: string;
  description: string;
  title_property: string;
  fields: Field[];
  computed: Field[];
  actions: ActionDef[];
  links: { name: string; label: string; target: string; cardinality: string }[];
}

export default function WorkshopAppPage({ params }: { params: Promise<{ type: string }> }) {
  const { type } = use(params);
  const [spec, setSpec] = useState<FormSpec | null>(null);
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [activeAction, setActiveAction] = useState<ActionDef | null>(null);
  const [actionInputs, setActionInputs] = useState<Record<string, unknown>>({});
  const [targetId, setTargetId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.get(`/api/v1/ontology/workshop/forms/${type}`).then(r => setSpec(r.data));
    api.get(`/api/v1/ontology/${type}?limit=20`).then(r => setItems(r.data?.items ?? []));
  }, [type]);

  const runAction = async (dryRun: boolean) => {
    if (!activeAction || !targetId) return;
    setRunning(true);
    setResult(null);
    try {
      const url = `/api/v1/ontology/${type}/${targetId}/actions/${activeAction.name}?dry_run=${dryRun}`;
      const res = await api.post(url, { inputs: actionInputs, actor_type: 'user' });
      setResult(res.data);
    } catch (err) {
      setResult({ error: err instanceof Error ? err.message : String(err) });
    } finally { setRunning(false); }
  };

  if (!spec) return <div className="p-8"><Loader2 className="animate-spin" /></div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Link href="/workshop" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-[#0A2342]">
        <ArrowLeft size={14} /> Workshop
      </Link>
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-[#0A2342]">{spec.title}</h1>
        <p className="text-sm text-gray-500 mt-1">{spec.description}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lista */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-bold text-[#0A2342] mb-3 text-sm uppercase tracking-wider">Items</h2>
          {items.length === 0 ? (
            <p className="text-sm text-gray-400">Nenhum item.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b border-gray-100">
                  <th className="text-left py-2">ID</th>
                  <th className="text-left py-2">{spec.fields.find(f => f.name === spec.title_property)?.label ?? 'Title'}</th>
                  <th className="text-right py-2">Ações</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 font-mono text-xs">{String(it.id)}</td>
                    <td className="py-2">{String(it[spec.title_property] ?? '—')}</td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => setTargetId(Number(it.id))}
                        className={`text-xs px-2 py-1 rounded ${targetId === Number(it.id) ? 'bg-[#C9A959] text-[#0A2342]' : 'bg-gray-100 text-gray-600'}`}
                      >
                        {targetId === Number(it.id) ? 'Selecionado' : 'Selecionar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Actions */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-bold text-[#0A2342] mb-3 text-sm uppercase tracking-wider">
            Actions ({spec.actions.length})
          </h2>
          <div className="space-y-2">
            {spec.actions.map(a => (
              <button
                key={a.name}
                onClick={() => { setActiveAction(a); setActionInputs({}); setResult(null); }}
                className={`w-full text-left p-3 rounded-lg border ${activeAction?.name === a.name ? 'border-[#C9A959] bg-yellow-50' : 'border-gray-100 hover:border-gray-300'}`}
              >
                <div className="font-bold text-sm text-[#0A2342]">{a.label}</div>
                <div className="text-xs text-gray-400 mt-0.5">{a.description?.split('\n')[0]}</div>
              </button>
            ))}
          </div>

          {activeAction && targetId && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-2">
                {activeAction.label} → #{targetId}
              </h3>
              {activeAction.inputs.map(inp => (
                <div key={inp.name} className="mb-2">
                  <label className="block text-xs text-gray-500 mb-1">
                    {inp.label}{inp.required && <span className="text-red-500"> *</span>}
                  </label>
                  {inp.hint_options ? (
                    <select
                      value={String(actionInputs[inp.name] ?? '')}
                      onChange={e => setActionInputs({ ...actionInputs, [inp.name]: e.target.value })}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-sm"
                    >
                      <option value="">—</option>
                      {inp.hint_options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type={inp.widget === 'number' || inp.widget === 'currency' ? 'number' : 'text'}
                      value={String(actionInputs[inp.name] ?? '')}
                      onChange={e => setActionInputs({
                        ...actionInputs,
                        [inp.name]: inp.widget === 'number' || inp.widget === 'currency'
                          ? parseFloat(e.target.value) : e.target.value,
                      })}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-sm"
                    />
                  )}
                </div>
              ))}
              <div className="flex gap-2 mt-3">
                {activeAction.dry_run_supported && (
                  <button onClick={() => runAction(true)} disabled={running}
                    className="flex items-center gap-1 text-xs bg-gray-100 text-gray-700 px-3 py-1.5 rounded">
                    <Eye size={12} /> Dry-run
                  </button>
                )}
                <button onClick={() => runAction(false)} disabled={running}
                  className="flex items-center gap-1 text-xs bg-[#0A2342] text-white px-3 py-1.5 rounded">
                  {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                  Executar
                </button>
              </div>
            </div>
          )}

          {result && (
            <div className="mt-4 p-3 bg-gray-50 rounded text-xs">
              <pre className="whitespace-pre-wrap font-mono">{JSON.stringify(result, null, 2).slice(0, 600)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
