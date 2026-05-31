'use client';

import { useState, useRef } from 'react';
import { api, getApiErrorMessage } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import {
  Upload, CheckCircle, XCircle, AlertTriangle, Package, Users,
  ShoppingCart, Factory, BarChart3, DollarSign, Truck,
  Loader2, FileDown, Clock, ChevronDown,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────
interface ImportResult {
  company_id: number;
  data_type: string;
  rows_received: number;
  rows_imported: number;
  rows_rejected: number;
  errors: string[];
  status: 'success' | 'partial' | 'error';
}

interface HistoryEntry {
  id: number;
  data_type: string;
  file_name: string;
  rows_received: number;
  rows_imported: number;
  rows_rejected: number;
  status: string;
  created_at: string;
}

const PILOT_UPLOAD_FILES: Record<string, string> = {
  products: '02_products_juno.csv',
  customers: '01_customers_juno.csv',
  sales_orders: '03_sales_orders_juno.csv',
  production_orders: '04_production_orders_juno.csv',
};

const DATA_TYPES = [
  { id: 'products',           label: 'Produtos',             icon: Package,     template: 'products_template.csv', supported: true },
  { id: 'customers',          label: 'Clientes',             icon: Users,       template: 'customers_template.csv', supported: true },
  { id: 'sales_orders',       label: 'Pedidos de Venda',     icon: ShoppingCart,template: 'sales_orders_template.csv', supported: true },
  { id: 'production_orders',  label: 'Ordens de Produção',   icon: Factory,     template: 'production_orders_template.csv', supported: true },
  { id: 'inventory',          label: 'Estoque',              icon: BarChart3,   template: null, supported: false },
  { id: 'financials',         label: 'Financeiro',           icon: DollarSign,  template: null, supported: false },
  { id: 'suppliers',          label: 'Fornecedores',         icon: Truck,       template: null, supported: false },
];

// ── Helpers ────────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
    success: { color: 'bg-green-100 text-green-800 border-green-300', icon: <CheckCircle size={14} />, label: 'Sucesso' },
    partial: { color: 'bg-yellow-100 text-yellow-800 border-yellow-300', icon: <AlertTriangle size={14} />, label: 'Parcial' },
    error:   { color: 'bg-red-100 text-red-800 border-red-300',         icon: <XCircle size={14} />,      label: 'Erro' },
  };
  const s = map[status] ?? map.error;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${s.color}`}>
      {s.icon} {s.label}
    </span>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function IntegrationsPage() {
  const { company, companyId } = useActiveCompany();
  const [dataType, setDataType]   = useState('products');
  const [file, setFile]           = useState<File | null>(null);
  const [dragging, setDragging]   = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult]       = useState<ImportResult | null>(null);
  const [fileWarning, setFileWarning] = useState('');
  const [history, setHistory]     = useState<HistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const selectedType = DATA_TYPES.find(t => t.id === dataType)!;

  const handleFile = (f: File | null) => {
    if (!f) return;
    const ok = f.name.match(/\.(csv|xlsx|xls)$/i);
    if (!ok) { alert('Use arquivos CSV ou Excel (.csv, .xlsx, .xls)'); return; }
    setFile(f);
    setResult(null);
    const expectedPilotFile = PILOT_UPLOAD_FILES[dataType];
    setFileWarning(
      expectedPilotFile && f.name.includes('_piloto_larga_escala')
        ? `Arquivo bruto selecionado. Para o piloto, prefira uploads_piloto_juno/${expectedPilotFile}.`
        : ''
    );
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0] ?? null);
  };

  const handleImport = async () => {
    if (!file) return;
    if (!companyId) {
      setResult({
        company_id: 0,
        data_type: dataType,
        rows_received: 0,
        rows_imported: 0,
        rows_rejected: 0,
        errors: ['Nenhuma empresa vinculada ao usuario.'],
        status: 'error',
      });
      return;
    }
    setImporting(true);
    setResult(null);
    const form = new FormData();
    form.append('company_id', companyId.toString());
    form.append('data_type', dataType);
    form.append('file', file);
    try {
      const res = await api.post('/integrations/erp/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
    } catch (err: unknown) {
      setResult({
        company_id: companyId,
        data_type: dataType,
        rows_received: 0,
        rows_imported: 0,
        rows_rejected: 0,
        errors: [getApiErrorMessage(err)],
        status: 'error',
      });
    } finally {
      setImporting(false);
    }
  };

  const loadHistory = async () => {
    setShowHistory(true);
    setLoadingHistory(true);
    try {
      if (!companyId) {
        setHistory([]);
        return;
      }
      const res = await api.get(`/integrations/erp/history/${companyId}`);
      setHistory(res.data);
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-[#0A2342]">Integrações ERP</h1>
        <p className="text-gray-500 text-sm mt-1">
          Importe dados exportados do seu ERP (CSV ou Excel) e recalcule diagnósticos automaticamente.
        </p>
      </div>

      {/* How-to steps */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { n: '1', title: 'Baixe o template', desc: 'Exporte seus dados no formato JUNO ou use o template como guia.' },
          { n: '2', title: 'Preencha com dados reais', desc: 'Substitua os exemplos pelos dados exportados do seu ERP.' },
          { n: '3', title: 'Importe para o JUNO', desc: 'Score, insights e diagnóstico são recalculados automaticamente.' },
        ].map(s => (
          <div key={s.n} className="bg-[#F0F4F8] rounded-xl p-4 flex gap-3">
            <div className="w-8 h-8 rounded-full bg-[#0A2342] text-[#C9A959] flex items-center justify-center font-bold text-sm shrink-0">
              {s.n}
            </div>
            <div>
              <p className="font-semibold text-[#0A2342] text-sm">{s.title}</p>
              <p className="text-xs text-gray-500 mt-0.5">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Form card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-6">

        {/* Company selector */}
        <div>
          <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
            Empresa ativa
          </label>
          <div className="inline-flex px-5 py-2.5 rounded-lg border-2 bg-[#0A2342] text-white border-[#0A2342] font-bold text-sm">
            {company?.name ?? 'Tenant nao selecionado'}
          </div>
        </div>

        {/* Data type selector */}
        <div>
          <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
            Tipo de Dado
          </label>
          <div className="grid grid-cols-4 gap-2">
            {DATA_TYPES.map(t => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => {
                    if (!t.supported) return;
                    setDataType(t.id);
                    setFile(null);
                    setFileWarning('');
                    setResult(null);
                    setShowHistory(false);
                  }}
                  disabled={!t.supported}
                  className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 text-xs font-semibold transition-all ${
                    dataType === t.id
                      ? 'bg-[#C9A959] text-[#0A2342] border-[#C9A959]'
                      : t.supported
                      ? 'bg-white text-gray-600 border-gray-100 hover:border-[#C9A959]'
                      : 'bg-gray-50 text-gray-300 border-gray-100 cursor-not-allowed'
                  }`}
                >
                  <Icon size={18} />
                  {t.label}
                  {!t.supported && <span className="text-[10px] font-medium">em preparo</span>}
                </button>
              );
            })}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Financeiro deve ser carregado na aba Financeiro. Estoque e fornecedores serao liberados quando o importador dedicado estiver pronto.
          </p>
        </div>

        {/* Template download */}
        {selectedType.template && (
          <div className="flex items-center gap-3 bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
            <FileDown size={18} className="text-[#0A2342] shrink-0" />
            <span className="text-sm text-gray-700 flex-1">
              Template para <strong>{selectedType.label}</strong> disponível.
            </span>
            <a
              href={`/templates/${selectedType.template}`}
              download
              className="text-xs font-bold text-[#0A2342] underline hover:text-[#C9A959]"
            >
              Baixar CSV
            </a>
          </div>
        )}

        {/* File drop zone */}
        <div>
          <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
            Arquivo (CSV ou Excel)
          </label>
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
              dragging
                ? 'border-[#C9A959] bg-yellow-50'
                : file
                ? 'border-green-400 bg-green-50'
                : 'border-gray-200 hover:border-[#0A2342]'
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={e => handleFile(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <div className="flex flex-col items-center gap-1">
                <CheckCircle size={28} className="text-green-500" />
                <p className="font-semibold text-green-700 text-sm">{file.name}</p>
                <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB — clique para trocar</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-gray-400">
                <Upload size={28} />
                <p className="text-sm">Arraste o arquivo aqui ou <span className="text-[#0A2342] font-semibold">clique para selecionar</span></p>
                <p className="text-xs">Suporte: .csv · .xlsx · .xls</p>
              </div>
            )}
          </div>
        </div>

        {fileWarning && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            {fileWarning}
          </div>
        )}

        {/* Import button */}
        <button
          onClick={handleImport}
          disabled={!file || importing || !companyId}
          className="w-full flex items-center justify-center gap-2 bg-[#0A2342] text-white font-bold py-3 rounded-xl hover:bg-[#0d2d57] transition-colors shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {importing
            ? <><Loader2 className="animate-spin" size={20} /> Importando para o JUNO...</>
            : <><Upload size={20} /> Importar para JUNO</>
          }
        </button>
      </div>

      {/* Result card */}
      {result && (
        <div className={`rounded-xl border-2 p-6 space-y-4 ${
          result.status === 'success' ? 'border-green-400 bg-green-50' :
          result.status === 'partial' ? 'border-yellow-400 bg-yellow-50' :
          'border-red-400 bg-red-50'
        }`}>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-[#0A2342]">Resumo da Importação</h2>
            <StatusBadge status={result.status} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Linhas recebidas', value: result.rows_received, color: 'text-gray-700' },
              { label: 'Importadas',       value: result.rows_imported, color: 'text-green-700' },
              { label: 'Rejeitadas',       value: result.rows_rejected, color: result.rows_rejected > 0 ? 'text-red-700' : 'text-gray-500' },
            ].map(s => (
              <div key={s.label} className="bg-white rounded-lg p-4 text-center shadow-sm">
                <div className={`text-3xl font-extrabold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-gray-500 mt-1 uppercase tracking-wider">{s.label}</div>
              </div>
            ))}
          </div>

          {result.status === 'success' && (
            <p className="text-sm text-green-700 font-medium">
              Dados importados com sucesso. Dashboard e insights atualizados automaticamente.
            </p>
          )}

          {result.errors.length > 0 && (
            <div>
              <p className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2">Erros encontrados</p>
              <ul className="space-y-1 max-h-40 overflow-y-auto">
                {result.errors.map((e, i) => (
                  <li key={i} className="text-xs text-red-700 bg-white rounded px-3 py-1.5 border border-red-200">
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Import history */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <button
          onClick={loadHistory}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors rounded-xl"
        >
          <div className="flex items-center gap-2 text-[#0A2342] font-semibold text-sm">
            <Clock size={16} />
            Histórico de Importações — {company?.name ?? 'Tenant ativo'}
          </div>
          <ChevronDown size={16} className={`text-gray-400 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
        </button>

        {showHistory && (
          <div className="px-6 pb-5 border-t border-gray-100">
            {loadingHistory ? (
              <div className="flex justify-center py-6">
                <Loader2 className="animate-spin text-gray-400" size={20} />
              </div>
            ) : history.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">Nenhuma importação registrada.</p>
            ) : (
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 uppercase tracking-wider border-b border-gray-100">
                      <th className="text-left py-2 pr-4">Tipo</th>
                      <th className="text-left py-2 pr-4">Arquivo</th>
                      <th className="text-right py-2 pr-4">Recebidas</th>
                      <th className="text-right py-2 pr-4">Importadas</th>
                      <th className="text-right py-2 pr-4">Rejeitadas</th>
                      <th className="text-center py-2 pr-4">Status</th>
                      <th className="text-right py-2">Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4 font-medium capitalize">{h.data_type.replace('_', ' ')}</td>
                        <td className="py-2 pr-4 text-gray-500 max-w-[140px] truncate">{h.file_name}</td>
                        <td className="py-2 pr-4 text-right">{h.rows_received}</td>
                        <td className="py-2 pr-4 text-right text-green-700 font-semibold">{h.rows_imported}</td>
                        <td className="py-2 pr-4 text-right text-red-600">{h.rows_rejected}</td>
                        <td className="py-2 pr-4 text-center"><StatusBadge status={h.status} /></td>
                        <td className="py-2 text-right text-gray-400">
                          {new Date(h.created_at).toLocaleDateString('pt-BR')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
