'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import { getTrendInfo, previousWindowCount } from '@/lib/trends';
import {
  Shield, AlertTriangle, CheckCircle, XCircle,
  Loader2, Database, TrendingUp, TrendingDown, Minus, Factory, Clock,
  ShoppingCart, BarChart3, ClipboardList, FileText, Download, CheckSquare,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────
interface Deduction { reason: string; deduction: number }
interface TrustScore { score: number; label: string; deductions: Deduction[] }
interface Issue {
  type: string;
  severity: 'Alto' | 'Médio' | 'Baixo';
  message: string;
  count: number;
  action: string;
}
interface Validation {
  receita_total: number;
  cmv_total?: number;
  despesa_total?: number;
  receita_pedidos?: number;
  financial_source?: string;
  financial_scope?: string | null;
  total_pedidos: number;
  total_produtos: number;
  total_ordens_producao: number;
  status: string;
  mensagem: string;
}
interface LastImport {
  data_type: string;
  file_name: string;
  rows_imported: number;
  status: string;
  created_at: string;
}
interface Report {
  company_id: number;
  validation: Validation;
  trust_score: TrustScore;
  issues: Issue[];
  last_import: LastImport | null;
  total_issues: number;
  high_severity: number;
  coverage: Coverage;
  domain_validations: DomainValidation[];
  reconciliation: ReconciliationItem[];
  event_summary: EventSummary;
  pending_actions: PendingAction[];
  executive_readiness: ReadinessItem[];
  exports: ExportItem[];
}
interface EventItem {
  id: number;
  company_id: number;
  entity_type: string;
  entity_id: number | null;
  event_type: string;
  old_state: Record<string, unknown> | null;
  new_state: Record<string, unknown> | null;
  user_id: string | null;
  created_at: string;
}
interface EventMetrics {
  total7d: number;
  totalPrev7d: number;
  total30d: number;
  price7d: number;
  pricePrev7d: number;
  price30d: number;
  erp7d: number;
  erpPrev7d: number;
  erp30d: number;
}
interface CoverageSource {
  name: string;
  loaded: boolean;
  records: number | null;
  status: string;
  action: string;
}
interface Coverage {
  score: number;
  loaded: number;
  total: number;
  sources: CoverageSource[];
  missing: string[];
}
interface DomainCheck {
  label: string;
  status: 'ok' | 'warning' | 'critical';
  severity: string;
  count: number;
  message: string;
  action: string;
}
interface DomainValidation {
  domain: string;
  status: 'ok' | 'warning' | 'critical' | 'missing';
  total_records: number;
  checks: DomainCheck[];
}
interface ReconciliationItem {
  label: string;
  status: 'ok' | 'warning' | 'critical' | 'missing';
  value: number | null;
  reference: number | null;
  difference_pct: number | null;
  message: string;
}
interface EventSummary {
  total_7d: number;
  total_30d: number;
  erp_import_30d: number;
  price_update_30d: number;
}
interface PendingAction {
  priority: string;
  owner: string;
  action: string;
  status: string;
  reason: string;
}
interface ReadinessItem {
  audience: string;
  ready: boolean;
  status: string;
  message: string;
}
interface ExportItem {
  label: string;
  format: string;
  available: boolean;
  endpoint: string;
  description: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function scoreColors(score: number) {
  if (score >= 80) return {
    ring: 'border-green-400', bg: 'bg-green-50', num: 'text-green-700',
    badge: 'bg-green-100 text-green-800 border-green-300',
  };
  if (score >= 60) return {
    ring: 'border-yellow-400', bg: 'bg-yellow-50', num: 'text-yellow-700',
    badge: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  };
  return {
    ring: 'border-red-400', bg: 'bg-red-50', num: 'text-red-700',
    badge: 'bg-red-100 text-red-800 border-red-300',
  };
}

function SeverityBadge({ s }: { s: string }) {
  const map: Record<string, string> = {
    Alto:  'bg-red-100 text-red-800 border-red-300',
    Médio: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    Baixo: 'bg-blue-100 text-blue-800 border-blue-300',
  };
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${map[s] ?? map.Baixo}`}>
      {s}
    </span>
  );
}

function fmt(n: number) {
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function statusBadgeClass(status: string) {
  if (status === 'ok' || status === 'ready' || status === 'loaded') {
    return 'bg-green-100 text-green-800 border-green-300';
  }
  if (status === 'critical' || status === 'blocked') {
    return 'bg-red-100 text-red-800 border-red-300';
  }
  return 'bg-yellow-100 text-yellow-800 border-yellow-300';
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    ok: 'OK',
    warning: 'Atencao',
    critical: 'Critico',
    missing: 'Pendente',
    loaded: 'Carregado',
    ready: 'Pronto',
    blocked: 'Bloqueado',
  };
  return labels[status] ?? status;
}

function fmtMaybe(n: number | null) {
  return n == null ? '-' : n.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
}

function eventTypeLabel(t: string) {
  const labels: Record<string, string> = {
    price_update: 'Atualizacao de preco',
    erp_import: 'Importacao ERP',
  };
  return labels[t] ?? t;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function AuditPage() {
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();
  const [report, setReport]   = useState<Report | null>(null);
  const [events, setEvents]   = useState<EventItem[]>([]);
  const [eventMetrics, setEventMetrics] = useState<EventMetrics | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState('all');
  const [periodFilter, setPeriodFilter] = useState('30');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const loadReport = useCallback(async (cid = companyId) => {
    if (!cid) {
      setReport(null);
      setEvents([]);
      setEventMetrics(null);
      setError('Nenhuma empresa vinculada ao usuario.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const eventsParams = new URLSearchParams({ limit: '20' });
      if (eventTypeFilter !== 'all') {
        eventsParams.set('event_type', eventTypeFilter);
      }
      if (periodFilter !== 'all') {
        eventsParams.set('days', periodFilter);
      }

      const [
        reportRes,
        eventsRes,
        total7dRes,
        total14dRes,
        total30dRes,
        price7dRes,
        price14dRes,
        price30dRes,
        erp7dRes,
        erp14dRes,
        erp30dRes,
      ] = await Promise.all([
        api.get(`/audit/data-quality/${cid}`),
        api.get(`/events/${cid}?${eventsParams.toString()}`),
        api.get(`/events/${cid}?count_only=true&days=7`),
        api.get(`/events/${cid}?count_only=true&days=14`),
        api.get(`/events/${cid}?count_only=true&days=30`),
        api.get(`/events/${cid}?count_only=true&event_type=price_update&days=7`),
        api.get(`/events/${cid}?count_only=true&event_type=price_update&days=14`),
        api.get(`/events/${cid}?count_only=true&event_type=price_update&days=30`),
        api.get(`/events/${cid}?count_only=true&event_type=erp_import&days=7`),
        api.get(`/events/${cid}?count_only=true&event_type=erp_import&days=14`),
        api.get(`/events/${cid}?count_only=true&event_type=erp_import&days=30`),
      ]);
      setReport(reportRes.data);
      setEvents(eventsRes.data ?? []);

      const total7d = Number(total7dRes.data?.count ?? 0);
      const total14d = Number(total14dRes.data?.count ?? 0);
      const price7d = Number(price7dRes.data?.count ?? 0);
      const price14d = Number(price14dRes.data?.count ?? 0);
      const erp7d = Number(erp7dRes.data?.count ?? 0);
      const erp14d = Number(erp14dRes.data?.count ?? 0);

      setEventMetrics({
        total7d,
        totalPrev7d: previousWindowCount(total7d, total14d),
        total30d: Number(total30dRes.data?.count ?? 0),
        price7d,
        pricePrev7d: previousWindowCount(price7d, price14d),
        price30d: Number(price30dRes.data?.count ?? 0),
        erp7d,
        erpPrev7d: previousWindowCount(erp7d, erp14d),
        erp30d: Number(erp30dRes.data?.count ?? 0),
      });
    } catch {
      setError('Erro ao carregar relatório de validação. Verifique se o backend está ativo.');
      setEvents([]);
      setEventMetrics(null);
    } finally {
      setLoading(false);
    }
  }, [companyId, eventTypeFilter, periodFilter]);

  useEffect(() => {
    if (!companyId) return;
    const timer = window.setTimeout(() => {
      void loadReport(companyId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [companyId, loadReport]);

  const C = report ? scoreColors(report.trust_score.score) : null;

  return (
    <div className="space-y-8 max-w-5xl">

      {/* Header */}
      <div className="border-b border-gray-200 pb-4 flex flex-wrap justify-between items-end gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0A2342]">Auditoria de Dados</h1>
          <p className="text-gray-500 text-sm mt-1">
            Verifique a confiabilidade dos dados antes de apresentar ao conselho.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-4 py-2 rounded-lg border-2 border-[#0A2342] bg-[#0A2342] text-white font-bold text-sm">
            {company?.name ?? 'Tenant nao selecionado'}
          </span>
          <button onClick={() => loadReport(companyId)} disabled={loading || companyLoading || !companyId}
            className="flex items-center gap-2 bg-[#C9A959] text-[#0A2342] font-bold py-2 px-5 rounded-lg hover:bg-[#b89a51] transition-colors shadow-md disabled:opacity-50">
            {loading
              ? <Loader2 className="animate-spin" size={18} />
              : <Shield size={18} />}
            Validar Dados
          </button>
        </div>
      </div>

      {/* Idle state */}
      {!report && !loading && !error && (
        <div className="bg-[#F0F4F8] rounded-xl p-12 text-center flex flex-col items-center gap-3">
          <Shield size={44} className="text-[#0A2342] opacity-30" />
          <p className="text-gray-500 font-medium">
            Clique em <strong>Validar Dados</strong> para auditar a qualidade dos dados da empresa selecionada.
          </p>
          <p className="text-xs text-gray-400">O relatório verifica integridade, consistência e prontidão para decisão executiva.</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-center gap-3">
          <XCircle size={20} className="text-red-500 shrink-0" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 className="animate-spin text-[#0A2342]" size={40} />
        </div>
      )}

      {/* Report */}
      {report && !loading && C && (
        <>
          {/* Row 1: Trust Score + Stats */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

            {/* Trust Score card */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Shield size={16} className="text-[#0A2342]" />
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Data Trust Score</span>
              </div>

              <div className={`${C.bg} rounded-xl p-5 text-center border-2 ${C.ring}`}>
                <div className={`text-6xl font-extrabold ${C.num}`}>{report.trust_score.score}</div>
                <div className="text-xs text-gray-400 mt-1">/100</div>
                <span className={`mt-2 inline-block px-3 py-1 rounded-full text-xs font-bold border ${C.badge}`}>
                  Confiabilidade {report.trust_score.label}
                </span>
              </div>

              {report.trust_score.deductions.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Deduções</p>
                  <ul className="space-y-1.5">
                    {report.trust_score.deductions.map((d, i) => (
                      <li key={i} className="flex justify-between items-start gap-2 text-xs text-gray-600">
                        <span className="flex-1">{d.reason}</span>
                        <span className="text-red-500 font-bold shrink-0">−{d.deduction}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Stats grid */}
            <div className="lg:col-span-3 flex flex-col gap-4">
              {report.validation.financial_scope && (
                <p className="text-xs text-gray-500">
                  Resumo financeiro (DRE): {report.validation.financial_scope}
                </p>
              )}
              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
                {[
                  { label: 'Receita (DRE)', value: `R$ ${fmt(report.validation.receita_total)}`, icon: TrendingUp },
                  { label: 'CMV (DRE)', value: `R$ ${fmt(report.validation.cmv_total ?? 0)}`, icon: TrendingDown },
                  { label: 'Despesa (DRE)', value: `R$ ${fmt(report.validation.despesa_total ?? 0)}`, icon: Minus },
                  { label: 'Pedidos de Venda', value: fmt(report.validation.total_pedidos), icon: ShoppingCart },
                  { label: 'Produtos', value: fmt(report.validation.total_produtos), icon: Database },
                  { label: 'Ordens Produção', value: fmt(report.validation.total_ordens_producao), icon: Factory },
                ].map(s => {
                  const Icon = s.icon;
                  return (
                    <div key={s.label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-xs text-gray-400 uppercase tracking-wider leading-tight">{s.label}</p>
                          <p className="text-xl font-extrabold text-[#0A2342] mt-1">{s.value}</p>
                        </div>
                        <Icon size={18} className="text-gray-200" />
                      </div>
                    </div>
                  );
                })}
              </div>
              {report.validation.receita_pedidos != null
                && report.validation.financial_source === 'dre'
                && Math.abs(report.validation.receita_pedidos - report.validation.receita_total) > report.validation.receita_total * 0.05 && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2">
                  Receita de pedidos (ERP): R$ {fmt(report.validation.receita_pedidos)} — diverge da DRE.
                  Use a DRE como referência financeira oficial.
                </p>
              )}

              {/* Sanity status banner */}
              <div className={`flex items-center gap-3 px-5 py-4 rounded-xl border-2 ${
                report.validation.status === 'ok'
                  ? 'bg-green-50 border-green-300'
                  : 'bg-red-50 border-red-300'
              }`}>
                {report.validation.status === 'ok'
                  ? <CheckCircle size={20} className="text-green-600 shrink-0" />
                  : <XCircle size={20} className="text-red-600 shrink-0" />}
                <div>
                  <p className={`font-bold text-sm ${report.validation.status === 'ok' ? 'text-green-800' : 'text-red-800'}`}>
                    {report.validation.status === 'ok' ? 'Validação Básica: Aprovada' : 'Validação Básica: Falha'}
                  </p>
                  <p className={`text-xs mt-0.5 ${report.validation.status === 'ok' ? 'text-green-600' : 'text-red-600'}`}>
                    {report.validation.mensagem}
                  </p>
                </div>
                {report.high_severity > 0 && (
                  <span className="ml-auto text-xs font-bold bg-red-100 text-red-700 px-3 py-1 rounded-full shrink-0">
                    {report.high_severity} problema(s) crítico(s)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Coverage */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
              <div className="flex items-center gap-2">
                <ClipboardList size={18} className="text-[#0A2342]" />
                <h3 className="font-bold text-[#0A2342]">Cobertura de Dados</h3>
              </div>
              <span className={`text-xs font-bold px-3 py-1 rounded-full border ${report.coverage.score >= 80 ? 'bg-green-100 text-green-800 border-green-300' : report.coverage.score >= 60 ? 'bg-yellow-100 text-yellow-800 border-yellow-300' : 'bg-red-100 text-red-800 border-red-300'}`}>
                {report.coverage.loaded}/{report.coverage.total} fontes · {report.coverage.score.toFixed(0)}%
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {report.coverage.sources.map(source => (
                <div key={source.name} className="rounded-lg border border-gray-100 p-3 flex items-start gap-3">
                  {source.loaded ? (
                    <CheckCircle size={18} className="text-green-600 mt-0.5 shrink-0" />
                  ) : (
                    <AlertTriangle size={18} className="text-yellow-600 mt-0.5 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="font-semibold text-sm text-gray-800">{source.name}</p>
                    <p className="text-xs text-gray-500">
                      {source.loaded ? 'Carregado' : `Pendente: ${source.action}`}
                      {source.records != null ? ` · ${source.records} registro(s)` : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Domain validations */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
              <CheckSquare size={18} className="text-[#0A2342]" />
              <h3 className="font-bold text-[#0A2342]">Validações por Domínio</h3>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-5">
              {report.domain_validations.map(domain => (
                <div key={domain.domain} className="rounded-lg border border-gray-100 p-4">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div>
                      <p className="font-bold text-[#0A2342]">{domain.domain}</p>
                      <p className="text-xs text-gray-400">{domain.total_records} registro(s)</p>
                    </div>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${statusBadgeClass(domain.status)}`}>
                      {statusLabel(domain.status)}
                    </span>
                  </div>
                  <ul className="space-y-2">
                    {domain.checks.map(check => (
                      <li key={`${domain.domain}-${check.label}`} className="flex items-start justify-between gap-3 text-sm">
                        <div>
                          <p className="font-medium text-gray-700">{check.label}</p>
                          {check.status !== 'ok' && (
                            <p className="text-xs text-gray-500">{check.action}</p>
                          )}
                        </div>
                        <span className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded-full border ${statusBadgeClass(check.status)}`}>
                          {check.count}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          {/* Reconciliation */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
              <BarChart3 size={18} className="text-[#0A2342]" />
              <h3 className="font-bold text-[#0A2342]">Reconciliação e Cruzamentos</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 bg-gray-50">
                    <th className="px-6 py-3">Cruzamento</th>
                    <th className="px-6 py-3 text-right">Valor</th>
                    <th className="px-6 py-3 text-right">Referencia</th>
                    <th className="px-6 py-3 text-right">Dif.</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {report.reconciliation.map(item => (
                    <tr key={item.label} className="border-t border-gray-100">
                      <td className="px-6 py-3">
                        <p className="font-semibold text-gray-800">{item.label}</p>
                        <p className="text-xs text-gray-500">{item.message}</p>
                      </td>
                      <td className="px-6 py-3 text-right">{fmtMaybe(item.value)}</td>
                      <td className="px-6 py-3 text-right">{fmtMaybe(item.reference)}</td>
                      <td className="px-6 py-3 text-right">{item.difference_pct == null ? '-' : `${item.difference_pct.toFixed(1)}%`}</td>
                      <td className="px-6 py-3">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${statusBadgeClass(item.status)}`}>
                          {statusLabel(item.status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Issues */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle size={17} className="text-[#0A2342]" />
                <h3 className="font-bold text-[#0A2342]">Problemas Detectados</h3>
              </div>
              <span className="text-xs text-gray-400">{report.total_issues} ocorrência(s)</span>
            </div>

            {report.issues.length === 0 ? (
              <div className="p-10 flex flex-col items-center gap-2">
                <CheckCircle size={36} className="text-green-500" />
                <p className="font-semibold text-green-700">Nenhum problema detectado</p>
                <p className="text-sm text-gray-400 text-center max-w-sm">
                  Os dados estão consistentes e prontos para o diagnóstico executivo. Este relatório pode ir ao conselho.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-50">
                {report.issues.map((issue, i) => (
                  <li key={i} className="px-6 py-4 flex items-start justify-between gap-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <AlertTriangle size={17} className={`shrink-0 mt-0.5 ${
                        issue.severity === 'Alto' ? 'text-red-500' :
                        issue.severity === 'Médio' ? 'text-yellow-500' : 'text-blue-400'
                      }`} />
                      <div className="min-w-0">
                        <p className="font-semibold text-gray-800 text-sm">{issue.message}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{issue.action}</p>
                      </div>
                    </div>
                    <SeverityBadge s={issue.severity} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Last import bar */}
          {report.last_import && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-6 py-4 flex flex-wrap items-center gap-4">
              <Clock size={17} className="text-[#0A2342] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="font-bold text-sm text-[#0A2342]">Última Importação ERP</p>
                <p className="text-xs text-gray-500 truncate">
                  {report.last_import.data_type.replace('_', ' ')} &nbsp;·&nbsp;
                  {report.last_import.file_name} &nbsp;·&nbsp;
                  {report.last_import.rows_imported} linhas importadas
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-gray-400">
                  {new Date(report.last_import.created_at).toLocaleDateString('pt-BR')}
                </span>
                <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                  report.last_import.status === 'success'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-yellow-100 text-yellow-700'
                }`}>
                  {report.last_import.status}
                </span>
              </div>
            </div>
          )}

          {/* Event governance metrics */}
          {eventMetrics && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-[#0A2342]">Governanca de Eventos</h3>
                <span className="text-xs text-gray-400">Ultimos 7 e 30 dias</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  {
                    label: 'Eventos (7d)',
                    value: eventMetrics.total7d,
                    trend: getTrendInfo(eventMetrics.total7d, eventMetrics.totalPrev7d),
                  },
                  { label: 'Eventos (30d)', value: eventMetrics.total30d },
                  {
                    label: 'Mudancas de Preco (7d)',
                    value: eventMetrics.price7d,
                    trend: getTrendInfo(eventMetrics.price7d, eventMetrics.pricePrev7d),
                    sublabel: `30d: ${eventMetrics.price30d}`,
                  },
                  {
                    label: 'Importacoes ERP (7d)',
                    value: eventMetrics.erp7d,
                    trend: getTrendInfo(eventMetrics.erp7d, eventMetrics.erpPrev7d),
                    sublabel: `30d: ${eventMetrics.erp30d}`,
                  },
                ].map((item) => (
                  <div key={item.label} className="bg-[#F0F4F8] rounded-lg p-3 border border-gray-100">
                    <p className="text-[11px] text-gray-500 uppercase tracking-wider leading-tight">{item.label}</p>
                    <p className="text-2xl font-extrabold text-[#0A2342] mt-1">{item.value}</p>
                    {'trend' in item && item.trend && (
                      <span className={`inline-flex items-center gap-1 mt-2 text-[10px] font-bold px-2 py-1 rounded-full ${item.trend.className}`}>
                        {item.trend.direction === 'up' && <TrendingUp size={11} />}
                        {item.trend.direction === 'down' && <TrendingDown size={11} />}
                        {item.trend.direction === 'flat' && <Minus size={11} />}
                        <span>{item.trend.text}</span>
                      </span>
                    )}
                    {'sublabel' in item && item.sublabel && (
                      <p className="text-[10px] text-gray-500 mt-1">{item.sublabel}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Event timeline */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-[#0A2342]">Linha do Tempo de Eventos</h3>
                <span className="text-xs text-gray-400">
                  /events/{companyId ?? '-'} · {company?.name ?? 'Tenant nao selecionado'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={eventTypeFilter}
                  onChange={(e) => setEventTypeFilter(e.target.value)}
                  className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-700"
                >
                  <option value="all">Todos tipos</option>
                  <option value="price_update">Atualizacao de preco</option>
                  <option value="erp_import">Importacao ERP</option>
                </select>
                <select
                  value={periodFilter}
                  onChange={(e) => setPeriodFilter(e.target.value)}
                  className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-700"
                >
                  <option value="7">7 dias</option>
                  <option value="30">30 dias</option>
                  <option value="90">90 dias</option>
                  <option value="all">Todo periodo</option>
                </select>
                <button
                  onClick={() => loadReport()}
                  className="text-xs font-bold bg-[#0A2342] text-white px-3 py-1.5 rounded-md hover:bg-[#0d2d57]"
                >
                  Aplicar
                </button>
              </div>
            </div>

            {events.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-500">
                Nenhum evento recente para esta empresa.
              </div>
            ) : (
              <ul className="divide-y divide-gray-50">
                {events.slice(0, 10).map((e) => (
                  <li key={e.id} className="px-6 py-4 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="font-semibold text-gray-800 text-sm">
                        {eventTypeLabel(e.event_type)}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        Entidade: {e.entity_type}
                        {e.entity_id ? ` #${e.entity_id}` : ''}
                        {e.user_id ? ` · Usuario: ${e.user_id}` : ''}
                      </p>

                      {e.event_type === 'price_update' && (
                        <p className="text-xs text-gray-600 mt-1">
                          Preco: R$ {Number(e.old_state?.sale_price ?? 0).toLocaleString('pt-BR')}
                          {' -> '}
                          R$ {Number(e.new_state?.sale_price ?? 0).toLocaleString('pt-BR')}
                        </p>
                      )}

                      {e.event_type === 'erp_import' && (
                        <p className="text-xs text-gray-600 mt-1">
                          Arquivo: {String(e.new_state?.file_name ?? '-')}
                          {' · Importadas: '}
                          {Number(e.new_state?.rows_imported ?? 0)}
                          {' · Rejeitadas: '}
                          {Number(e.new_state?.rows_rejected ?? 0)}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 shrink-0">
                      {new Date(e.created_at).toLocaleString('pt-BR')}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Pending actions and readiness */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <AlertTriangle size={18} className="text-[#0A2342]" />
                <h3 className="font-bold text-[#0A2342]">Pendências e Plano de Ação</h3>
              </div>
              {report.pending_actions.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-500">
                  Nenhuma pendência aberta para os critérios atuais.
                </div>
              ) : (
                <ul className="divide-y divide-gray-50">
                  {report.pending_actions.slice(0, 8).map((action, i) => (
                    <li key={`${action.action}-${i}`} className="px-6 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-gray-800 text-sm">{action.action}</p>
                          <p className="text-xs text-gray-500 mt-1">{action.reason}</p>
                          <p className="text-[11px] text-gray-400 mt-1">Responsavel: {action.owner}</p>
                        </div>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${action.priority === 'Alta' ? 'bg-red-100 text-red-800 border-red-300' : 'bg-yellow-100 text-yellow-800 border-yellow-300'}`}>
                          {action.priority}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <Shield size={18} className="text-[#0A2342]" />
                <h3 className="font-bold text-[#0A2342]">Prontidão Executiva</h3>
              </div>
              <ul className="divide-y divide-gray-50">
                {report.executive_readiness.map(item => (
                  <li key={item.audience} className="px-6 py-4 flex items-start justify-between gap-4">
                    <div>
                      <p className="font-semibold text-gray-800">{item.audience}</p>
                      <p className="text-xs text-gray-500 mt-1">{item.message}</p>
                    </div>
                    <span className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded-full border ${statusBadgeClass(item.status)}`}>
                      {statusLabel(item.status)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Exports */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <div className="flex items-center gap-2 mb-4">
              <FileText size={18} className="text-[#0A2342]" />
              <h3 className="font-bold text-[#0A2342]">Exportações de Auditoria</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {report.exports.map(item => (
                <div key={item.label} className="rounded-lg border border-gray-100 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-bold text-sm text-gray-800">{item.label}</p>
                    <Download size={16} className={item.available ? 'text-[#C9A959]' : 'text-gray-300'} />
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{item.description}</p>
                  <p className="text-[11px] text-gray-400 mt-2 uppercase">{item.format}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Quick summary for executive use */}
          <div className="bg-[#0A2342] rounded-xl p-6 text-white">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 size={18} className="text-[#C9A959]" />
              <h3 className="font-bold text-sm uppercase tracking-wider text-[#C9A959]">Resumo Executivo — Prontidão dos Dados</h3>
            </div>
            <p className="text-sm leading-relaxed opacity-90">
              {report.trust_score.score >= 80
                ? `Os dados da empresa apresentam alta confiabilidade (Score ${report.trust_score.score}/100). O diagnóstico JUNO está pronto para ser apresentado ao conselho e à diretoria.`
                : report.trust_score.score >= 60
                ? `Os dados apresentam confiabilidade média (Score ${report.trust_score.score}/100). Recomenda-se corrigir os ${report.total_issues} problema(s) identificados antes da apresentação executiva.`
                : `Atenção: confiabilidade baixa (Score ${report.trust_score.score}/100). Há ${report.high_severity} problema(s) crítico(s) que devem ser resolvidos antes de qualquer apresentação ao conselho.`
              }
            </p>
          </div>
        </>
      )}
    </div>
  );
}
