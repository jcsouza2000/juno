'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  CheckSquare, Square, ChevronDown, ChevronUp, FileText, Database,
  Building2, Plus, RefreshCw, Upload, CheckCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { setActiveCompany, useActiveCompany } from '@/lib/tenant';

// ── Config ────────────────────────────────────────────────────────────────────
const CHECKLIST = [
  {
    id: 'sponsor',
    label: 'Sponsor interno identificado',
    desc: 'Quem será o responsável pelo projeto dentro da empresa?',
    placeholder: 'Ex: Diretor Industrial, CFO, Gerente de Operações...',
  },
  {
    id: 'erp',
    label: 'ERP utilizado mapeado',
    desc: 'Qual sistema ERP a empresa utiliza atualmente?',
    placeholder: 'Ex: TOTVS Protheus, SAP B1, Sankhya, Oracle, Senior...',
  },
  {
    id: 'data',
    label: 'Dados a exportar definidos',
    desc: 'Quais módulos serão exportados para o JUNO? (Produtos, Pedidos, OPs, Clientes)',
    placeholder: 'Ex: Produtos + Ordens de Produção + Pedidos de Venda',
  },
  {
    id: 'validator',
    label: 'Responsável pela validação dos números definido',
    desc: 'Quem na empresa vai confirmar que os números do JUNO estão corretos?',
    placeholder: 'Ex: Controller, Analista de BI, Gerente Financeiro...',
  },
  {
    id: 'problem',
    label: 'Problema prioritário definido',
    desc: 'Qual é o maior problema operacional que o piloto vai atacar primeiro?',
    placeholder: 'Ex: Margem negativa no produto X, Atrasos na linha Y, Custo fora de controle...',
  },
  {
    id: 'roi',
    label: 'ROI esperado estimado',
    desc: 'Qual o retorno financeiro esperado com a resolução do problema prioritário?',
    placeholder: 'Ex: Recuperar R$ 200k/mês em margem no produto X',
  },
];

const DATA_REQUEST = [
  { type: 'products',           label: 'Produtos',           file: 'exportar_produtos.csv',           priority: 'Alta',  columns: 'Código, Nome, Categoria, Custo Padrão, Preço de Venda',         format: 'CSV / Excel' },
  { type: 'customers',          label: 'Clientes',           file: 'exportar_clientes.csv',            priority: 'Alta',  columns: 'Código, Nome, Segmento / Tipo',                                   format: 'CSV / Excel' },
  { type: 'sales_orders',       label: 'Pedidos de Venda',   file: 'exportar_pedidos.csv',             priority: 'Alta',  columns: 'Nº Pedido, Cliente, Produto, Receita, Desconto, Data',           format: 'CSV / Excel' },
  { type: 'production_orders',  label: 'Ordens de Produção', file: 'exportar_ops.csv',                 priority: 'Alta',  columns: 'Nº OP, Produto, Qtd Planejada, Qtd Real, Custo Plan., Custo Real, Datas, Status', format: 'CSV / Excel' },
  { type: 'inventory',          label: 'Estoque',            file: 'exportar_estoque.csv',             priority: 'Média', columns: 'Produto, Quantidade, Valor Unitário, Data',                       format: 'CSV / Excel' },
  { type: 'financials',         label: 'Faturamento',        file: 'exportar_faturamento.csv',         priority: 'Média', columns: 'Mês, Produto, Receita Bruta, Receita Líquida, Margem',            format: 'CSV / Excel' },
  { type: 'costs',              label: 'Custos Industriais', file: 'exportar_custos.csv',              priority: 'Média', columns: 'Produto / OP, Tipo Custo, Valor, Período',                        format: 'CSV / Excel' },
  { type: 'suppliers',          label: 'Fornecedores',       file: 'exportar_fornecedores.csv',        priority: 'Baixa', columns: 'Código, Nome, Insumo Fornecido, Preço Médio',                    format: 'CSV / Excel' },
];

const UPLOAD_FLOW = [
  {
    step: 1,
    title: 'Criar ou selecionar empresa piloto',
    detail: 'Ex: Empresa Piloto X, AAA Beleza, Cliente Metalúrgica Sul.',
    href: '/pilot',
  },
  {
    step: 2,
    title: 'Clientes, produtos, pedidos e OPs',
    detail: 'Upload na aba Integrações ERP, usando os arquivos 01 a 04.',
    href: '/integrations',
  },
  {
    step: 3,
    title: 'DRE, Balanço e DFC',
    detail: 'Upload na aba Financeiro, usando o arquivo 05.',
    href: '/financials',
  },
  {
    step: 4,
    title: 'Validar e apresentar',
    detail: 'Auditoria, KPIs Executivos e Minha Empresa.',
    href: '/audit',
  },
];

const PRESENTATION_SLIDES = [
  {
    n: 1,
    title: 'O Problema',
    icon: '⚠️',
    content: 'A indústria opera com dados fragmentados: ERP não conversa com BI, margem real é desconhecida, atrasos são gerenciados no Excel. A tomada de decisão é lenta e baseada em intuição.',
    talking_points: ['Quanto você perde por mês por não saber a margem real?', 'Quantas decisões são tomadas sem dados confiáveis?', 'O CFO confia nos números que recebe hoje?'],
  },
  {
    n: 2,
    title: 'O Que o JUNO Integra',
    icon: '🔌',
    content: 'O JUNO se conecta ao ERP via exportação CSV/Excel. Sem integração complexa. Sem risco de sistema. Em 30 minutos, os dados da empresa estão dentro da plataforma.',
    talking_points: ['Exportação do ERP em 5 minutos', 'Upload via interface web', 'Validação automática dos dados importados'],
  },
  {
    n: 3,
    title: 'O Que o JUNO Revela',
    icon: '🔍',
    content: 'Score JUNO 0-100, margem real por produto, ordens em atraso, custo vs. planejado, insights automáticos e diagnóstico 360°. Tudo em uma tela, com exportação em PDF executivo.',
    talking_points: ['Score de saúde operacional em tempo real', 'Quais produtos estão destruindo a margem?', 'Diagnóstico 360° exportável para o conselho'],
  },
  {
    n: 4,
    title: 'Como o Data Trust Garante Confiança',
    icon: '🛡️',
    content: 'Antes de mostrar qualquer número ao CFO, o JUNO valida automaticamente os dados importados com um Data Trust Score. Problemas são identificados, explicados e resolvidos antes da apresentação.',
    talking_points: ['Data Trust Score 0-100', 'Detecção de receita negativa, custo ausente, inconsistências', '"Os números do JUNO batem com o ERP"'],
  },
  {
    n: 5,
    title: 'Como Será o Piloto',
    icon: '🚀',
    content: 'Piloto de 30 dias. Semana 1: setup e importação. Semana 2: validação com o responsável interno. Semana 3: apresentação ao board. Semana 4: avaliação de ROI e decisão de expansão.',
    talking_points: ['30 dias, dados reais, sem integração técnica', 'Acompanhamento semanal via JUNO Dashboard', 'PDF executivo ao final do piloto'],
  },
  {
    n: 6,
    title: 'Resultados Esperados em 30 Dias',
    icon: '💰',
    content: 'Ao final do piloto, a empresa terá: visibilidade real de margem por produto, identificação dos gargalos de produção, estimativa de perda mensal e plano de ação com ROI calculado.',
    talking_points: ['Identificar R$ X de perda mensal evitável', '3–5 decisões táticas baseadas em dados reais', 'Base para expansão da plataforma (ERP direto, BI, multi-unidade)'],
  },
];

const NEXT_EVOLUTION = [
  { version: 'v0.4', title: 'ERP Connectors', desc: 'Integração direta com TOTVS, SAP B1, Sankhya e Senior via API/banco. Zero exportação manual.' },
  { version: 'v0.5', title: 'BI & Analytics', desc: 'Dashboards customizáveis por perfil (CEO, CFO, COO), gráficos de tendência e comparativos históricos.' },
  { version: 'v0.6', title: 'Multi-Unidade', desc: 'Consolidação de múltiplas plantas e unidades de negócio em um único diagnóstico executivo.' },
  { version: 'v1.0', title: 'Plataforma Completa', desc: 'Alertas proativos, predição de risco operacional, integração com sistemas de automação industrial.' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function PriorityBadge({ p }: { p: string }) {
  const m: Record<string, string> = {
    Alta:  'bg-red-100 text-red-800 border-red-200',
    Média: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    Baixa: 'bg-gray-100 text-gray-600 border-gray-200',
  };
  return <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${m[p] ?? m.Baixa}`}>{p}</span>;
}

interface Tenant {
  id: number;
  name: string;
  sector?: string;
  role?: string;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function PilotPage() {
  const { company } = useActiveCompany();
  const [checks, setChecks]   = useState<Record<string, boolean>>({});
  const [notes, setNotes]     = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ tenant: true, upload: true, checklist: true, data: true });
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantLoading, setTenantLoading] = useState(false);
  const [tenantError, setTenantError] = useState('');
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newCompanySector, setNewCompanySector] = useState('Piloto industrial');
  const [creatingTenant, setCreatingTenant] = useState(false);

  const toggle = (id: string) => setChecks(p => ({ ...p, [id]: !p[id] }));
  const toggleSection = (id: string) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  const done  = CHECKLIST.filter(c => checks[c.id]).length;
  const total = CHECKLIST.length;
  const pct   = Math.round((done / total) * 100);

  const readiness = pct >= 100 ? 'PRONTO PARA PILOTO ✅' : pct >= 66 ? 'Em preparação...' : 'Configuração inicial';
  const readyColor = pct >= 100 ? 'text-green-700' : pct >= 66 ? 'text-yellow-700' : 'text-gray-500';

  const loadTenants = async () => {
    setTenantLoading(true);
    setTenantError('');
    try {
      const res = await api.get('/tenants/my');
      const list = res.data?.tenants ?? [];
      setTenants(list);
      if (!company && list.length > 0) {
        setActiveCompany({ id: list[0].id, name: list[0].name });
      }
    } catch {
      setTenantError('Nao foi possivel carregar empresas vinculadas ao usuario.');
    } finally {
      setTenantLoading(false);
    }
  };

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadTenants();
    }, 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createPilotCompany = async () => {
    const name = newCompanyName.trim();
    const sector = newCompanySector.trim() || 'Piloto';
    if (!name) {
      setTenantError('Informe o nome da empresa piloto.');
      return;
    }

    setCreatingTenant(true);
    setTenantError('');
    try {
      const res = await api.post('/tenants/', null, { params: { name, sector } });
      const created = { id: res.data.id, name: res.data.name, sector: res.data.sector };
      setTenants(prev => [created, ...prev.filter(t => t.id !== created.id)]);
      setActiveCompany({ id: created.id, name: created.name });
      setNewCompanyName('');
    } catch (err: unknown) {
      const detail = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : undefined;
      setTenantError(detail ?? 'Erro ao criar empresa piloto. Verifique se o usuario e admin.');
    } finally {
      setCreatingTenant(false);
    }
  };

  const copyDataRequest = () => {
    const text = DATA_REQUEST.map(r =>
      `${r.label} (${r.priority})\nArquivo: ${r.file}\nColunas: ${r.columns}\nFormato: ${r.format}`
    ).join('\n\n');
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="space-y-8 max-w-4xl">

      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold bg-[#0A2342] text-[#C9A959] px-2 py-0.5 rounded uppercase tracking-wider">Pilot Readiness</span>
        </div>
        <h1 className="text-2xl font-bold text-[#0A2342]">Pacote de Piloto JUNO</h1>
        <p className="text-gray-500 text-sm mt-1">Checklist comercial, data request e estrutura de apresentação para o cliente piloto.</p>
      </div>

      {/* Readiness meter */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-widest">Prontidão do Piloto</p>
            <p className={`text-xl font-extrabold mt-0.5 ${readyColor}`}>{readiness}</p>
          </div>
          <div className="text-right">
            <span className={`text-4xl font-extrabold ${readyColor}`}>{pct}%</span>
            <p className="text-xs text-gray-400">{done}/{total} itens</p>
          </div>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-500 ${pct >= 100 ? 'bg-green-500' : pct >= 66 ? 'bg-yellow-400' : 'bg-[#C9A959]'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Tenant setup */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <button onClick={() => toggleSection('tenant')}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors">
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-[#0A2342]" />
            <h2 className="font-bold text-[#0A2342]">Empresa do Piloto</h2>
            <span className="text-xs text-gray-400">criar ou selecionar antes do upload</span>
          </div>
          {expanded.tenant ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </button>

        {expanded.tenant && (
          <div className="border-t border-gray-100 p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#F0F4F8] p-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-gray-400">Empresa ativa</p>
                <p className="text-lg font-extrabold text-[#0A2342]">{company?.name ?? 'Nenhuma empresa selecionada'}</p>
              </div>
              <button
                onClick={() => void loadTenants()}
                disabled={tenantLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-xs font-bold text-[#0A2342] hover:border-[#0A2342] disabled:opacity-50"
              >
                <RefreshCw size={14} className={tenantLoading ? 'animate-spin' : ''} />
                Atualizar empresas
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                type="text"
                value={newCompanyName}
                onChange={e => setNewCompanyName(e.target.value)}
                placeholder="Ex: Empresa Piloto X"
                className="md:col-span-2 rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-700 placeholder-gray-300 focus:outline-none focus:border-[#0A2342]"
              />
              <input
                type="text"
                value={newCompanySector}
                onChange={e => setNewCompanySector(e.target.value)}
                placeholder="Setor"
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-700 placeholder-gray-300 focus:outline-none focus:border-[#0A2342]"
              />
              <button
                type="button"
                onClick={createPilotCompany}
                disabled={creatingTenant}
                className="md:col-span-3 inline-flex items-center justify-center gap-2 rounded-xl bg-[#C9A959] px-5 py-3 font-bold text-[#0A2342] shadow-md hover:bg-[#b8943f] disabled:opacity-50"
              >
                {creatingTenant ? <RefreshCw size={18} className="animate-spin" /> : <Plus size={18} />}
                Criar empresa piloto
              </button>
            </div>

            {tenantError && (
              <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
                {tenantError}
              </div>
            )}

            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-widest text-gray-400">Empresas vinculadas</p>
              {tenants.length === 0 ? (
                <p className="rounded-lg border border-dashed border-gray-200 p-4 text-sm text-gray-400">
                  Nenhuma empresa encontrada. Crie uma empresa piloto acima.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {tenants.map(tenant => {
                    const active = company?.id === tenant.id;
                    return (
                      <button
                        key={tenant.id}
                        type="button"
                        onClick={() => setActiveCompany({ id: tenant.id, name: tenant.name })}
                        className={`rounded-xl border-2 p-4 text-left transition-all ${
                          active
                            ? 'border-[#0A2342] bg-[#0A2342] text-white'
                            : 'border-gray-100 bg-white text-gray-700 hover:border-[#C9A959]'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-bold">{tenant.name}</p>
                            <p className={`text-xs ${active ? 'text-white/60' : 'text-gray-400'}`}>
                              {tenant.sector || 'Setor nao informado'} · ID {tenant.id}
                            </p>
                          </div>
                          {active && <CheckCircle size={18} className="text-[#C9A959]" />}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Upload flow */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <button onClick={() => toggleSection('upload')}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors">
          <div className="flex items-center gap-2">
            <Upload size={18} className="text-[#0A2342]" />
            <h2 className="font-bold text-[#0A2342]">Fluxo de Upload do Piloto</h2>
            <span className="text-xs text-gray-400">ordem recomendada</span>
          </div>
          {expanded.upload ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </button>

        {expanded.upload && (
          <div className="border-t border-gray-100 p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              {UPLOAD_FLOW.map(item => (
                <Link
                  key={item.step}
                  href={item.href}
                  className="rounded-xl border border-gray-100 bg-white p-4 hover:border-[#C9A959] hover:bg-[#F0F4F8] transition-colors"
                >
                  <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-[#0A2342] text-sm font-extrabold text-[#C9A959]">
                    {item.step}
                  </div>
                  <p className="text-sm font-bold text-[#0A2342]">{item.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-gray-500">{item.detail}</p>
                </Link>
              ))}
            </div>
            <div className="mt-4 rounded-lg bg-blue-50 border border-blue-100 px-4 py-3 text-xs text-blue-800">
              Arquivos convertidos para teste: <strong>C:\Souza\juno\uploads_piloto_juno</strong>. Use 01 a 04 em Integrações ERP e 05 em Financeiro.
            </div>
          </div>
        )}
      </div>

      {/* Checklist */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <button onClick={() => toggleSection('checklist')}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors">
          <div className="flex items-center gap-2">
            <CheckSquare size={18} className="text-[#0A2342]" />
            <h2 className="font-bold text-[#0A2342]">Checklist do Piloto</h2>
            <span className="text-xs text-gray-400">({done}/{total} concluídos)</span>
          </div>
          {expanded.checklist ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </button>

        {expanded.checklist && (
          <ul className="divide-y divide-gray-50 border-t border-gray-100">
            {CHECKLIST.map((item, i) => (
              <li key={item.id} className={`px-6 py-4 transition-colors ${checks[item.id] ? 'bg-green-50' : 'hover:bg-gray-50'}`}>
                <div className="flex items-start gap-3">
                  <button onClick={() => toggle(item.id)} className="mt-0.5 shrink-0">
                    {checks[item.id]
                      ? <CheckSquare size={20} className="text-green-600" />
                      : <Square size={20} className="text-gray-300 hover:text-[#0A2342]" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-gray-400">{i + 1}.</span>
                      <p className={`font-semibold text-sm ${checks[item.id] ? 'text-green-800 line-through opacity-70' : 'text-gray-800'}`}>
                        {item.label}
                      </p>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5 ml-4">{item.desc}</p>
                    {!checks[item.id] && (
                      <input
                        type="text"
                        value={notes[item.id] || ''}
                        onChange={e => setNotes(p => ({ ...p, [item.id]: e.target.value }))}
                        placeholder={item.placeholder}
                        className="mt-2 ml-4 w-full max-w-lg text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-700 placeholder-gray-300 focus:outline-none focus:border-[#0A2342]"
                      />
                    )}
                    {checks[item.id] && notes[item.id] && (
                      <p className="text-xs text-green-700 mt-1 ml-4 italic">&quot;{notes[item.id]}&quot;</p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Data Request */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div
          role="button"
          tabIndex={0}
          onClick={() => toggleSection('data')}
          onKeyDown={e => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              toggleSection('data');
            }
          }}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Database size={18} className="text-[#0A2342]" />
            <h2 className="font-bold text-[#0A2342]">Data Request List</h2>
            <span className="text-xs text-gray-400">(enviar para o TI da empresa)</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={e => { e.stopPropagation(); copyDataRequest(); }}
              className="text-xs text-[#0A2342] font-semibold underline hover:text-[#C9A959] px-2">
              Copiar tudo
            </button>
            {expanded.data ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
          </div>
        </div>

        {expanded.data && (
          <div className="border-t border-gray-100 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100 bg-gray-50">
                <th className="text-left px-6 py-3">Dados</th>
                <th className="text-left px-6 py-3">Arquivo Sugerido</th>
                <th className="text-left px-6 py-3">Colunas Necessárias</th>
                <th className="text-center px-6 py-3">Formato</th>
                <th className="text-center px-6 py-3">Prioridade</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-50">
                {DATA_REQUEST.map(r => (
                  <tr key={r.type} className="hover:bg-gray-50">
                    <td className="px-6 py-3 font-semibold text-gray-800">{r.label}</td>
                    <td className="px-6 py-3 font-mono text-xs text-gray-500">{r.file}</td>
                    <td className="px-6 py-3 text-xs text-gray-600 max-w-xs">{r.columns}</td>
                    <td className="px-6 py-3 text-center text-xs text-gray-500">{r.format}</td>
                    <td className="px-6 py-3 text-center"><PriorityBadge p={r.priority} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-6 py-3 bg-blue-50 border-t border-blue-100">
              <p className="text-xs text-blue-700">
                💡 <strong>Para o TI:</strong> export simples do ERP em CSV ou Excel. Não é necessária nenhuma integração técnica. Os arquivos são carregados manualmente via interface web do JUNO.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Presentation outline */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
          <FileText size={18} className="text-[#0A2342]" />
          <h2 className="font-bold text-[#0A2342]">Estrutura da Apresentação</h2>
          <span className="text-xs text-gray-400">JUNO Industrial Diagnostic — Piloto {'{'}Empresa{'}'}</span>
        </div>
        <div className="divide-y divide-gray-50">
          {PRESENTATION_SLIDES.map(s => (
            <div key={s.n} className="px-6 py-5 hover:bg-gray-50 transition-colors">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-[#0A2342] text-[#C9A959] flex items-center justify-center font-extrabold text-sm shrink-0 mt-0.5">
                  {s.n}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-base">{s.icon}</span>
                    <p className="font-bold text-[#0A2342]">{s.title}</p>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">{s.content}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {s.talking_points.map((tp, i) => (
                      <span key={i} className="text-xs bg-[#F0F4F8] text-[#0A2342] px-2 py-1 rounded-lg border border-gray-200">
                        💬 {tp}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Next evolution roadmap */}
      <div className="bg-[#0A2342] rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[#C9A959] font-bold text-sm uppercase tracking-wider">Próxima Evolução Técnica</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {NEXT_EVOLUTION.map(e => (
            <div key={e.version} className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-[#C9A959] bg-[#C9A959]/10 px-2 py-0.5 rounded">{e.version}</span>
                <span className="text-white font-bold text-sm">{e.title}</span>
              </div>
              <p className="text-gray-400 text-xs leading-relaxed">{e.desc}</p>
            </div>
          ))}
        </div>
        <p className="text-gray-500 text-xs mt-4 text-center">
          Ordem: ERP Upload ✔ → Data Trust ✔ → Diagnóstico Confiável → Cliente Piloto → Integração Direta
        </p>
      </div>

    </div>
  );
}
