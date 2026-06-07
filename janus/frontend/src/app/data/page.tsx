'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import {
  Database, Trash2, AlertTriangle, RefreshCw, Loader2,
  FileStack, Calendar, ShieldAlert, CheckCircle, AlertCircle,
} from 'lucide-react';
import { api, getApiErrorMessage } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';

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

const SCOPE_LABELS: Record<Scope, { title: string; desc: string }> = {
  financial: { title: 'Financeiro', desc: 'DRE, Balanço, DFC e lançamentos. Também recalcula KPIs.' },
  erp: { title: 'Operacional ERP', desc: 'Produtos, clientes, fornecedores, pedidos e estoque.' },
  all: { title: 'Tudo', desc: 'Todos os dados de negócio do tenant (mantém usuários e conexões).' },
};

const GROUP_ICON: Record<string, React.ReactNode> = {
  financial: <FileStack size={16} className="text-[#C9A959]" />,
  erp: <Database size={16} className="text-[#C9A959]" />,
  derived: <RefreshCw size={16} className="text-[#C9A959]" />,
};

// ── Page ───────────────────────────────────────────────────────────────────
export default function DataPage() {
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();
  const { data: session } = useSession();
  const role = session?.user?.role;
  const isAdmin = role === 'admin' || role === 'platform_admin';

  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Purge state
  const [scope, setScope] = useState<Scope>('financial');
  const [confirmation, setConfirmation] = useState('');
  const [purging, setPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState<PurgeResult | null>(null);
  const [purgeError, setPurgeError] = useState<string | null>(null);

  const expectedToken = companyId != null ? `PURGE-${companyId}` : '';

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

  const handlePurge = async () => {
    if (!companyId || confirmation !== expectedToken) return;
    if (!window.confirm(
      `Confirma a exclusão "${SCOPE_LABELS[scope].title}" do tenant ${company?.name ?? companyId}? ` +
      `Esta ação é irreversível.`,
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
          <h1 className="text-2xl font-bold text-[#0A2342]">Meus Dados</h1>
          <p className="text-gray-500 text-sm mt-1">
            Tudo que está depositado no JUNO para a empresa ativa — e exclusão controlada
            sob comando do administrador.
          </p>
        </div>
        <button
          onClick={() => void loadInventory()}
          disabled={loading || !companyId}
          className="flex items-center gap-2 text-sm font-semibold text-[#0A2342] border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50 disabled:opacity-40"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Atualizar
        </button>
      </div>

      {companyLoading && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 text-sm text-gray-500">
          Carregando tenant ativo...
        </div>
      )}

      {!companyLoading && !companyId && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-xl p-6 text-sm text-yellow-800">
          Nenhuma empresa vinculada ao usuário. Vincule um tenant para ver os dados.
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
              <p className="text-xs uppercase tracking-widest font-semibold text-[#C9A959]">Total de registros</p>
              <div className="text-3xl font-extrabold mt-1 text-white">
                {loading ? '—' : (inventory?.total_rows ?? 0).toLocaleString('pt-BR')}
              </div>
              <p className="text-xs mt-1 text-white/60">{company?.name ?? 'Tenant ativo'}</p>
            </div>

            {(inventory?.groups ?? []).map((g) => (
              <div key={g.group} className="rounded-xl border border-gray-100 bg-white p-4">
                <div className="flex items-center gap-2">
                  {GROUP_ICON[g.group] ?? <Database size={16} className="text-[#C9A959]" />}
                  <p className="text-xs uppercase tracking-widest font-semibold text-gray-400">{g.label}</p>
                </div>
                <div className="text-2xl font-extrabold mt-1 text-[#0A2342]">
                  {g.total_rows.toLocaleString('pt-BR')}
                </div>
                <div className="mt-2 space-y-0.5">
                  {g.tables.filter((t) => t.rows > 0).map((t) => (
                    <div key={t.table} className="flex justify-between text-[11px] text-gray-500">
                      <span className="truncate">{t.table}</span>
                      <span className="font-semibold">{t.rows.toLocaleString('pt-BR')}</span>
                    </div>
                  ))}
                  {g.total_rows === 0 && <p className="text-[11px] text-gray-300">vazio</p>}
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
                  Períodos disponíveis ({inventory?.periods.length})
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {inventory?.periods.map((p) => (
                  <span key={p} className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium">{p}</span>
                ))}
              </div>
            </div>
          )}

          {/* Deposits history */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center gap-2 mb-3">
              <FileStack size={16} className="text-[#C9A959]" />
              <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">Histórico de depósitos</h2>
            </div>
            {loading ? (
              <div className="flex justify-center py-6"><Loader2 className="animate-spin text-gray-400" size={20} /></div>
            ) : (inventory?.uploads.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">Nenhum depósito registrado.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 uppercase tracking-wider border-b border-gray-100">
                      <th className="text-left py-2 pr-4">Origem</th>
                      <th className="text-left py-2 pr-4">Arquivo / Tipo</th>
                      <th className="text-left py-2 pr-4">Períodos</th>
                      <th className="text-right py-2 pr-4">Linhas</th>
                      <th className="text-right py-2">Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory?.uploads.map((d) => (
                      <tr key={`${d.source}-${d.id}`} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            d.source === 'financial' ? 'bg-amber-100 text-amber-800' : 'bg-indigo-100 text-indigo-800'
                          }`}>
                            {d.source === 'financial' ? 'Financeiro' : 'ERP'}
                          </span>
                        </td>
                        <td className="py-2 pr-4 font-medium max-w-[200px] truncate">
                          {d.file_name || d.data_type || '—'}
                        </td>
                        <td className="py-2 pr-4 text-gray-500 max-w-[160px] truncate">{d.periods || '—'}</td>
                        <td className="py-2 pr-4 text-right text-green-700 font-semibold">{d.rows.toLocaleString('pt-BR')}</td>
                        <td className="py-2 text-right text-gray-400">
                          {d.created_at ? new Date(d.created_at).toLocaleDateString('pt-BR') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Danger zone — purge */}
          {isAdmin ? (
            <div className="bg-white rounded-xl border-2 border-red-200 p-6 space-y-4">
              <div className="flex items-center gap-2">
                <ShieldAlert size={18} className="text-red-600" />
                <h2 className="text-sm font-bold text-red-700 uppercase tracking-wider">Zona de exclusão controlada</h2>
              </div>
              <p className="text-sm text-gray-600">
                A exclusão remove apenas <strong>dados de negócio</strong> do tenant. Usuários, vínculos,
                conexões ERP e auditoria são <strong>preservados</strong>. A ação é irreversível.
              </p>

              {/* Scope selector */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {(Object.keys(SCOPE_LABELS) as Scope[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    className={`text-left rounded-lg border-2 p-3 transition-colors ${
                      scope === s ? 'border-red-400 bg-red-50' : 'border-gray-150 hover:border-red-200'
                    }`}
                  >
                    <p className="font-bold text-sm text-[#0A2342]">{SCOPE_LABELS[s].title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{SCOPE_LABELS[s].desc}</p>
                  </button>
                ))}
              </div>

              {/* Confirmation */}
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
                  Para confirmar, digite <span className="text-red-600 font-mono">{expectedToken}</span>
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
                  ? <><Loader2 className="animate-spin" size={18} /> Excluindo...</>
                  : <><Trash2 size={18} /> Excluir dados ({SCOPE_LABELS[scope].title})</>}
              </button>

              {purgeResult && (
                <div className="rounded-lg border-2 border-green-300 bg-green-50 p-4 text-sm">
                  <div className="flex items-center gap-2 font-bold text-green-800">
                    <CheckCircle size={18} />
                    {purgeResult.total_rows_deleted.toLocaleString('pt-BR')} registros excluídos
                    (escopo: {purgeResult.scope})
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
              <ShieldAlert size={16} /> A exclusão de dados é restrita a administradores do tenant.
            </div>
          )}
        </>
      )}
    </div>
  );
}
