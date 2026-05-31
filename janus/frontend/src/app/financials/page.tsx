'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, getApiErrorMessage } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import {
  Upload, CheckCircle, FileDown, Loader2, Clock,
  ChevronDown, TrendingUp, TrendingDown, BarChart3,
  DollarSign, Percent, AlertCircle,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────
interface UploadResult {
  status: 'success' | 'error';
  rows_imported: number;
  periods: string[];
  statement_types: string[];
  message?: string;
}

interface FinancialSummary {
  available: boolean;
  dre?: {
    periodo: string;
    receita_bruta: number;
    receita_liquida: number;
    lucro_bruto: number;
    ebitda: number;
    lucro_liquido: number;
    margem_bruta_pct: number;
    margem_liquida_pct: number;
    margem_ebitda_pct: number | null;
    todos_periodos: string[];
  };
  balanco?: {
    periodo: string;
    ativo_circulante: number;
    passivo_circulante: number;
    patrimonio_liquido: number;
    liquidez_corrente: number | null;
    endividamento_pct: number | null;
  };
  dfc?: {
    periodo: string;
    caixa_operacional: number;
    caixa_investimento: number;
    caixa_financiamento: number;
    variacao_caixa: number;
    caixa_final: number;
  };
}

interface HistoryEntry {
  id: number;
  file_name: string;
  periods: string;
  rows_imported: number;
  status: string;
  created_at: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmt(v: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(v);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

function PctBadge({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-gray-400 text-sm">—</span>;
  const ok = value >= 0;
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-bold ${ok ? 'text-green-600' : 'text-red-600'}`}>
      {ok ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
      {fmtPct(value)}
    </span>
  );
}

function KpiCard({ label, value, sub, accent }: { label: string; value: React.ReactNode; sub?: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${accent ? 'bg-[#0A2342] border-[#0A2342]' : 'bg-white border-gray-100'}`}>
      <p className={`text-xs uppercase tracking-widest font-semibold ${accent ? 'text-[#C9A959]' : 'text-gray-400'}`}>{label}</p>
      <div className={`text-2xl font-extrabold mt-1 ${accent ? 'text-white' : 'text-[#0A2342]'}`}>{value}</div>
      {sub && <p className={`text-xs mt-1 ${accent ? 'text-white/60' : 'text-gray-400'}`}>{sub}</p>}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function FinancialsPage() {
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();
  const [file, setFile]             = useState<File | null>(null);
  const [dragging, setDragging]     = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [result, setResult]         = useState<UploadResult | null>(null);
  const [summary, setSummary]       = useState<FinancialSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [history, setHistory]       = useState<HistoryEntry[]>([]);
  const [showHistory, setShowHistory]       = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadSummary = useCallback(async () => {
    if (!companyId) {
      setSummary(null);
      return;
    }
    setLoadingSummary(true);
    try {
      const res = await api.get(`/financials/${companyId}/summary`);
      setSummary(res.data);
    } catch {
      setSummary(null);
    } finally {
      setLoadingSummary(false);
    }
  }, [companyId]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadSummary();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadSummary]);

  const handleFile = (f: File | null) => {
    if (!f) return;
    if (!f.name.match(/\.(xlsx|xls|csv)$/i)) {
      alert('Use arquivos Excel (.xlsx, .xls) ou CSV (.csv)');
      return;
    }
    setFile(f);
    setResult(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0] ?? null);
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!companyId) {
      setResult({
        status: 'error',
        rows_imported: 0,
        periods: [],
        statement_types: [],
        message: 'Nenhuma empresa vinculada ao usuario.',
      });
      return;
    }
    setUploading(true);
    setResult(null);
    const form = new FormData();
    form.append('company_id', companyId.toString());
    form.append('file', file);
    try {
      const res = await api.post('/financials/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
      if (res.data.status === 'success') {
        await loadSummary();
      }
    } catch (err: unknown) {
      setResult({
        status: 'error',
        rows_imported: 0,
        periods: [],
        statement_types: [],
        message: getApiErrorMessage(err),
      });
    } finally {
      setUploading(false);
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
      const res = await api.get(`/financials/${companyId}/history`);
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
        <h1 className="text-2xl font-bold text-[#0A2342]">Demonstrações Financeiras</h1>
        <p className="text-gray-500 text-sm mt-1">
          Carregue DRE, Balanço Patrimonial e DFC para análise global e histórica.
          A IA incorpora automaticamente esses dados ao diagnóstico.
        </p>
      </div>

      {/* Steps */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { n: '1', title: 'Baixe o template', desc: 'Excel com abas DRE, Balanco e DFC. Preencha com seus dados reais.' },
          { n: '2', title: 'Preencha as abas', desc: 'Colunas: conta, periodo (AAAA-MM), valor. Negativo para saídas.' },
          { n: '3', title: 'Carregue no JUNO', desc: 'Indicadores e ratios calculados automaticamente após upload.' },
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

      {companyLoading && (
        <div className="bg-white border border-gray-100 rounded-xl p-6 text-sm text-gray-500">
          Carregando tenant ativo...
        </div>
      )}

      {!companyLoading && !companyId && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-xl p-6 text-sm text-yellow-800">
          Nenhuma empresa vinculada ao usuario. Vincule um tenant para carregar demonstracoes financeiras.
        </div>
      )}

      {/* Upload card */}
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

        {/* Template download */}
        <div className="flex items-center gap-3 bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
          <FileDown size={18} className="text-[#0A2342] shrink-0" />
          <span className="text-sm text-gray-700 flex-1">
            Template Excel com abas <strong>DRE</strong>, <strong>Balanco</strong> e <strong>DFC</strong>.
          </span>
          <a
            href="/templates/template_demonstracoes.xlsx"
            download
            className="text-xs font-bold text-[#0A2342] underline hover:text-[#C9A959]"
          >
            Baixar template
          </a>
        </div>

        {/* Drop zone */}
        <div>
          <label className="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">
            Arquivo (.xlsx ou .csv)
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
              accept=".xlsx,.xls,.csv"
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
                <p className="text-sm">
                  Arraste o arquivo aqui ou{' '}
                  <span className="text-[#0A2342] font-semibold">clique para selecionar</span>
                </p>
                <p className="text-xs">Suporte: .xlsx com abas DRE / Balanco / DFC</p>
              </div>
            )}
          </div>
        </div>

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={!file || uploading || !companyId}
          className="w-full flex items-center justify-center gap-2 bg-[#C9A959] text-[#0A2342] font-bold py-3 rounded-xl hover:bg-[#b8943f] transition-colors shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {uploading
            ? <><Loader2 className="animate-spin" size={20} /> Processando demonstrações...</>
            : <><Upload size={20} /> Carregar Demonstrações Financeiras</>
          }
        </button>
      </div>

      {/* Upload result */}
      {result && (
        <div className={`rounded-xl border-2 p-5 ${
          result.status === 'success' ? 'border-green-400 bg-green-50' : 'border-red-400 bg-red-50'
        }`}>
          {result.status === 'success' ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle size={20} className="text-green-600" />
                <span className="font-bold text-green-800">
                  {result.rows_imported} linhas importadas com sucesso
                </span>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {result.statement_types.map(t => (
                  <span key={t} className="px-2 py-0.5 rounded-full bg-green-200 text-green-800 text-xs font-bold">{t}</span>
                ))}
                {result.periods.map(p => (
                  <span key={p} className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium">{p}</span>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-2">
              <AlertCircle size={20} className="text-red-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-red-800">Erro ao importar</p>
                <p className="text-sm text-red-700 mt-1">{result.message}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Financial summary */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-[#0A2342]">
          Indicadores — {company?.name ?? 'Tenant ativo'}
        </h2>

        {loadingSummary ? (
          <div className="flex justify-center py-10">
            <Loader2 className="animate-spin text-gray-400" size={24} />
          </div>
        ) : !summary?.available ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-200 p-10 text-center">
            <BarChart3 size={36} className="text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm font-medium">Nenhuma demonstração carregada.</p>
            <p className="text-gray-400 text-xs mt-1">Faça upload do Excel para visualizar os indicadores.</p>
          </div>
        ) : (
          <div className="space-y-6">

            {/* DRE */}
            {summary.dre && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <DollarSign size={16} className="text-[#C9A959]" />
                  <h3 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">
                    DRE — Período {summary.dre.periodo}
                  </h3>
                  {summary.dre.todos_periodos.length > 1 && (
                    <span className="text-xs text-gray-400 ml-1">
                      ({summary.dre.todos_periodos.length} períodos disponíveis)
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                  <KpiCard label="Receita Líquida" value={fmt(summary.dre.receita_liquida)} accent />
                  <KpiCard label="Lucro Bruto" value={fmt(summary.dre.lucro_bruto)} sub={`Margem: ${fmtPct(summary.dre.margem_bruta_pct)}`} />
                  <KpiCard label="EBITDA" value={summary.dre.ebitda ? fmt(summary.dre.ebitda) : '—'} sub={summary.dre.margem_ebitda_pct != null ? `Margem: ${fmtPct(summary.dre.margem_ebitda_pct)}` : undefined} />
                  <KpiCard label="Lucro Líquido" value={fmt(summary.dre.lucro_liquido)} sub={`Margem: ${fmtPct(summary.dre.margem_liquida_pct)}`} />
                  <div className="rounded-xl border border-gray-100 bg-white p-4">
                    <p className="text-xs uppercase tracking-widest font-semibold text-gray-400">Margens</p>
                    <div className="mt-2 space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Bruta</span>
                        <PctBadge value={summary.dre.margem_bruta_pct} />
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-500">EBITDA</span>
                        <PctBadge value={summary.dre.margem_ebitda_pct} />
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Líquida</span>
                        <PctBadge value={summary.dre.margem_liquida_pct} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Balanço */}
            {summary.balanco && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Percent size={16} className="text-[#C9A959]" />
                  <h3 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">
                    Balanço — Período {summary.balanco.periodo}
                  </h3>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KpiCard label="Ativo Circulante" value={fmt(summary.balanco.ativo_circulante)} />
                  <KpiCard label="Passivo Circulante" value={fmt(summary.balanco.passivo_circulante)} />
                  <KpiCard
                    label="Liquidez Corrente"
                    value={summary.balanco.liquidez_corrente != null ? summary.balanco.liquidez_corrente.toFixed(2) : '—'}
                    sub={summary.balanco.liquidez_corrente != null
                      ? summary.balanco.liquidez_corrente >= 1.5 ? 'Saudável' : summary.balanco.liquidez_corrente >= 1 ? 'Atenção' : 'Crítico'
                      : undefined}
                    accent={!!summary.balanco.liquidez_corrente && summary.balanco.liquidez_corrente < 1}
                  />
                  <KpiCard
                    label="Endividamento"
                    value={summary.balanco.endividamento_pct != null ? `${summary.balanco.endividamento_pct.toFixed(1)}%` : '—'}
                    sub={summary.balanco.endividamento_pct != null
                      ? summary.balanco.endividamento_pct < 40 ? 'Baixo' : summary.balanco.endividamento_pct < 70 ? 'Moderado' : 'Alto'
                      : undefined}
                  />
                </div>
              </div>
            )}

            {/* DFC */}
            {summary.dfc && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp size={16} className="text-[#C9A959]" />
                  <h3 className="text-sm font-bold text-[#0A2342] uppercase tracking-wider">
                    Fluxo de Caixa — Período {summary.dfc.periodo}
                  </h3>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KpiCard label="Operacional" value={fmt(summary.dfc.caixa_operacional)} sub={summary.dfc.caixa_operacional >= 0 ? 'Geração' : 'Consumo'} />
                  <KpiCard label="Investimentos" value={fmt(summary.dfc.caixa_investimento)} />
                  <KpiCard label="Financiamentos" value={fmt(summary.dfc.caixa_financiamento)} />
                  <KpiCard label="Caixa Final" value={fmt(summary.dfc.caixa_final)} sub={`Variação: ${fmt(summary.dfc.variacao_caixa)}`} accent />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* History */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <button
          onClick={loadHistory}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors rounded-xl"
        >
          <div className="flex items-center gap-2 text-[#0A2342] font-semibold text-sm">
            <Clock size={16} />
            Histórico de Uploads — {company?.name ?? 'Tenant ativo'}
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
              <p className="text-sm text-gray-400 text-center py-6">Nenhum upload registrado.</p>
            ) : (
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 uppercase tracking-wider border-b border-gray-100">
                      <th className="text-left py-2 pr-4">Arquivo</th>
                      <th className="text-left py-2 pr-4">Períodos</th>
                      <th className="text-right py-2 pr-4">Linhas</th>
                      <th className="text-right py-2">Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4 font-medium max-w-[160px] truncate">{h.file_name}</td>
                        <td className="py-2 pr-4 text-gray-500 max-w-[200px] truncate">{h.periods}</td>
                        <td className="py-2 pr-4 text-right text-green-700 font-semibold">{h.rows_imported}</td>
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
