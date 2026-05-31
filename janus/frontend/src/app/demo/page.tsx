'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import {
  Play, ChevronLeft, ChevronRight, Loader2, Download,
  TrendingDown, AlertTriangle, ShieldCheck, BarChart3,
  DollarSign, Clock, CheckCircle, XCircle, Shield,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────
interface DemoData {
  company: { id: number; name: string; sector: string };
  kpis: {
    receita_total: number; receita_liquida: number; score_juno: number;
    total_delayed: number; neg_margin_products: number;
    estimated_loss: number; high_impact_insights: number;
  };
  margin_by_product: { product: string; receita_liquida: number; custo_real: number; margem: number }[];
  delayed_orders: { order_id: number; product: string; planned_date: string; actual_date: string; status: string }[];
  insights: { type: string; message: string; impact: string; action: string }[];
  trust: { score: number; label: string; deductions: { reason: string; deduction: number }[] };
  data_issues: { type: string; severity: string; message: string; action: string }[];
  validation: { receita_total: number; total_pedidos: number; total_produtos: number; status: string };
}

// ── Config ────────────────────────────────────────────────────────────────────
const COMPANIES = [{ id: 1, label: 'Minha Empresa', sector: 'Diagnóstico multi-setorial' }];

const FLOWS = [
  { id: 'dashboard', label: 'Dashboard Executivo',    emoji: '📊', desc: 'Score, receita e margem por produto' },
  { id: 'insights',  label: 'Insights + Diagnóstico', emoji: '🔍', desc: 'Riscos detectados e plano de ação 360°' },
  { id: 'auditoria', label: 'Auditoria de Dados',     emoji: '🛡️', desc: 'Data Trust Score e confiabilidade' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n: number) { return n.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }); }

function scoreColor(s: number) {
  if (s >= 85) return { text: 'text-green-600', bg: 'bg-green-50', border: 'border-green-400', badge: 'bg-green-100 text-green-800' };
  if (s >= 70) return { text: 'text-[#C9A959]', bg: 'bg-yellow-50', border: 'border-yellow-400', badge: 'bg-yellow-100 text-yellow-800' };
  if (s >= 50) return { text: 'text-orange-500', bg: 'bg-orange-50', border: 'border-orange-400', badge: 'bg-orange-100 text-orange-800' };
  return { text: 'text-red-600', bg: 'bg-red-50', border: 'border-red-400', badge: 'bg-red-100 text-red-800' };
}

function scoreLabel(s: number) { return s >= 85 ? 'EXCELENTE' : s >= 70 ? 'BOM' : s >= 50 ? 'ATENÇÃO' : 'CRÍTICO'; }

// ── Flows ─────────────────────────────────────────────────────────────────────
function FlowDashboard({ d }: { d: DemoData }) {
  const C = scoreColor(d.kpis.score_juno);
  return (
    <div className="space-y-6">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className={`${C.bg} border-2 ${C.border} rounded-xl p-5 text-center`}>
          <div className={`text-5xl font-extrabold ${C.text}`}>{d.kpis.score_juno}</div>
          <div className="text-xs text-gray-500 mt-1">Score JUNO</div>
          <span className={`mt-2 inline-block text-xs font-bold px-2 py-0.5 rounded-full ${C.badge}`}>{scoreLabel(d.kpis.score_juno)}</span>
        </div>
        {[
          { label: 'Receita Líquida',   value: `R$ ${fmt(d.kpis.receita_liquida)}`,   icon: DollarSign,     color: 'text-[#0A2342]' },
          { label: 'Perda Estimada/mês',value: `R$ ${fmt(d.kpis.estimated_loss)}`,     icon: TrendingDown,   color: 'text-red-600' },
          { label: 'Ordens Atrasadas',  value: String(d.kpis.total_delayed),           icon: Clock,          color: 'text-orange-500' },
        ].map(k => {
          const Icon = k.icon;
          return (
            <div key={k.label} className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wider">{k.label}</p>
                  <p className={`text-xl font-extrabold mt-1 ${k.color}`}>{k.value}</p>
                </div>
                <Icon size={18} className="text-gray-200" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Margin table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-3 bg-[#0A2342] flex items-center gap-2">
          <BarChart3 size={16} className="text-[#C9A959]" />
          <span className="text-white font-bold text-sm uppercase tracking-wider">Margem por Produto</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-gray-400 uppercase tracking-wider border-b">
              <th className="text-left px-6 py-3">Produto</th>
              <th className="text-right px-6 py-3">Receita Líquida</th>
              <th className="text-right px-6 py-3">Custo Real</th>
              <th className="text-right px-6 py-3">Margem</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {d.margin_by_product.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium text-gray-800">{r.product}</td>
                  <td className="px-6 py-3 text-right text-gray-600">R$ {fmt(r.receita_liquida)}</td>
                  <td className="px-6 py-3 text-right text-gray-600">R$ {fmt(r.custo_real)}</td>
                  <td className={`px-6 py-3 text-right font-bold ${r.margem < 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {r.margem < 0 ? '▼' : '▲'} R$ {fmt(Math.abs(r.margem))}
                  </td>
                </tr>
              ))}
              {d.margin_by_product.length === 0 && (
                <tr><td colSpan={4} className="px-6 py-6 text-center text-gray-400">Sem dados de margem</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delayed orders */}
      {d.delayed_orders.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-3 bg-orange-500 flex items-center gap-2">
            <Clock size={16} className="text-white" />
            <span className="text-white font-bold text-sm uppercase tracking-wider">
              Ordens em Atraso ({d.delayed_orders.length})
            </span>
          </div>
          <ul className="divide-y divide-gray-50">
            {d.delayed_orders.slice(0, 4).map((o, i) => (
              <li key={i} className="px-6 py-3 flex items-center justify-between text-sm">
                <span className="font-medium text-gray-800">OP-{o.order_id} · {o.product}</span>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>Previsto: {o.planned_date?.slice(0, 10)}</span>
                  <span className="text-red-500 font-semibold">Real: {o.actual_date?.slice(0, 10)}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function FlowInsights({ d }: { d: DemoData }) {
  const opInsights = d.insights.filter(i => !i.type.startsWith('data_'));
  return (
    <div className="space-y-6">
      {/* Loss highlight */}
      <div className="bg-[#0A2342] rounded-xl p-6 flex items-center justify-between">
        <div>
          <p className="text-[#C9A959] text-xs font-bold uppercase tracking-widest mb-1">Impacto Financeiro Estimado</p>
          <p className="text-white text-4xl font-extrabold">R$ {fmt(d.kpis.estimated_loss)}<span className="text-lg font-normal text-gray-400">/mês</span></p>
        </div>
        <div className="text-right">
          <p className="text-gray-400 text-xs mb-1">{d.kpis.high_impact_insights} risco(s) de alto impacto</p>
          <p className="text-gray-400 text-xs">{d.kpis.neg_margin_products} produto(s) com margem negativa</p>
        </div>
      </div>

      {/* Insights */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-3 bg-[#0A2342] flex items-center gap-2">
          <AlertTriangle size={16} className="text-[#C9A959]" />
          <span className="text-white font-bold text-sm uppercase tracking-wider">Riscos Detectados</span>
        </div>
        {opInsights.length === 0 ? (
          <div className="p-8 text-center text-gray-400 flex flex-col items-center gap-2">
            <CheckCircle size={28} className="text-green-400" />
            <p>Nenhum risco operacional crítico detectado.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-50">
            {opInsights.map((ins, i) => (
              <li key={i} className="px-6 py-4 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  <AlertTriangle size={16} className={`shrink-0 mt-0.5 ${ins.impact === 'Alto' ? 'text-red-500' : 'text-yellow-500'}`} />
                  <div>
                    <p className="font-semibold text-gray-800 text-sm">{ins.message}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{ins.action}</p>
                  </div>
                </div>
                <span className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded-full border ${
                  ins.impact === 'Alto' ? 'bg-red-100 text-red-800 border-red-300' : 'bg-yellow-100 text-yellow-800 border-yellow-300'
                }`}>{ins.impact}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Action plan */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="px-6 py-3 border-b border-gray-100 flex items-center gap-2">
          <CheckCircle size={16} className="text-[#C9A959]" />
          <span className="font-bold text-[#0A2342] text-sm uppercase tracking-wider">Plano de Ação Recomendado</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-gray-100">
          {[
            { label: '30 dias', color: 'bg-yellow-50', items: ['Reunião de alinhamento com direção comercial', 'Revisão da precificação dos produtos críticos', 'Mapeamento das causas dos atrasos'] },
            { label: '90 dias', color: 'bg-blue-50',   items: ['Política de gestão de custos industriais', 'Auditoria de desperdícios na linha produtiva', 'Monitoramento contínuo via JUNO'] },
          ].map(p => (
            <div key={p.label} className={`p-5 ${p.color}`}>
              <p className="font-bold text-[#0A2342] text-xs uppercase tracking-wider mb-3">Curto Prazo · {p.label}</p>
              <ul className="space-y-2">
                {p.items.map((it, j) => (
                  <li key={j} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-[#C9A959] mt-0.5">•</span>{it}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FlowAuditoria({ d }: { d: DemoData }) {
  const C = scoreColor(d.trust.score);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Big trust score */}
        <div className={`${C.bg} border-2 ${C.border} rounded-xl p-6 text-center`}>
          <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Data Trust Score</p>
          <Shield size={28} className={`mx-auto mb-2 ${C.text}`} />
          <div className={`text-6xl font-extrabold ${C.text}`}>{d.trust.score}</div>
          <div className="text-xs text-gray-400 mt-1">/100</div>
          <span className={`mt-3 inline-block text-sm font-bold px-3 py-1 rounded-full ${C.badge}`}>Confiabilidade {d.trust.label}</span>
        </div>

        {/* Data stats */}
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          {[
            { label: 'Receita Total', value: `R$ ${fmt(d.validation.receita_total)}` },
            { label: 'Total Pedidos', value: fmt(d.validation.total_pedidos) },
            { label: 'Total Produtos', value: fmt(d.validation.total_produtos) },
            { label: 'Problemas Detectados', value: String(d.data_issues.length) },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
              <p className="text-xs text-gray-400 uppercase tracking-wider">{s.label}</p>
              <p className="text-2xl font-extrabold text-[#0A2342] mt-1">{s.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Deductions */}
      {d.trust.deductions.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Deduções do Score</p>
          <ul className="space-y-2">
            {d.trust.deductions.map((ded, i) => (
              <li key={i} className="flex justify-between text-sm text-gray-700">
                <span>{ded.reason}</span>
                <span className="text-red-500 font-bold">−{ded.deduction}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Issues */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-3 bg-[#0A2342] flex items-center gap-2">
          <ShieldCheck size={16} className="text-[#C9A959]" />
          <span className="text-white font-bold text-sm uppercase tracking-wider">Problemas de Qualidade de Dados</span>
        </div>
        {d.data_issues.length === 0 ? (
          <div className="p-8 text-center flex flex-col items-center gap-2">
            <CheckCircle size={28} className="text-green-500" />
            <p className="font-semibold text-green-700">Dados íntegros — prontos para o conselho.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-50">
            {d.data_issues.map((iss, i) => (
              <li key={i} className="px-6 py-3 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  <AlertTriangle size={15} className={`shrink-0 mt-0.5 ${iss.severity === 'Alto' ? 'text-red-500' : iss.severity === 'Médio' ? 'text-yellow-500' : 'text-blue-400'}`} />
                  <div>
                    <p className="font-semibold text-sm text-gray-800">{iss.message}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{iss.action}</p>
                  </div>
                </div>
                <span className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded-full border ${
                  iss.severity === 'Alto'  ? 'bg-red-100 text-red-800 border-red-300' :
                  iss.severity === 'Médio' ? 'bg-yellow-100 text-yellow-800 border-yellow-300' :
                                             'bg-blue-100 text-blue-800 border-blue-300'
                }`}>{iss.severity}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Validation status */}
      <div className={`flex items-center gap-3 px-5 py-4 rounded-xl border-2 ${
        d.validation.status === 'ok' ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'
      }`}>
        {d.validation.status === 'ok'
          ? <CheckCircle size={20} className="text-green-600" />
          : <XCircle size={20} className="text-red-600" />}
        <p className={`font-bold text-sm ${d.validation.status === 'ok' ? 'text-green-800' : 'text-red-800'}`}>
          {d.validation.status === 'ok'
            ? 'Validação básica aprovada — dados prontos para diagnóstico executivo.'
            : 'Validação básica falhou — revisar dados antes da apresentação.'}
        </p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DemoPage() {
  const [company, setCompany] = useState(1);
  const [flow, setFlow]       = useState(0);
  const [data, setData]       = useState<DemoData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const loadDemo = async (cid = company) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/demo/summary/${cid}`);
      setData(res.data);
    } catch {
      setError('Não foi possível carregar os dados demo. Verifique se o backend está ativo.');
    } finally {
      setLoading(false);
    }
  };

  const switchCompany = (id: number) => {
    setCompany(id);
    if (data) loadDemo(id);
  };

  const handleDownloadPDF = async () => {
    try {
      const res = await api.get(`/report/pdf/${company}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url; a.download = `JUNO_Demo_${data?.company.name ?? company}.pdf`;
      document.body.appendChild(a); a.click();
      window.URL.revokeObjectURL(url); document.body.removeChild(a);
    } catch { /* silently fail */ }
  };

  return (
    <div className="space-y-6 max-w-5xl">

      {/* Header */}
      <div className="border-b border-gray-200 pb-4 flex flex-wrap justify-between items-end gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold bg-[#C9A959] text-[#0A2342] px-2 py-0.5 rounded uppercase tracking-wider">Demo Mode</span>
            <span className="text-xs text-gray-400">JUNO v0.3.2</span>
          </div>
          <h1 className="text-2xl font-bold text-[#0A2342]">Pacote de Demonstração Executiva</h1>
          <p className="text-gray-500 text-sm mt-0.5">3 fluxos prontos para apresentação ao cliente.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            {COMPANIES.map(c => (
              <button key={c.id} onClick={() => switchCompany(c.id)}
                className={`px-4 py-2 rounded-lg border-2 font-bold text-sm transition-all ${
                  company === c.id ? 'bg-[#0A2342] text-white border-[#0A2342]' : 'bg-white text-[#0A2342] border-gray-200 hover:border-[#0A2342]'
                }`}>
                <span>{c.label}</span>
                <span className="block text-xs font-normal opacity-60">{c.sector}</span>
              </button>
            ))}
          </div>
          <button onClick={() => loadDemo()} disabled={loading}
            className="flex items-center gap-2 bg-[#C9A959] text-[#0A2342] font-bold py-2 px-5 rounded-lg hover:bg-[#b89a51] transition-colors shadow-md disabled:opacity-50">
            {loading ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
            Carregar Demo
          </button>
          {data && (
            <button onClick={handleDownloadPDF}
              className="flex items-center gap-2 bg-[#0A2342] text-white font-bold py-2 px-4 rounded-lg hover:bg-[#0d2d57] transition-colors shadow-md">
              <Download size={18} /> PDF
            </button>
          )}
        </div>
      </div>

      {/* Idle */}
      {!data && !loading && !error && (
        <div className="bg-[#F0F4F8] rounded-xl p-12 text-center flex flex-col items-center gap-3">
          <div className="text-4xl">🎯</div>
          <p className="text-[#0A2342] font-bold text-lg">Pronto para apresentar</p>
          <p className="text-gray-500 text-sm max-w-md">Selecione a empresa, clique em <strong>Carregar Demo</strong> e apresente os 3 fluxos ao cliente em tempo real.</p>
          <div className="flex gap-4 mt-3">
            {FLOWS.map((f, i) => (
              <div key={f.id} className="bg-white rounded-lg p-3 text-left shadow-sm border border-gray-100 w-44">
                <span className="text-lg">{f.emoji}</span>
                <p className="font-bold text-xs text-[#0A2342] mt-1">{i + 1}. {f.label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-center gap-3">
          <XCircle size={20} className="text-red-500" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="animate-spin text-[#0A2342]" size={40} />
          <p className="text-gray-500 text-sm">Carregando dados da demo...</p>
        </div>
      )}

      {/* Demo content */}
      {data && !loading && (
        <>
          {/* Company banner */}
          <div className="bg-[#0A2342] rounded-xl px-6 py-4 flex items-center justify-between">
            <div>
              <p className="text-[#C9A959] text-xs font-bold uppercase tracking-widest">Empresa em Análise</p>
              <p className="text-white text-xl font-extrabold mt-0.5">{data.company.name}</p>
              <p className="text-gray-400 text-xs">{data.company.sector}</p>
            </div>
            <div className="text-right">
              <p className="text-gray-400 text-xs uppercase tracking-wider">Score JUNO</p>
              <p className={`text-4xl font-extrabold ${scoreColor(data.kpis.score_juno).text}`}>{data.kpis.score_juno}</p>
            </div>
          </div>

          {/* Flow tabs */}
          <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
            {FLOWS.map((f, i) => (
              <button key={f.id} onClick={() => setFlow(i)}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                  flow === i ? 'bg-white text-[#0A2342] shadow-sm' : 'text-gray-500 hover:text-[#0A2342]'
                }`}>
                <span>{f.emoji}</span>
                <span className="hidden sm:inline">{f.label}</span>
                <span className="sm:hidden">{i + 1}</span>
              </button>
            ))}
          </div>

          {/* Slide navigation */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-[#0A2342]">{FLOWS[flow].emoji} {FLOWS[flow].label}</h2>
              <p className="text-sm text-gray-500">{FLOWS[flow].desc}</p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setFlow(f => Math.max(0, f - 1))} disabled={flow === 0}
                className="p-2 rounded-lg border border-gray-200 hover:border-[#0A2342] disabled:opacity-30 transition-colors">
                <ChevronLeft size={18} />
              </button>
              <span className="text-xs text-gray-400 px-2">{flow + 1} / {FLOWS.length}</span>
              <button onClick={() => setFlow(f => Math.min(FLOWS.length - 1, f + 1))} disabled={flow === FLOWS.length - 1}
                className="p-2 rounded-lg border border-gray-200 hover:border-[#0A2342] disabled:opacity-30 transition-colors">
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          {/* Active flow */}
          <div className="min-h-[400px]">
            {flow === 0 && <FlowDashboard d={data} />}
            {flow === 1 && <FlowInsights d={data} />}
            {flow === 2 && <FlowAuditoria d={data} />}
          </div>

          {/* Footer brand */}
          <div className="border-t border-gray-100 pt-4 text-center">
            <p className="text-xs text-gray-400 uppercase tracking-widest">
              Gerado por JUNO Industrial Diagnostic v0.3.2 — gravithy.com.br
            </p>
          </div>
        </>
      )}
    </div>
  );
}
