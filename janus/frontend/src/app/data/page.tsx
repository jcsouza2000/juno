'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import {
  Database, Trash2, AlertTriangle, RefreshCw, Loader2,
  FileStack, Calendar, ShieldAlert, CheckCircle, AlertCircle,
} from 'lucide-react';
import { api, getApiErrorMessage } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import { useI18n } from '@/lib/i18n';

// ── Types ──────────────────────────────────────────────────────────────────
interface InventoryTable { table: string; rows: number }
interface InventoryGroup { group: string; label: string; total_rows: number; tables: InventoryTable[] }
interface Deposit {
  source: 'financial' | 'erp';
  id: number;
  file_name?: string | null;
  periods?: string | null;
  data_type?: string | null;
  rows: number;
  status: string;
  version_number?: number;
  version_label?: string;
  is_active?: boolean;
  created_at: string | null;
}
interface Inventory {
  company_id: number;
  total_rows: number;
  groups: InventoryGroup[];
  periods: string[];
  uploads: Deposit[];
}
interface PurgeResult {
  status: string;
  company_id: number;
  scope: string;
  total_rows_deleted: number;
  deleted: Record<string, number>;
}

type Scope = 'financial' | 'erp' | 'all';

const GROUP_ICON: Record<string, React.ReactNode> = {
  financial: <FileStack size={16} className="text-[#C9A959]" />,
  erp: <Database size={16} className="text-[#C9A959]" />,
  derived: <RefreshCw size={16} className="text-[#C9A959]" />,
};

const SCOPES: Scope[] = ['financial', 'erp', 'all'];

// ── Page ───────────────────────────────────────────────────────────────────
export default function DataPage() {
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();
  const { data: session } = useSession();
  const { t } = useI18n();
  const role = session?.user?.role;
  const isDevPilot = process.env.NODE_ENV !== 'production' && !role;
  const isAdmin = role === 'admin' || role === 'platform_admin' || isDevPilot;

  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Purge state
  const [scope, setScope] = useState<Scope>('financial');
  const [confirmation, setConfirmation] = useState('');
  const [purging, setPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState<PurgeResult | null>(null);
  const [purgeError, setPurgeError] = useState<string | null>(null);

  const [activatingKey, setActivatingKey] = useState<string | null>(null);
  const [activateMsg, setActivateMsg] = useState<string | null>(null);
  const [activateError, setActivateError] = useState<string | null>(null);

  const expectedToken = companyId != null ? `PURGE-${companyId}` : '';

  const scopeTitle = (s: Scope) => t(`data.scope.${s}Title`);
  const scopeDesc = (s: Scope) => t(`data.scope.${s}Desc`);

  const loadInventory = useCallback(async () => {
    if (!companyId) {
      setInventory(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/data/${companyId}/inventory`);
      setInventory(res.data);
    } catch (err: unknown) {
      setInventory(null);
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    const id = window.setTimeout(() => { void loadInventory(); }, 0);
    return () => window.clearTimeout(id);
  }, [loadInventory]);

  const handleActivate = async (d: Deposit) => {
    if (!companyId || d.is_active) return;
    const key = `${d.source}-${d.id}`;
    if (!window.confirm(
      t('data.versions.activate') + ` ${d.version_label ?? ''}?`,
    )) return;

    setActivatingKey(key);
    setActivateMsg(null);
    setActivateError(null);
    try {
      await api.post(`/data/${companyId}/versions/${d.id}/activate?source=${d.source}`);
      setActivateMsg(t('data.versions.activated', { version: d.version_label ?? '' }));
      await loadInventory();
    } catch (err: unknown) {
      setActivateError(getApiErrorMessage(err));
    } finally {
      setActivatingKey(null);
    }
  };

  const handlePurge = async () => {
    if (!companyId || confirmation !== expectedToken) return;
    if (!window.confirm(
      t('data.confirmDialog', { scope: scopeTitle(scope), company: company?.name ?? companyId }),
    )) return;

    setPurging(true);
    setPurgeResult(null);
    setPurgeError(null);
    try {
      const res = await api.post(`/data/${companyId}/purge`, { scope, confirmation });
      setPurgeResult(res.data);
      setConfirmation('');
      await loadInventory();
    } catch (err: unknown) {
      setPurgeError(getApiErrorMessage(err));
    } finally {
      setPurging(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#0A2342]">{t('data.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('data.subtitle')}</p>
        </div>
        <button
          onClick={() => void loadInventory()}
          disabled={loading || !companyId}
          className="flex items-center gap-2 text-sm font-semibold text-[#0A2342] border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50 disabled:opacity-40"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> {t('common.refresh')}
        </button>
      </div>

      {companyLoading && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 text-sm text-gray-500">
          {t('common.loadingTenant')}
        </div>
      )}

      {!companyLoading && !companyId && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-xl p-6 text-sm text-yellow-800">
          {t('common.noCompany')}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-sm text-red-700 flex items-start gap-2">
          <AlertCircle size={18} className="shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {/* Total + groups */}
      {companyId && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-[#0A2342] bg-[#0A2342] p-4">
              <p className="text-xs uppercase tracking-widest font-semibold text-[#C9A959]">{t('data.totalRecords')}</p>
              <div className="text-3xl font-extrabold mt-1 text-white">
                {loading ? '—' : (inventory?.total_rows ?? 0).toLocaleString('pt-BR')}
              </div>
              <p className="text-xs mt-1 text-white/60">{company?.name ?? ''}</p>
            </div>

            {(inventory?.groups ?? []).map((g) => (
              <div key={g.group} className="rounded-xl border border-gray-100 bg-white p-4">
                <div className="flex items-center gap-2">
                  {GROUP_ICON[g.group] ?? <Database size={16} className="text-[#C9A959]" />}
                  <p className="text-xs uppercase tracking-widest font-semibold text-gray-400">
                    {t(`data.group.${g.group}`)}
                  </p>
                </div>
                <div className="text-2xl font-extrabold mt-1 text-[#0A2342]">
                  {g.total_rows.toLocaleString('pt-BR')}
                </div>
                <div className="mt-2 space-y-0.5">
                  {g.tables.filter((tbl) => tbl.rows > 0).map((tbl) => (
                    <div key={tbl.table} className="flex justify-between text-[11px] text-gray-500">
                      <span className="truncate">{tbl.table}</span>
                      <span className="font-semibold">{tbl.rows.toLocaleString('pt-BR')}</span>
                    </div>
                  ))}
                  {g.total_rows === 0 && <p className="text-[11px] text-gray-300">{t('common.empty')}</p>}
                </div>
              </div>
            ))}
          </div>

          {/* Periods */}
          {(inventory?.periods.length ?? 0) > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Calendar size={16} className="text-[#C9A959]" />
                <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">
                  {t('data.periods', { count: inventory?.periods.length ?? 0 })}
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {inventory?.periods.map((p) => (
                  <span key={p} className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium">{p}</span>
                ))}
              </div>
            </div>
          )}

          {/* Deposits history + versioning */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center gap-2 mb-1">
              <FileStack size={16} className="text-[#C9A959]" />
              <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">{t('data.depositHistory')}</h2>
            </div>
            <p className="text-xs text-gray-500 mb-3">{t('data.versions.subtitle')}</p>
            {activateMsg && (
              <div className="mb-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800 flex items-center gap-2">
                <CheckCircle size={14} /> {activateMsg}
              </div>
            )}
            {activateError && (
              <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 flex items-center gap-2">
                <AlertCircle size={14} /> {activateError}
              </div>
            )}
            {loading ? (
              <div className="flex justify-center py-6"><Loader2 className="animate-spin text-gray-400" size={20} /></div>
            ) : (inventory?.uploads.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">{t('data.noDeposits')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 uppercase tracking-wider border-b border-gray-100">
                      <th className="text-left py-2 pr-4">{t('data.origin')}</th>
                      <th className="text-left py-2 pr-4">{t('data.versions.column')}</th>
                      <th className="text-left py-2 pr-4">{t('data.fileOrType')}</th>
                      <th className="text-left py-2 pr-4">{t('data.periodsColumn')}</th>
                      <th className="text-right py-2 pr-4">{t('common.rows')}</th>
                      <th className="text-right py-2 pr-4">{t('common.date')}</th>
                      <th className="text-right py-2">{t('common.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory?.uploads.map((d) => (
                      <tr key={`${d.source}-${d.id}`} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            d.source === 'financial' ? 'bg-amber-100 text-amber-800' : 'bg-indigo-100 text-indigo-800'
                          }`}>
                            {t(`data.source.${d.source}`)}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            d.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                          }`}>
                            {d.version_label ?? 'v1'}
                            {d.is_active ? ` · ${t('data.versions.active')}` : ''}
                          </span>
                        </td>
                        <td className="py-2 pr-4 font-medium max-w-[200px] truncate">
                          {d.file_name || d.data_type || '—'}
                        </td>
                        <td className="py-2 pr-4 text-gray-500 max-w-[160px] truncate">{d.periods || '—'}</td>
                        <td className="py-2 pr-4 text-right text-green-700 font-semibold">{d.rows.toLocaleString('pt-BR')}</td>
                        <td className="py-2 pr-4 text-right text-gray-400">
                          {d.created_at ? new Date(d.created_at).toLocaleDateString('pt-BR') : '—'}
                        </td>
                        <td className="py-2 text-right">
                          {isAdmin && !d.is_active ? (
                            <button
                              type="button"
                              onClick={() => void handleActivate(d)}
                              disabled={activatingKey === `${d.source}-${d.id}`}
                              className="text-[10px] font-bold uppercase tracking-wider text-[#0A2342] border border-gray-200 rounded px-2 py-1 hover:bg-gray-50 disabled:opacity-40"
                            >
                              {activatingKey === `${d.source}-${d.id}`
                                ? t('data.versions.activating')
                                : t('data.versions.activate')}
                            </button>
                          ) : (
                            <span className="text-[10px] text-gray-300">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="text-[11px] text-gray-400 mt-3">{t('data.versions.erpNote')}</p>
            {!isAdmin && (
              <p className="text-[11px] text-gray-400 mt-1">{t('data.versions.adminOnly')}</p>
            )}
          </div>

          {/* Danger zone — purge */}
          {isAdmin ? (
            <div className="bg-white rounded-xl border-2 border-red-200 p-6 space-y-4">
              <div className="flex items-center gap-2">
                <ShieldAlert size={18} className="text-red-600" />
                <h2 className="text-sm font-bold text-red-700 uppercase tracking-wider">{t('data.dangerZone')}</h2>
              </div>
              <p className="text-sm text-gray-600">{t('data.dangerIntro')}</p>

              {/* Scope selector */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {SCOPES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    className={`text-left rounded-lg border-2 p-3 transition-colors ${
                      scope === s ? 'border-red-400 bg-red-50' : 'border-gray-150 hover:border-red-200'
                    }`}
                  >
                    <p className="font-bold text-sm text-[#0A2342]">{scopeTitle(s)}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{scopeDesc(s)}</p>
                  </button>
                ))}
              </div>

              {/* Confirmation */}
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
                  {t('data.confirmLabel', { token: '' })}{' '}
                  <span className="text-red-600 font-mono">{expectedToken}</span>
                </label>
                <input
                  type="text"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  placeholder={expectedToken}
                  className="w-full md:w-72 border-2 border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:border-red-400 focus:outline-none"
                />
              </div>

              <button
                onClick={handlePurge}
                disabled={purging || confirmation !== expectedToken}
                className="flex items-center gap-2 bg-red-600 text-white font-bold py-2.5 px-5 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {purging
                  ? <><Loader2 className="animate-spin" size={18} /> {t('data.deleting')}</>
                  : <><Trash2 size={18} /> {t('data.deleteButton', { scope: scopeTitle(scope) })}</>}
              </button>

              {purgeResult && (
                <div className="rounded-lg border-2 border-green-300 bg-green-50 p-4 text-sm">
                  <div className="flex items-center gap-2 font-bold text-green-800">
                    <CheckCircle size={18} />
                    {t('data.deletedCount', {
                      count: purgeResult.total_rows_deleted.toLocaleString('pt-BR'),
                      scope: purgeResult.scope,
                    })}
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {Object.entries(purgeResult.deleted)
                      .filter(([, n]) => n > 0)
                      .map(([table, n]) => (
                        <span key={table} className="px-2 py-0.5 rounded-full bg-green-200 text-green-800 text-[11px] font-medium">
                          {table}: {n}
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {purgeError && (
                <div className="rounded-lg border-2 border-red-300 bg-red-50 p-4 text-sm text-red-700 flex items-start gap-2">
                  <AlertTriangle size={18} className="shrink-0 mt-0.5" /> {purgeError}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-500 flex items-center gap-2">
              <ShieldAlert size={16} /> {t('data.adminOnly')}
            </div>
          )}
        </>
      )}
    </div>
  );
}
