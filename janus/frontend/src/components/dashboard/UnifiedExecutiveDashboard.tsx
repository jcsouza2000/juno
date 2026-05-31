'use client';

import { useMemo, useState, type ReactNode } from 'react';
import type { TemplateReportPayload } from '@/components/dashboard/TemplateExecutiveReport';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Activity,
  Brain,
  ChevronDown,
  ChevronUp,
  Factory,
  Landmark,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  Wifi,
} from 'lucide-react';

export interface UnifiedSeriesPoint {
  periodo: string;
  valor?: number;
  margem_bruta?: number | null;
  margem_liquida?: number | null;
  margem_ebitda?: number | null;
}

export interface UnifiedIndicator {
  valor: number | null;
  meta_wcm?: number | null;
  fonte?: string;
}

export interface UnifiedDashboardPayload {
  company_id?: number;
  meta?: {
    fonte?: string;
    unidade?: string;
    periodo_competencia?: string;
    source_mode?: string;
    generated_at?: string;
  };
  governanca?: {
    erp_conexao?: { label: string; status: string };
    auditoria_lgpd?: { label: string; status: string };
    busca_inteligente_placeholder?: string;
  };
  core?: {
    score_industrial: number;
    sintese_ia: string;
  };
  quadrantes?: {
    operacoes?: {
      titulo: string;
      series?: {
        oee?: UnifiedIndicator;
        ftt_fpy?: UnifiedIndicator;
        giro_estoque?: UnifiedIndicator;
      };
      tendencia_giro_estoque?: UnifiedSeriesPoint[];
    };
    financeiro?: {
      titulo: string;
      cards?: {
        faturamento?: number;
        margem_bruta_pct?: number | null;
        margem_liquida_pct?: number | null;
        ebitda_ajustado_pct?: number | null;
      };
      tendencia_faturamento?: UnifiedSeriesPoint[];
      tendencia_margens?: UnifiedSeriesPoint[];
    };
    risco_pessoas?: {
      titulo: string;
      indicadores?: {
        tfa?: UnifiedIndicator;
        turnover?: UnifiedIndicator;
        racio_administrativo_pct?: number | null;
      };
      contas_receber?: number | null;
    };
  };
  kpis_unificados?: Record<string, { resultado?: string; valor_numerico?: number | null }>;
  resumo_demonstracoes?: {
    unidade?: string;
    competencia?: string;
    patrimonial?: string;
    fonte?: string;
    dre?: {
      titulo?: string;
      receita_bruta?: number;
      receita_liquida?: number;
      cpv?: number;
      lucro_bruto?: number;
      despesas_admin?: number;
    };
    balanco?: {
      titulo?: string;
      caixa_equivalentes?: number;
      contas_receber?: number;
      estoques?: number;
      ativo_circulante?: number;
    };
    dfc?: {
      titulo?: string;
      lucro_antes_tributos?: number;
      depreciacao_amortizacao?: number;
    };
    kpis?: {
      titulo?: string;
      margem_bruta_pct?: number;
      margem_ebitda_pct?: number;
      margem_liquida_pct?: number;
      racio_admin_pct?: number;
      giro_estoque?: number;
      score_industrial?: number;
    };
  };
  busca_inteligente?: {
    ativo?: boolean;
    placeholder?: string;
    exemplos?: string[];
    faq?: Array<{ tags: string[]; resposta: string }>;
  };
  relatorio_templates?: TemplateReportPayload;
  pnl_table?: {
    unit: string;
    periods: string[];
    rows: Array<{
      id: string;
      label: string;
      total: number | null;
      pct: number | null;
      values: Array<number | null>;
      unit?: string;
    }>;
  } | null;
  source_status?: Array<{ source: string; loaded: boolean; records: number | null }>;
}

interface Props {
  data: UnifiedDashboardPayload;
  companyName?: string;
}

const GOLD = '#C9A959';
const NAVY = '#0A2342';
const CYAN = '#5EEAD4';
const VIOLET = '#A78BFA';

function fmtCurrency(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
}

function fmtPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
}

function fmtRatio(value: number | null | undefined, suffix = 'x') {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}${suffix}`;
}

function normalizeText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function answerUnoQuery(query: string, data: UnifiedDashboardPayload): string {
  const normalized = normalizeText(query);
  if (!normalized) {
    return 'Digite uma pergunta sobre DRE, balanco, fluxo de caixa ou KPIs do modelo Templates.';
  }

  const faq = data.busca_inteligente?.faq ?? [];
  let best: { score: number; resposta: string } | null = null;

  for (const item of faq) {
    let score = 0;
    for (const tag of item.tags) {
      const tagNorm = normalizeText(tag);
      if (normalized.includes(tagNorm)) score += tagNorm.length;
    }
    if (score > 0 && (!best || score > best.score)) {
      best = { score, resposta: item.resposta };
    }
  }

  if (best) return best.resposta;

  const resumo = data.resumo_demonstracoes;
  if (resumo?.kpis) {
    return (
      `Nao encontrei correspondencia exata. KPIs Templates ${resumo.competencia}: ` +
      `margem bruta ${resumo.kpis.margem_bruta_pct?.toFixed(2)}%, ` +
      `EBITDA ${resumo.kpis.margem_ebitda_pct?.toFixed(2)}%, ` +
      `liquida ${resumo.kpis.margem_liquida_pct?.toFixed(2)}%, ` +
      `giro ${resumo.kpis.giro_estoque?.toFixed(2)}x.`
    );
  }

  return data.core?.sintese_ia ?? 'Consulta indisponivel. Verifique se Templates esta carregado.';
}

function StatusPill({ label, status }: { label: string; status: string }) {
  const ok = ['ativa', 'ok', 'active'].includes(status.toLowerCase());
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold tracking-wide ${
        ok
          ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.15)]'
          : 'border-amber-400/30 bg-amber-500/10 text-amber-200'
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
      {label}: {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function ScoreRing({ score }: { score: number }) {
  const radius = 88;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (circumference * Math.min(score, 100)) / 100;
  const label = score >= 85 ? 'Excelente' : score >= 70 ? 'Monitoramento' : score >= 50 ? 'Atencao' : 'Critico';

  return (
    <div className="relative flex flex-col items-center">
      <div className="relative h-[220px] w-[220px]">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 200 200">
          <defs>
            <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={GOLD} />
              <stop offset="55%" stopColor={CYAN} />
              <stop offset="100%" stopColor={VIOLET} />
            </linearGradient>
          </defs>
          <circle cx="100" cy="100" r={radius} stroke="rgba(255,255,255,0.08)" strokeWidth="14" fill="none" />
          <circle
            cx="100"
            cy="100"
            r={radius}
            stroke="url(#scoreGradient)"
            strokeWidth="14"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-[11px] font-bold uppercase tracking-[0.25em] text-white/50">Score UNO</span>
          <span className="mt-1 text-5xl font-black text-white tabular-nums">{score.toFixed(1)}</span>
          <span className="mt-2 rounded-full bg-white/10 px-3 py-0.5 text-[10px] font-bold uppercase text-[#C9A959]">
            {label}
          </span>
        </div>
      </div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  hint,
  accent = '#fff',
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-sm">
      <p className="text-[11px] font-bold uppercase tracking-widest text-white/45">{label}</p>
      <p className="mt-2 text-2xl font-extrabold tabular-nums" style={{ color: accent }}>
        {value}
      </p>
      {hint && <p className="mt-1 text-[11px] text-white/40">{hint}</p>}
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-white/[0.02] p-5 backdrop-blur-md">
      <div className="mb-4">
        <h3 className="text-sm font-bold uppercase tracking-widest text-[#C9A959]">{title}</h3>
        {subtitle && <p className="mt-1 text-xs text-white/45">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function PendingBadge() {
  return (
    <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-white/50">
      Integracao pendente
    </span>
  );
}

const tooltipStyle = {
  contentStyle: {
    background: '#0f2744',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: '12px',
    color: '#fff',
    fontSize: '12px',
  },
};

export default function UnifiedExecutiveDashboard({ data, companyName }: Props) {
  const [showPnl, setShowPnl] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchAnswer, setSearchAnswer] = useState<string | null>(null);
  const [activeResumo, setActiveResumo] = useState<'dre' | 'balanco' | 'dfc' | 'kpis'>('dre');
  const score = data.core?.score_industrial ?? 0;
  const ops = data.quadrantes?.operacoes;
  const fin = data.quadrantes?.financeiro;
  const risk = data.quadrantes?.risco_pessoas;
  const gov = data.governanca;

  const marginBars = useMemo(
    () => [
      { name: 'Bruta', value: fin?.cards?.margem_bruta_pct ?? 0, fill: GOLD },
      { name: 'Liquida', value: fin?.cards?.margem_liquida_pct ?? 0, fill: CYAN },
      { name: 'EBITDA', value: fin?.cards?.ebitda_ajustado_pct ?? 0, fill: VIOLET },
    ],
    [fin?.cards],
  );

  const marginTrend = fin?.tendencia_margens ?? [];
  const revenueTrend = fin?.tendencia_faturamento ?? [];
  const giroTrend = ops?.tendencia_giro_estoque ?? [];
  const resumo = data.resumo_demonstracoes;
  const busca = data.busca_inteligente;
  const searchPlaceholder =
    busca?.placeholder ?? gov?.busca_inteligente_placeholder ?? 'Pergunte ao UNO sobre a operacao...';

  function handleSearchSubmit(event?: React.FormEvent) {
    event?.preventDefault();
    setSearchAnswer(answerUnoQuery(searchQuery, data));
  }

  const resumoLabels = {
    dre: 'DRE',
    balanco: 'Balanco',
    dfc: 'Fluxo de Caixa',
    kpis: 'KPIs',
  } as const;

  return (
    <div className="relative min-h-full overflow-hidden rounded-3xl border border-white/10 bg-[#071526] text-white shadow-2xl">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(201,169,89,0.18),transparent_35%),radial-gradient(circle_at_80%_20%,rgba(94,234,212,0.12),transparent_30%),radial-gradient(circle_at_50%_100%,rgba(167,139,250,0.1),transparent_40%)]" />

      <div className="relative border-b border-white/10 bg-[#0A2342]/80 px-6 py-4 backdrop-blur-xl">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill label={gov?.erp_conexao?.label ?? 'Conexao ERP'} status={gov?.erp_conexao?.status ?? 'pendente'} />
            <StatusPill label={gov?.auditoria_lgpd?.label ?? 'Auditoria LGPD'} status={gov?.auditoria_lgpd?.status ?? 'revisar'} />
            <span className="hidden items-center gap-2 text-xs text-white/40 md:inline-flex">
              <Wifi size={14} />
              {companyName ?? 'Tenant ativo'}
            </span>
          </div>

          <form className="relative mx-auto w-full max-w-2xl xl:mx-0 xl:flex-1" onSubmit={handleSearchSubmit}>
            <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#C9A959]" />
            <input
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              placeholder={searchPlaceholder}
              className="w-full rounded-full border border-[#C9A959]/40 bg-white/10 py-3 pl-11 pr-24 text-sm text-white placeholder:text-white/45 outline-none ring-[#C9A959]/30 transition focus:border-[#C9A959] focus:bg-white/[0.12] focus:ring-2"
            />
            <button
              type="submit"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-[#C9A959] px-4 py-1.5 text-xs font-bold text-[#0A2342] hover:bg-[#d9bc6a]"
            >
              Perguntar
            </button>
          </form>

          <div className="text-right text-xs text-white/45">
            <p className="font-bold uppercase tracking-widest text-[#C9A959]">Dashboard UNO</p>
            <p>Competencia {data.meta?.periodo_competencia ?? '—'}</p>
          </div>
        </div>

        {(searchAnswer || (busca?.exemplos?.length ?? 0) > 0) && (
          <div className="border-t border-white/10 px-6 py-4">
            {searchAnswer && (
              <div className="mb-3 rounded-2xl border border-cyan-400/20 bg-cyan-500/10 px-4 py-3 text-sm leading-relaxed text-cyan-50">
                <span className="font-bold text-[#C9A959]">UNO: </span>
                {searchAnswer}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {(busca?.exemplos ?? []).map(exemplo => (
                <button
                  key={exemplo}
                  type="button"
                  onClick={() => {
                    setSearchQuery(exemplo);
                    setSearchAnswer(answerUnoQuery(exemplo, data));
                  }}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 hover:border-[#C9A959]/40 hover:text-white"
                >
                  {exemplo}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {resumo && (
        <div className="relative border-b border-white/10 px-6 py-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-[#C9A959]">Resumo Templates</p>
              <p className="mt-1 text-sm text-white/50">
                {resumo.fonte} · {resumo.unidade} · DRE/DFC {resumo.competencia} · Balanco {resumo.patrimonial}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(resumoLabels) as Array<keyof typeof resumoLabels>).map(key => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveResumo(key)}
                  className={`rounded-full px-4 py-1.5 text-xs font-bold transition ${
                    activeResumo === key
                      ? 'bg-[#C9A959] text-[#0A2342]'
                      : 'border border-white/10 bg-white/5 text-white/70 hover:border-[#C9A959]/40'
                  }`}
                >
                  {resumoLabels[key]}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {activeResumo === 'dre' && resumo.dre && (
              <>
                <MetricTile label="Receita Bruta" value={`R$ ${fmtCurrency(resumo.dre.receita_bruta)} mi`} />
                <MetricTile label="Receita Liquida" value={`R$ ${fmtCurrency(resumo.dre.receita_liquida)} mi`} accent={CYAN} />
                <MetricTile label="CPV" value={`R$ ${fmtCurrency(resumo.dre.cpv)} mi`} accent={VIOLET} />
                <MetricTile label="Lucro Bruto" value={`R$ ${fmtCurrency(resumo.dre.lucro_bruto)} mi`} />
              </>
            )}
            {activeResumo === 'balanco' && resumo.balanco && (
              <>
                <MetricTile label="Caixa e Equivalentes" value={`R$ ${fmtCurrency(resumo.balanco.caixa_equivalentes)} mi`} />
                <MetricTile label="Contas a Receber" value={`R$ ${fmtCurrency(resumo.balanco.contas_receber)} mi`} accent={CYAN} />
                <MetricTile label="Estoques" value={`R$ ${fmtCurrency(resumo.balanco.estoques)} mi`} accent={VIOLET} />
                <MetricTile label="Ativo Circulante" value={`R$ ${fmtCurrency(resumo.balanco.ativo_circulante)} mi`} />
              </>
            )}
            {activeResumo === 'dfc' && resumo.dfc && (
              <>
                <MetricTile label="Lucro Antes dos Tributos" value={`R$ ${fmtCurrency(resumo.dfc.lucro_antes_tributos)} mi`} />
                <MetricTile
                  label="Depreciacao e Amortizacao"
                  value={`R$ ${fmtCurrency(resumo.dfc.depreciacao_amortizacao)} mi`}
                  accent={CYAN}
                />
              </>
            )}
            {activeResumo === 'kpis' && resumo.kpis && (
              <>
                <MetricTile label="Margem Bruta" value={fmtPct(resumo.kpis.margem_bruta_pct)} />
                <MetricTile label="Margem EBITDA" value={fmtPct(resumo.kpis.margem_ebitda_pct)} accent={CYAN} />
                <MetricTile label="Margem Liquida" value={fmtPct(resumo.kpis.margem_liquida_pct)} accent={VIOLET} />
                <MetricTile label="Giro de Estoque" value={fmtRatio(resumo.kpis.giro_estoque)} />
              </>
            )}
          </div>
        </div>
      )}

      <div className="relative grid gap-6 p-6 xl:grid-cols-[320px_1fr]">
        <div className="flex flex-col items-center justify-center rounded-3xl border border-white/10 bg-white/[0.03] p-6 text-center backdrop-blur-sm">
          <ScoreRing score={score} />
          <p className="mt-6 max-w-xs text-xs uppercase tracking-[0.2em] text-white/40">Score Industrial / Operacional</p>
        </div>

        <div className="flex flex-col justify-center rounded-3xl border border-[#C9A959]/20 bg-gradient-to-br from-[#C9A959]/10 via-transparent to-cyan-500/5 p-6 backdrop-blur-sm">
          <div className="mb-3 flex items-center gap-2 text-[#C9A959]">
            <Brain size={18} />
            <span className="text-xs font-bold uppercase tracking-widest">Sintese analitica UNO</span>
            <Sparkles size={14} className="text-cyan-300" />
          </div>
          <p className="text-lg leading-relaxed text-white/90 md:text-xl">{data.core?.sintese_ia}</p>
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            {Object.entries(data.kpis_unificados ?? {}).slice(0, 4).map(([name, kpi]) => (
              <div key={name} className="rounded-xl border border-white/10 bg-black/20 px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-white/40">{name}</p>
                <p className="mt-1 text-sm font-bold text-white">{kpi.resultado ?? '—'}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="relative grid gap-4 px-6 pb-6 xl:grid-cols-3">
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Factory size={16} className="text-[#C9A959]" />
            <h2 className="text-sm font-bold uppercase tracking-widest">{ops?.titulo ?? 'Operacoes'}</h2>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <MetricTile
              label="OEE"
              value={ops?.series?.oee?.valor != null ? fmtPct(ops.series.oee.valor) : '—'}
              hint={ops?.series?.oee?.valor == null ? 'Producao' : `Meta ${ops?.series?.oee?.meta_wcm}%`}
            />
            <MetricTile
              label="FTT / FPY"
              value={ops?.series?.ftt_fpy?.valor != null ? fmtPct(ops.series.ftt_fpy.valor) : '—'}
              hint={ops?.series?.ftt_fpy?.valor == null ? 'Qualidade' : `Meta ${ops?.series?.ftt_fpy?.meta_wcm}%`}
              accent={CYAN}
            />
            <MetricTile
              label="Giro estoque"
              value={fmtRatio(ops?.series?.giro_estoque?.valor)}
              hint="CPV / estoque"
              accent={VIOLET}
            />
          </div>

          <ChartCard title="Tendencia de giro" subtitle="Serie trimestral / mensal">
            {giroTrend.length > 0 ? (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={giroTrend}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="periodo" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} width={32} />
                    <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(2)}x`, 'Giro']} />
                    <Line type="monotone" dataKey="valor" stroke={CYAN} strokeWidth={2.5} dot={{ r: 4, fill: CYAN }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex h-48 items-center justify-center text-sm text-white/40">Sem serie historica</div>
            )}
          </ChartCard>
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Landmark size={16} className="text-[#C9A959]" />
            <h2 className="text-sm font-bold uppercase tracking-widest">{fin?.titulo ?? 'Financeiro'}</h2>
          </div>

          <MetricTile
            label="Faturamento (Receita Liquida)"
            value={`R$ ${fmtCurrency(fin?.cards?.faturamento)}`}
            hint={data.meta?.unidade ? `Unidade: ${data.meta.unidade}` : undefined}
          />

          <ChartCard title="Margens consolidadas" subtitle="Indicadores percentuais">
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={marginBars} barSize={36}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" width={36} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)}%`, 'Margem']} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                    {marginBars.map(entry => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>

          <ChartCard title="Faturamento em tendencia" subtitle="Evolucao por periodo">
            {revenueTrend.length > 0 ? (
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={revenueTrend}>
                    <defs>
                      <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={GOLD} stopOpacity={0.45} />
                        <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="periodo" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} width={48} />
                    <Tooltip {...tooltipStyle} formatter={(v: number) => [`R$ ${fmtCurrency(v)}`, 'Receita']} />
                    <Area type="monotone" dataKey="valor" stroke={GOLD} fill="url(#revenueFill)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex h-40 items-center justify-center text-sm text-white/40">Sem serie historica</div>
            )}
          </ChartCard>
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-[#C9A959]" />
            <h2 className="text-sm font-bold uppercase tracking-widest">{risk?.titulo ?? 'Risco e Pessoas'}</h2>
          </div>

          <div className="grid gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-bold uppercase tracking-widest text-white/45">TFA — Seguranca</p>
                {risk?.indicadores?.tfa?.valor == null && <PendingBadge />}
              </div>
              <p className="mt-2 text-2xl font-extrabold">{risk?.indicadores?.tfa?.valor ?? '—'}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-bold uppercase tracking-widest text-white/45">Turnover</p>
                {risk?.indicadores?.turnover?.valor == null && <PendingBadge />}
              </div>
              <p className="mt-2 text-2xl font-extrabold">
                {risk?.indicadores?.turnover?.valor != null ? fmtPct(risk.indicadores.turnover.valor) : '—'}
              </p>
            </div>
            <MetricTile
              label="Racio administrativo"
              value={fmtPct(risk?.indicadores?.racio_administrativo_pct)}
              hint="Despesas admin / receita bruta"
            />
            {risk?.contas_receber != null && (
              <MetricTile
                label="Contas a receber"
                value={`R$ ${fmtCurrency(risk.contas_receber)}`}
                hint="Posicao patrimonial"
                accent={CYAN}
              />
            )}
          </div>

          {marginTrend.length > 0 && (
            <ChartCard title="Margens em tendencia" subtitle="Bruta, liquida e EBITDA">
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={marginTrend}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="periodo" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" width={36} />
                    <Tooltip {...tooltipStyle} />
                    <Line type="monotone" dataKey="margem_bruta" name="Bruta" stroke={GOLD} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="margem_liquida" name="Liquida" stroke={CYAN} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="margem_ebitda" name="EBITDA" stroke={VIOLET} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          )}
        </section>
      </div>

      {(data.pnl_table?.periods?.length || data.source_status?.length) && (
        <div className="relative border-t border-white/10 px-6 py-4">
          <button
            type="button"
            onClick={() => setShowPnl(v => !v)}
            className="flex w-full items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-left text-sm font-semibold text-white/80 hover:bg-white/[0.06]"
          >
            <span className="flex items-center gap-2">
              <Activity size={16} className="text-[#C9A959]" />
              Detalhes analiticos e fontes
            </span>
            {showPnl ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {showPnl && (
            <div className="mt-4 space-y-4">
              {data.source_status && data.source_status.length > 0 && (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  {data.source_status.map(source => (
                    <div key={source.source} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                      <ShieldCheck size={18} className={source.loaded ? 'text-emerald-400' : 'text-amber-400'} />
                      <div>
                        <p className="text-sm font-semibold">{source.source}</p>
                        <p className="text-xs text-white/45">
                          {source.loaded ? 'Carregado' : 'Pendente'}
                          {source.records != null ? ` · ${source.records}` : ''}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {data.pnl_table?.periods?.length ? (
                <div className="overflow-x-auto rounded-2xl border border-white/10">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead>
                      <tr className="bg-white/[0.04] text-left text-white/70">
                        <th className="px-4 py-3 font-bold">Indicador</th>
                        <th className="px-4 py-3 text-right font-bold">Total</th>
                        <th className="px-4 py-3 text-right font-bold">%</th>
                        {data.pnl_table.periods.map(period => (
                          <th key={period} className="px-4 py-3 text-right font-bold">
                            {period}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.pnl_table.rows.map(row => (
                        <tr key={row.id} className="border-t border-white/10 text-white/80">
                          <td className="px-4 py-2">{row.label}</td>
                          <td className="px-4 py-2 text-right tabular-nums">{fmtCurrency(row.total)}</td>
                          <td className="px-4 py-2 text-right tabular-nums">{row.pct != null ? `${row.pct.toFixed(1)}%` : '—'}</td>
                          {row.values.map((value, idx) => (
                            <td key={`${row.id}-${idx}`} className="px-4 py-2 text-right tabular-nums">
                              {fmtCurrency(value)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
