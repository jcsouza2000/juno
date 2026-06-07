'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Users, UserPlus, Trash2, Loader2, AlertCircle, CheckCircle,
  ShieldAlert, Crown, KeyRound, Copy,
} from 'lucide-react';
import { api, getApiErrorMessage } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';

// ── Types ──────────────────────────────────────────────────────────────────
type TenantRole = 'owner' | 'admin' | 'member' | 'viewer';

interface Member {
  user_id: number;
  email: string;
  full_name: string | null;
  role_in_tenant: TenantRole;
  is_primary: boolean;
  global_role: string;
  is_active: boolean;
  joined_at: string | null;
}

interface CreateResponse {
  member: Member;
  created_user: boolean;
  temp_password: string | null;
}

const ROLE_LABELS: Record<TenantRole, string> = {
  owner: 'Proprietário',
  admin: 'Administrador',
  member: 'Membro',
  viewer: 'Visualizador',
};

const ROLE_STYLES: Record<TenantRole, string> = {
  owner: 'bg-[#C9A959]/20 text-[#8a6d2f]',
  admin: 'bg-indigo-100 text-indigo-800',
  member: 'bg-blue-100 text-blue-800',
  viewer: 'bg-gray-100 text-gray-600',
};

const ROLES: TenantRole[] = ['owner', 'admin', 'member', 'viewer'];

// ── Page ───────────────────────────────────────────────────────────────────
export default function TenantUsersPage() {
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();

  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<TenantRole>('member');
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState<CreateResponse | null>(null);
  const [createErr, setCreateErr] = useState<string | null>(null);

  const loadMembers = useCallback(async () => {
    if (!companyId) {
      setMembers([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/tenants/${companyId}/members`);
      setMembers(res.data);
    } catch (err: unknown) {
      setMembers([]);
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    const id = window.setTimeout(() => { void loadMembers(); }, 0);
    return () => window.clearTimeout(id);
  }, [loadMembers]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyId || !email.trim()) return;
    setCreating(true);
    setCreateMsg(null);
    setCreateErr(null);
    try {
      const res = await api.post(`/tenants/${companyId}/members`, {
        email: email.trim(),
        full_name: fullName.trim() || null,
        role_in_tenant: role,
      });
      setCreateMsg(res.data);
      setEmail('');
      setFullName('');
      setRole('member');
      await loadMembers();
    } catch (err: unknown) {
      setCreateErr(getApiErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const handleRoleChange = async (userId: number, newRole: TenantRole) => {
    if (!companyId) return;
    try {
      await api.patch(`/tenants/${companyId}/members/${userId}`, { role_in_tenant: newRole });
      await loadMembers();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    }
  };

  const handleRemove = async (member: Member) => {
    if (!companyId) return;
    if (!window.confirm(`Remover ${member.email} deste tenant? O usuário global é preservado.`)) return;
    try {
      await api.delete(`/tenants/${companyId}/members/${member.user_id}`);
      await loadMembers();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center gap-2">
          <Users size={22} className="text-[#0A2342]" />
          <h1 className="text-2xl font-bold text-[#0A2342]">Usuários do Tenant</h1>
        </div>
        <p className="text-gray-500 text-sm mt-1">
          Gerencie quem acessa <strong>{company?.name ?? 'a empresa ativa'}</strong> e o papel de cada um.
        </p>
      </div>

      {companyLoading && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 text-sm text-gray-500">
          Carregando tenant ativo...
        </div>
      )}

      {!companyLoading && !companyId && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-xl p-6 text-sm text-yellow-800">
          Nenhuma empresa vinculada ao usuário.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-sm text-red-700 flex items-start gap-2">
          <AlertCircle size={18} className="shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {companyId && (
        <>
          {/* Add member */}
          <form onSubmit={handleCreate} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <UserPlus size={18} className="text-[#C9A959]" />
              <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">Convidar usuário</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@empresa.com"
                className="md:col-span-2 border-2 border-gray-200 rounded-lg px-3 py-2 text-sm focus:border-[#0A2342] focus:outline-none"
              />
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Nome completo (opcional)"
                className="border-2 border-gray-200 rounded-lg px-3 py-2 text-sm focus:border-[#0A2342] focus:outline-none"
              />
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as TenantRole)}
                className="border-2 border-gray-200 rounded-lg px-3 py-2 text-sm focus:border-[#0A2342] focus:outline-none bg-white"
              >
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </div>
            <button
              type="submit"
              disabled={creating || !email.trim()}
              className="flex items-center gap-2 bg-[#C9A959] text-[#0A2342] font-bold py-2.5 px-5 rounded-lg hover:bg-[#b8943f] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {creating ? <><Loader2 className="animate-spin" size={18} /> Adicionando...</> : <><UserPlus size={18} /> Adicionar membro</>}
            </button>

            {createMsg && (
              <div className="rounded-lg border-2 border-green-300 bg-green-50 p-4 text-sm space-y-2">
                <div className="flex items-center gap-2 font-bold text-green-800">
                  <CheckCircle size={18} />
                  {createMsg.member.email} adicionado como {ROLE_LABELS[createMsg.member.role_in_tenant]}
                  {createMsg.created_user ? ' (usuário novo)' : ' (usuário já existente)'}
                </div>
                {createMsg.temp_password && (
                  <div className="flex items-center gap-2 bg-white border border-green-200 rounded-lg px-3 py-2">
                    <KeyRound size={16} className="text-amber-600 shrink-0" />
                    <span className="text-gray-600">Senha temporária:</span>
                    <code className="font-mono font-bold text-[#0A2342]">{createMsg.temp_password}</code>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard?.writeText(createMsg.temp_password!)}
                      className="ml-auto text-gray-400 hover:text-[#0A2342]"
                      title="Copiar"
                    >
                      <Copy size={15} />
                    </button>
                  </div>
                )}
                {createMsg.temp_password && (
                  <p className="text-xs text-green-700">
                    Anote e repasse com segurança — esta senha não será exibida novamente.
                  </p>
                )}
              </div>
            )}
            {createErr && (
              <div className="rounded-lg border-2 border-red-300 bg-red-50 p-3 text-sm text-red-700 flex items-start gap-2">
                <AlertCircle size={16} className="shrink-0 mt-0.5" /> {createErr}
              </div>
            )}
          </form>

          {/* Members list */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">
                Membros ({members.length})
              </h2>
            </div>
            {loading ? (
              <div className="flex justify-center py-10"><Loader2 className="animate-spin text-gray-400" size={22} /></div>
            ) : members.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-10">Nenhum membro neste tenant.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 text-xs uppercase tracking-wider border-b border-gray-100">
                      <th className="text-left py-3 px-6">Usuário</th>
                      <th className="text-left py-3 px-4">Papel</th>
                      <th className="text-left py-3 px-4">Entrou em</th>
                      <th className="text-right py-3 px-6">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr key={m.user_id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-3 px-6">
                          <div className="flex items-center gap-2">
                            {m.role_in_tenant === 'owner' && <Crown size={14} className="text-[#C9A959]" />}
                            <div>
                              <p className="font-semibold text-[#0A2342]">{m.full_name || m.email.split('@')[0]}</p>
                              <p className="text-xs text-gray-400">{m.email}</p>
                            </div>
                            {m.is_primary && (
                              <span className="text-[10px] font-bold bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded uppercase">Primário</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <select
                            value={m.role_in_tenant}
                            onChange={(e) => handleRoleChange(m.user_id, e.target.value as TenantRole)}
                            className={`text-xs font-bold rounded-full px-2.5 py-1 border-0 cursor-pointer ${ROLE_STYLES[m.role_in_tenant]}`}
                          >
                            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                          </select>
                        </td>
                        <td className="py-3 px-4 text-gray-400 text-xs">
                          {m.joined_at ? new Date(m.joined_at).toLocaleDateString('pt-BR') : '—'}
                        </td>
                        <td className="py-3 px-6 text-right">
                          <button
                            onClick={() => handleRemove(m)}
                            className="text-red-400 hover:text-red-600 transition-colors"
                            title="Remover do tenant"
                          >
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-xs text-gray-500 flex items-start gap-2">
            <ShieldAlert size={15} className="shrink-0 mt-0.5" />
            <span>
              O último <strong>Proprietário</strong> não pode ser rebaixado nem removido. Remover um membro
              desfaz apenas o vínculo com este tenant — o usuário global é preservado.
            </span>
          </div>
        </>
      )}
    </div>
  );
}
