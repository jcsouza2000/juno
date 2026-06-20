'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import {
  Archive, CalendarCheck, CameraIcon, Loader2, AlertCircle, CheckCircle, ShieldAlert, Lock,
} from 'lucide-react';
import { api, getApiErrorMessage } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import { useI18n } from '@/lib/i18n';

// ── Types ──────────────────────────────────────────────────────────────────
interface MonthlyClose {
  id: number;
  year: number;
  month: number;
  status: string;
  closed_at: string | null;
  closed_by: number | null;
  snapshot?: { score?: { overall?: number | null } | null } | null;
}
interface DailySnapshot {
  id: number;
  snapshot_date: string;
  created_at: string | null;
  updated_at: string | null;
}

const now = new Date();

export default function RetentionPage() {
  const { companyId, isLoading: companyLoading } = useActiveCompany();
  const { data: session } = useSession();
  const { t } = useI18n();
  const role = session?.user?.role;
  const isAdmin = role === 'admin' || role === 'platform_admin';

  const [closes, setCloses] = useState<MonthlyClose[]>([]);
  const [snapshots, setSnapshots] = useState<DailySnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [busy, setBusy] = useState(false);

  // Guard contra empresa-fantasma: se o companyId mudar durante o fetch (ex.:
  // resolucao tardia do tenant ativo), uma chamada antiga pode falhar com 403
  // "Acesso negado" e fixar o erro mesmo apos a carga correta. So a ULTIMA
  // chamada aplica resultado/erro.
  const reqRef = useRef(0);

  const load = useCallback(async () => {
    if (!companyId) { setCloses([]); setSnapshots([]); return; }
    const reqId = ++reqRef.current;
    setLoading(true);
    setError(null);
    try {
      const [c, s] = await Promise.all([
        api.get(`/retention/${companyId}/monthly-close`),
        api.get(`/retention/${companyId}/daily-snapshot?limit=30`),
      ]);
      if (reqId !== reqRef.current) return;
      setCloses(c.data);
      setSnapshots(s.data);
    } catch (err: unknown) {
      if (reqId !== reqRef.current) return;
      setError(getApiErrorMessage(err));
    } finally {
      if (reqId === reqRef.current) setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    const id = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  const createClose = async () => {
    if (!companyId) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      await api.post(`/retention/${companyId}/monthly-close`, { year, month });
      setMsg(t('retention.closeCreated', { year, month: String(month).padStart(2, '0') }));
      await load();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const captureSnapshot = async () => {
    if (!companyId) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const res = await api.post(`/retention/${companyId}/daily-snapshot`, {});
      setMsg(t('retention.snapshotCreated', { date: res.data?.snapshot_date ?? '' }));
      await load();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleDateString('pt-BR') : '—');

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center gap-2">
          <Archive size={22} className="text-[#0A2342]" />
          <h1 className="text-2xl font-bold text-[#0A2342]">{t('retention.title')}</h1>
        </div>
        <p className="text-gray-500 text-sm mt-1">{t('retention.subtitle')}</p>
      </div>

      {companyLoading && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 text-sm text-gray-500">{t('common.loadingTenant')}</div>
      )}
      {!companyLoading && !companyId && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-xl p-6 text-sm text-yellow-800">{t('common.noCompany')}</div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-sm text-red-700 flex items-start gap-2">
          <AlertCircle size={18} className="shrink-0 mt-0.5" /> {error}
        </div>
      )}
      {msg && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-800 flex items-center gap-2">
          <CheckCircle size={18} /> {msg}
        </div>
      )}

      {companyId && (
        <>
          {/* Monthly closes */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <CalendarCheck size={18} className="text-[#C9A959]" />
              <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">{t('retention.monthlyTitle')}</h2>
            </div>
            <p className="text-xs text-gray-500">{t('retention.monthlySubtitle')}</p>

            {isAdmin ? (
              <div className="flex flex-wrap items-end gap-3">
                <label className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                  {t('retention.year')}
                  <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))}
                    className="mt-1 block w-28 border-2 border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:border-[#0A2342] focus:outline-none" />
                </label>
                <label className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                  {t('retention.month')}
                  <input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))}
                    className="mt-1 block w-20 border-2 border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:border-[#0A2342] focus:outline-none" />
                </label>
                <button onClick={createClose} disabled={busy}
                  className="flex items-center gap-2 bg-[#0A2342] text-white font-bold py-2.5 px-5 rounded-lg hover:bg-[#0d2d57] transition-colors disabled:opacity-40">
                  {busy ? <><Loader2 className="animate-spin" size={18} /> {t('retention.creating')}</> : <><Lock size={16} /> {t('retention.createClose')}</>}
                </button>
              </div>
            ) : (
              <div className="text-xs text-gray-500 flex items-center gap-2"><ShieldAlert size={14} /> {t('retention.adminOnly')}</div>
            )}

            {loading ? (
              <div className="flex justify-center py-6"><Loader2 className="animate-spin text-gray-400" size={20} /></div>
            ) : closes.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">{t('retention.noCloses')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 text-xs uppercase tracking-wider border-b border-gray-100">
                      <th className="text-left py-2 pr-4">{t('retention.month')}</th>
                      <th className="text-left py-2 pr-4">{t('retention.status')}</th>
                      <th className="text-right py-2 pr-4">{t('retention.score')}</th>
                      <th className="text-right py-2">{t('retention.closedAt')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closes.map((c) => (
                      <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4 font-mono font-semibold text-[#0A2342]">{c.year}-{String(c.month).padStart(2, '0')}</td>
                        <td className="py-2 pr-4">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-[10px] font-bold uppercase">
                            <Lock size={10} /> {c.status}
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {c.snapshot?.score?.overall != null ? Number(c.snapshot.score.overall).toFixed(1) : '—'}
                        </td>
                        <td className="py-2 text-right text-gray-400">{fmtDate(c.closed_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Daily snapshots */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CameraIcon size={18} className="text-[#C9A959]" />
                <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">{t('retention.snapshotsTitle')}</h2>
              </div>
              {isAdmin && (
                <button onClick={captureSnapshot} disabled={busy}
                  className="flex items-center gap-2 text-sm font-semibold text-[#0A2342] border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50 disabled:opacity-40">
                  {busy ? <Loader2 className="animate-spin" size={14} /> : <CameraIcon size={14} />} {t('retention.captureSnapshot')}
                </button>
              )}
            </div>

            {loading ? (
              <div className="flex justify-center py-6"><Loader2 className="animate-spin text-gray-400" size={20} /></div>
            ) : snapshots.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">{t('retention.noSnapshots')}</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {snapshots.map((s) => (
                  <span key={s.id} className="px-2.5 py-1 rounded-lg bg-[#F0F4F8] text-[#0A2342] text-xs font-mono">
                    {s.snapshot_date}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-xs text-gray-500 flex items-start gap-2">
            <ShieldAlert size={15} className="shrink-0 mt-0.5" />
            <span>{t('retention.immutableNote')}</span>
          </div>
        </>
      )}
    </div>
  );
}
