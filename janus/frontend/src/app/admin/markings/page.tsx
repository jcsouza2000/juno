'use client';

import { useCallback, useEffect, useState } from 'react';
import { Shield, Plus, X, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

interface MarkingDef {
  description: string;
  enforcement: 'row_level' | 'column_level' | 'object_level';
  requires_role: string[];
  requires_marking_grant: boolean;
}

interface Grant {
  id: number;
  user_id: number;
  marking: string;
  granted_by: number;
  granted_at: string;
  valid_until: string | null;
  reason: string | null;
  revoked: boolean;
  revoked_at: string | null;
  revoked_by: number | null;
}

export default function MarkingsAdminPage() {
  const [markings, setMarkings] = useState<Record<string, MarkingDef>>({});
  const [grants, setGrants] = useState<Grant[]>([]);
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Form de novo grant
  const [newUserId, setNewUserId] = useState('');
  const [newMarking, setNewMarking] = useState('');
  const [newReason, setNewReason] = useState('');
  const [creating, setCreating] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [defs, list] = await Promise.all([
        api.get('/api/v1/markings'),
        api.get(`/api/v1/markings/grants?include_revoked=${includeRevoked}&limit=200`),
      ]);
      setMarkings(defs.data?.markings ?? {});
      setGrants(Array.isArray(list.data) ? list.data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [includeRevoked]);

  // Guard: usuario nao-admin nao deve ver esta pagina
  useEffect(() => {
    api.get('/api/v1/markings/me').then(res => {
      const role = res.data?.role;
      if (role !== 'admin' && role !== 'data_steward') {
        window.location.href = '/';
      }
    }).catch(() => {
      window.location.href = process.env.NODE_ENV === 'production' ? '/login' : '/';
    });
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadAll();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadAll]);

  const handleGrant = async () => {
    setCreating(true);
    setError('');
    try {
      await api.post('/api/v1/markings/grants', {
        user_id: Number(newUserId),
        marking: newMarking,
        reason: newReason || null,
      });
      setNewUserId('');
      setNewMarking('');
      setNewReason('');
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally { setCreating(false); }
  };

  const handleRevoke = async (id: number) => {
    if (!confirm(`Revogar grant #${id}?`)) return;
    try {
      await api.delete(`/api/v1/markings/grants/${id}`, { data: { reason: 'revogado via admin UI' } });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="border-b border-gray-200 pb-4 flex justify-between items-end">
        <div>
          <div className="flex items-center gap-2">
            <Shield size={22} className="text-[#C9A959]" />
            <h1 className="text-2xl font-bold text-[#0A2342]">Markings &amp; Grants</h1>
          </div>
          <p className="text-gray-500 text-sm mt-1">
            Conceda ou revogue markings sens&iacute;veis. Admin/data_steward apenas.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-2">
          <AlertCircle size={18} className="text-red-500" />
          <span className="text-sm text-red-700">{error}</span>
        </div>
      )}

      {/* Catalogo */}
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h2 className="font-bold text-[#0A2342] mb-3 text-sm uppercase tracking-wider">
          Markings declaradas no _markings.yaml
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(markings).map(([name, def]) => (
            <div key={name} className="border border-gray-100 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-bold text-[#0A2342]">{name}</span>
                <span className="text-[10px] uppercase tracking-wider bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                  {def.enforcement}
                </span>
                {def.requires_marking_grant && (
                  <span className="text-[10px] uppercase tracking-wider bg-[#C9A959]/20 text-[#0A2342] px-1.5 py-0.5 rounded">
                    requer grant
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-600">{def.description}</p>
              {def.requires_role.length > 0 && (
                <p className="text-xs text-gray-500 mt-1">
                  Roles: {def.requires_role.join(', ')}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Form de grant */}
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h2 className="font-bold text-[#0A2342] mb-3 text-sm uppercase tracking-wider">
          Conceder novo grant
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">User ID</label>
            <input
              type="number"
              value={newUserId}
              onChange={e => setNewUserId(e.target.value)}
              className="w-full border border-gray-200 rounded-md px-2 py-1.5 text-sm"
              placeholder="42"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Marking</label>
            <select
              value={newMarking}
              onChange={e => setNewMarking(e.target.value)}
              className="w-full border border-gray-200 rounded-md px-2 py-1.5 text-sm"
            >
              <option value="">— selecione —</option>
              {Object.keys(markings).map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs text-gray-500 mb-1">Motivo (audit)</label>
            <input
              type="text"
              value={newReason}
              onChange={e => setNewReason(e.target.value)}
              className="w-full border border-gray-200 rounded-md px-2 py-1.5 text-sm"
              placeholder="auditoria de compliance Q2 aprovou..."
            />
          </div>
          <button
            onClick={handleGrant}
            disabled={!newUserId || !newMarking || creating}
            className="md:col-span-4 flex items-center justify-center gap-2 bg-[#0A2342] text-white font-bold py-2 rounded-md hover:bg-[#0c2d54] disabled:opacity-40"
          >
            {creating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            Conceder
          </button>
        </div>
      </div>

      {/* Listagem de grants */}
      <div className="bg-white rounded-xl border border-gray-100">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <h2 className="font-bold text-[#0A2342] text-sm uppercase tracking-wider">
            Grants ({grants.length})
          </h2>
          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={includeRevoked}
              onChange={e => setIncludeRevoked(e.target.checked)}
            />
            mostrar revogados
          </label>
        </div>
        {loading ? (
          <div className="p-6 text-center"><Loader2 size={20} className="animate-spin mx-auto text-gray-400" /></div>
        ) : grants.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">Nenhum grant.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 uppercase tracking-wider border-b border-gray-100">
                <th className="text-left py-2 px-4">User</th>
                <th className="text-left py-2 px-4">Marking</th>
                <th className="text-left py-2 px-4">Concedido em</th>
                <th className="text-left py-2 px-4">Valido at&eacute;</th>
                <th className="text-left py-2 px-4">Motivo</th>
                <th className="text-left py-2 px-4">Status</th>
                <th className="text-right py-2 px-4">A&ccedil;&otilde;es</th>
              </tr>
            </thead>
            <tbody>
              {grants.map(g => (
                <tr key={g.id} className={g.revoked ? 'bg-gray-50' : 'hover:bg-gray-50'}>
                  <td className="py-2 px-4 font-mono">{g.user_id}</td>
                  <td className="py-2 px-4 font-semibold">{g.marking}</td>
                  <td className="py-2 px-4 text-gray-600 text-xs">
                    {new Date(g.granted_at).toLocaleString('pt-BR')}
                  </td>
                  <td className="py-2 px-4 text-gray-600 text-xs">
                    {g.valid_until ? new Date(g.valid_until).toLocaleDateString('pt-BR') : '—'}
                  </td>
                  <td className="py-2 px-4 text-gray-600 text-xs max-w-[200px] truncate">
                    {g.reason ?? '—'}
                  </td>
                  <td className="py-2 px-4">
                    {g.revoked ? (
                      <span className="text-xs font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded-full">revogado</span>
                    ) : (
                      <span className="text-xs font-bold text-green-700 bg-green-100 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <CheckCircle size={10} /> ativo
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-4 text-right">
                    {!g.revoked && (
                      <button
                        onClick={() => handleRevoke(g.id)}
                        className="text-xs text-red-600 hover:text-red-800 inline-flex items-center gap-1"
                      >
                        <X size={12} /> Revogar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
