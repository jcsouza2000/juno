'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import { useI18n } from '@/lib/i18n';
import { getTrendInfo, previousWindowCount } from '@/lib/trends';

type Translator = (key: string, vars?: Record<string, string | number>) => string;
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

// Severidade vem do backend em PT ('Alto'/'Médio'/'Baixo'); mapeia para a chave i18n.
const SEVERITY_KEY: Record<string, string> = { Alto: 'high', Médio: 'medium', Baixo: 'low' };

function SeverityBadge({ s }: { s: string }) {
  const { t } = useI18n();
  const map: Record<string, string> = {
    Alto:  'bg-red-100 text-red-800 border-red-300',
    Médio: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    Baixo: 'bg-blue-100 text-blue-800 border-blue-300',
  };
  const label = SEVERITY_KEY[s] ? t(`audit.severity.${SEVERITY_KEY[s]}`) : s;
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${map[s] ?? map.Baixo}`}>
      {label}
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

const KNOWN_STATUS = ['ok', 'warning', 'critical', 'missing', 'loaded', 'ready', 'blocked'];

function statusLabel(status: string, t: Translator) {
  return KNOWN_STATUS.includes(status) ? t(`audit.status.${status}`) : status;
}

function fmtMaybe(n: number | null) {
  return n == null ? '-' : n.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
}

function eventTypeLabel(eventType: string, t: Translator) {
  if (eventType === 'price_update') return t('audit.priceUpdate');
  if (eventType === 'erp_import') return t('audit.erpImport');
  return eventType;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function AuditPage() {
  const { t } = useI18n();
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
      setError(t('audit.noCompany'));
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
      setError(t('audit.errorLoad'));
      setEvents([]);
      setEventMetrics(null);
    } finally {
      setLoading(false);
    }
  }, [companyId, eventTypeFilter, periodFilter, t]);

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
          <h1 className="text-2xl font-bold text-[#0A2342]">{t('audit.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">
            {t('audit.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-4 py-2 rounded-lg border-2 border-[#0A2342] bg-[#0A2342] text-white font-bold text-sm">
            {company?.name ?? t('audit.noTenant')}
          </span>
          <button onClick={() => loadReport(companyId)} disabled={loading || companyLoading || !companyId}
            className="flex items-center gap-2 bg-[#C9A959] text-[#0A2342] font-bold py-2 px-5 rounded-lg hover:bg-[#b89a51] transition-colors shadow-md disabled:opacity-50">
            {loading
              ? <Loader2 className="animate-spin" size={18} />
              : <Shield size={18} />}
            {t('audit.validateBtn')}
          </button>
        </div>
      </div>

      {/* Idle state */}
      {!report && !loading && !error && (
        <div className="bg-[#F0F4F8] rounded-xl p-12 text-center flex flex-col items-center gap-3">
          <Shield size={44} className="text-[#0A2342] opacity-30" />
          <p className="text-gray-500 font-medium">
            {t('audit.idleText')}
          </p>
          <p className="text-xs text-gray-400">{t('audit.idleHint')}</p>
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
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">{t('audit.trustScore')}</span>
              </div>

              <div className={`${C.bg} rounded-xl p-5 text-center border-2 ${C.ring}`}>
                <div className={`text-6xl font-extrabold ${C.num}`}>{report.trust_score.score}</div>
                <div className="text-xs text-gray-400 mt-1">/100</div>
                <span className={`mt-2 inline-block px-3 py-1 rounded-full text-xs font-bold border ${C.badge}`}>
                  {t('audit.reliability', { label: report.trust_score.label })}
                </span>
              </div>

              {report.trust_score.deductions.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">{t('audit.deductions')}</p>
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
                  {t('audit.financialSummary', { scope: report.validation.financial_scope })}
                </p>
              )}
              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
                {[
                  { label: t('audit.stat.revenueDre'), value: `R$ ${fmt(report.validation.receita_total)}`, icon: TrendingUp },
                  { label: t('audit.stat.cmvDre'), value: `R$ ${fmt(report.validation.cmv_total ?? 0)}`, icon: TrendingDown },
                  { label: t('audit.stat.expenseDre'), value: `R$ ${fmt(report.validation.despesa_total ?? 0)}`, icon: Minus },
                  { label: t('audit.stat.salesOrders'), value: fmt(report.validation.total_pedidos), icon: ShoppingCart },
                  { label: t('audit.stat.products'), value: fmt(report.validation.total_produtos), icon: Database },
                  { label: t('audit.stat.productionOrders'), value: fmt(report.validation.total_ordens_producao), icon: Factory },
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
                  {t('audit.erpDivergence', { value: fmt(report.validation.receita_pedidos) })}
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
                    {report.validation.status === 'ok' ? t('audit.basicValidationOk') : t('audit.basicValidationFail')}
                  </p>
                  <p className={`text-xs mt-0.5 ${report.validation.status === 'ok' ? 'text-green-600' : 'text-red-600'}`}>
                    {report.validation.mensagem}
                  </p>
                </div>
                {report.high_severity > 0 && (
                  <span className="ml-auto text-xs font-bold bg-red-100 text-red-700 px-3 py-1 rounded-full shrink-0">
                    {t('audit.criticalProblems', { n: report.high_severity })}
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
                <h3 className="font-bold text-[#0A2342]">{t('audit.coverage')}</h3>
              </div>
              <span className={`text-xs font-bold px-3 py-1 rounded-full border ${report.coverage.score >= 80 ? 'bg-green-100 text-green-800 border-green-300' : report.coverage.score >= 60 ? 'bg-yellow-100 text-yellow-800 border-yellow-300' : 'bg-red-100 text-red-800 border-red-300'}`}>
                {t('audit.coverageBadge', { loaded: report.coverage.loaded, total: report.coverage.total, score: report.coverage.score.toFixed(0) })}
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
                      {source.loaded ? t('audit.loaded') : t('audit.pendingAction', { action: source.action })}
                      {source.records != null ? ` · ${t('audit.records', { n: source.records })}` : ''}
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
              <h3 className="font-bold text-[#0A2342]">{t('audit.domainValidations')}</h3>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-5">
              {report.domain_validations.map(domain => (
                <div key={domain.domain} className="rounded-lg border border-gray-100 p-4">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div>
                      <p className="font-bold text-[#0A2342]">{domain.domain}</p>
                      <p className="text-xs text-gray-400">{t('audit.records', { n: domain.total_records })}</p>
                    </div>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${statusBadgeClass(domain.status)}`}>
                      {statusLabel(domain.status, t)}
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
              <h3 className="font-bold text-[#0A2342]">{t('audit.reconciliation')}</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 bg-gray-50">
                    <th className="px-6 py-3">{t('audit.colCrossing')}</th>
                    <th className="px-6 py-3 text-right">{t('audit.colValue')}</th>
                    <th className="px-6 py-3 text-right">{t('audit.colReference')}</th>
                    <th className="px-6 py-3 text-right">{t('audit.colDiff')}</th>
                    <th className="px-6 py-3">{t('audit.colStatus')}</th>
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
                          {statusLabel(item.status, t)}
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
                <h3 className="font-bold text-[#0A2342]">{t('audit.issuesDetected')}</h3>
              </div>
              <span className="text-xs text-gray-400">{t('audit.occurrences', { n: report.total_issues })}</span>
            </div>

            {report.issues.length === 0 ? (
              <div className="p-10 flex flex-col items-center gap-2">
                <CheckCircle size={36} className="text-green-500" />
                <p className="font-semibold text-green-700">{t('audit.noIssues')}</p>
                <p className="text-sm text-gray-400 text-center max-w-sm">
                  {t('audit.noIssuesHint')}
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
                <p className="font-bold text-sm text-[#0A2342]">{t('audit.lastImport')}</p>
                <p className="text-xs text-gray-500 truncate">
                  {report.last_import.data_type.replace('_', ' ')} &nbsp;·&nbsp;
                  {report.last_import.file_name} &nbsp;·&nbsp;
                  {t('audit.rowsImported', { n: report.last_import.rows_imported })}
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
                <h3 className="font-bold text-[#0A2342]">{t('audit.eventGovernance')}</h3>
                <span className="text-xs text-gray-400">{t('audit.last7and30')}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  {
                    label: t('audit.events7d'),
                    value: eventMetrics.total7d,
                    trend: getTrendInfo(eventMetrics.total7d, eventMetrics.totalPrev7d),
                  },
                  { label: t('audit.events30d'), value: eventMetrics.total30d },
                  {
                    label: t('audit.priceChanges7d'),
                    value: eventMetrics.price7d,
                    trend: getTrendInfo(eventMetrics.price7d, eventMetrics.pricePrev7d),
                    sublabel: t('audit.sub30d', { n: eventMetrics.price30d }),
                  },
                  {
                    label: t('audit.erpImports7d'),
                    value: eventMetrics.erp7d,
                    trend: getTrendInfo(eventMetrics.erp7d, eventMetrics.erpPrev7d),
                    sublabel: t('audit.sub30d', { n: eventMetrics.erp30d }),
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
                <h3 className="font-bold text-[#0A2342]">{t('audit.eventTimeline')}</h3>
                <span className="text-xs text-gray-400">
                  /events/{companyId ?? '-'} · {company?.name ?? t('audit.noTenant')}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={eventTypeFilter}
                  onChange={(e) => setEventTypeFilter(e.target.value)}
                  className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-700"
                >
                  <option value="all">{t('audit.allTypes')}</option>
                  <option value="price_update">{t('audit.priceUpdate')}</option>
                  <option value="erp_import">{t('audit.erpImport')}</option>
                </select>
                <select
                  value={periodFilter}
                  onChange={(e) => setPeriodFilter(e.target.value)}
                  className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-700"
                >
                  <option value="7">{t('audit.days7')}</option>
                  <option value="30">{t('audit.days30')}</option>
                  <option value="90">{t('audit.days90')}</option>
                  <option value="all">{t('audit.allPeriod')}</option>
                </select>
                <button
                  onClick={() => loadReport()}
                  className="text-xs font-bold bg-[#0A2342] text-white px-3 py-1.5 rounded-md hover:bg-[#0d2d57]"
                >
                  {t('audit.apply')}
                </button>
              </div>
            </div>

            {events.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-500">
                {t('audit.noEvents')}
              </div>
            ) : (
              <ul className="divide-y divide-gray-50">
                {events.slice(0, 10).map((e) => (
                  <li key={e.id} className="px-6 py-4 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="font-semibold text-gray-800 text-sm">
                        {eventTypeLabel(e.event_type, t)}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {t('audit.entity')} {e.entity_type}
                        {e.entity_id ? ` #${e.entity_id}` : ''}
                        {e.user_id ? ` · ${t('audit.user')} ${e.user_id}` : ''}
                      </p>

                      {e.event_type === 'price_update' && (
                        <p className="text-xs text-gray-600 mt-1">
                          {t('audit.price')} R$ {Number(e.old_state?.sale_price ?? 0).toLocaleString('pt-BR')}
                          {' -> '}
                          R$ {Number(e.new_state?.sale_price ?? 0).toLocaleString('pt-BR')}
                        </p>
                      )}

                      {e.event_type === 'erp_import' && (
                        <p className="text-xs text-gray-600 mt-1">
                          {t('audit.file')} {String(e.new_state?.file_name ?? '-')}
                          {` · ${t('audit.imported')} `}
                          {Number(e.new_state?.rows_imported ?? 0)}
                          {` · ${t('audit.rejected')} `}
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
                <h3 className="font-bold text-[#0A2342]">{t('audit.pendingActions')}</h3>
              </div>
              {report.pending_actions.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-500">
                  {t('audit.noPending')}
                </div>
              ) : (
                <ul className="divide-y divide-gray-50">
                  {report.pending_actions.slice(0, 8).map((action, i) => (
                    <li key={`${action.action}-${i}`} className="px-6 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-gray-800 text-sm">{action.action}</p>
                          <p className="text-xs text-gray-500 mt-1">{action.reason}</p>
                          <p className="text-[11px] text-gray-400 mt-1">{t('audit.owner')} {action.owner}</p>
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
                <h3 className="font-bold text-[#0A2342]">{t('audit.executiveReadiness')}</h3>
              </div>
              <ul className="divide-y divide-gray-50">
                {report.executive_readiness.map(item => (
                  <li key={item.audience} className="px-6 py-4 flex items-start justify-between gap-4">
                    <div>
                      <p className="font-semibold text-gray-800">{item.audience}</p>
                      <p className="text-xs text-gray-500 mt-1">{item.message}</p>
                    </div>
                    <span className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded-full border ${statusBadgeClass(item.status)}`}>
                      {statusLabel(item.status, t)}
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
              <h3 className="font-bold text-[#0A2342]">{t('audit.auditExports')}</h3>
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
              <h3 className="font-bold text-sm uppercase tracking-wider text-[#C9A959]">{t('audit.execSummaryTitle')}</h3>
            </div>
            <p className="text-sm leading-relaxed opacity-90">
              {report.trust_score.score >= 80
                ? t('audit.summaryHigh', { score: report.trust_score.score })
                : report.trust_score.score >= 60
                ? t('audit.summaryMid', { score: report.trust_score.score, issues: report.total_issues })
                : t('audit.summaryLow', { score: report.trust_score.score, high: report.high_severity })
              }
            </p>
          </div>
        </>
      )}
    </div>
  );
}
