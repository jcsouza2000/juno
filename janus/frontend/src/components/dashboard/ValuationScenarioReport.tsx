'use client';

import { useMemo, useState } from 'react';
import { TrendingUp } from 'lucide-react';

export interface ValuationDreRow {
  ano: number;
  tipo: 'realizado' | 'projecao';
  receita_liquida: number;
  custos_operacionais: number;
  ebitda: number;
  lucro_liquido: number;
}

export interface ValuationDfcRow {
  ano: number;
  tipo: 'realizado' | 'projecao';
  ebitda: number;
  depreciacao: number;
  lucro_antes_ir: number;
  imposto: number;
  lucro_liquido: number;
  capex: number;
  fcf: number;
  fator_desconto: number;
  pv_fcf: number;
}

export interface ValuationScenarioPayload {
  kind: 'valuation_scenario';
  company_id: number;
  cenario: string;
  unidade: string;
  ano_base: number;
  periodo_base?: string;
  premissas: {
    anos: number;
    crescimento_receita_pct: number;
    crescimento_custos_fixos_pct: number;
    taxa_desconto_pct: number;
    anos_descontados?: number;
  };
  base: {
    receita_liquida: number;
    ebitda: number;
    lucro_liquido: number;
    depreciacao: number;
    fcf: number;
  };
  dre_projetada: ValuationDreRow[];
  dfc_projetado: ValuationDfcRow[];
  valuation: {
    enterprise_value: number;
    pv_fcf_total: number;
    taxa_desconto_pct: number;
    metodo: string;
  };
  diagnostico?: string;
}

interface Props {
  data: ValuationScenarioPayload;
  companyName?: string;
  compact?: boolean;
}

const NAVY = '#0A2342';
const GOLD = '#C9A959';

function fmt(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function money(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—';
  return `R$ ${fmt(value)}`;
}

export default function ValuationScenarioReport({ data, companyName, compact = false }: Props) {
  const [active, setActive] = useState<'dre' | 'dfc' | 'resumo'>('resumo');
  const anos = useMemo(() => data.dre_projetada.map(r => String(r.ano)), [data.dre_projetada]);

  const dreLines = [
    { label: 'Receita Líquida', key: 'receita_liquida' as const, destaque: false },
    { label: 'Custos Operacionais', key: 'custos_operacionais' as const, destaque: false },
    { label: 'EBITDA', key: 'ebitda' as const, destaque: true },
    { label: 'Lucro Líquido', key: 'lucro_liquido' as const, destaque: true },
  ];

  const dfcLines = [
    { label: 'EBITDA', key: 'ebitda' as const },
    { label: 'Depreciação / Amortização', key: 'depreciacao' as const },
    { label: 'Lucro antes IR/CS', key: 'lucro_antes_ir' as const },
    { label: 'Imposto de Renda', key: 'imposto' as const },
    { label: 'Lucro Líquido', key: 'lucro_liquido' as const },
    { label: 'Capex (manutenção)', key: 'capex' as const },
    { label: 'Fluxo de Caixa Livre (FCF)', key: 'fcf' as const, destaque: true },
    { label: 'PV do FCF', key: 'pv_fcf' as const, destaque: true },
  ];

  return (
    <section className={`overflow-hidden rounded-3xl border border-[#C9A959]/30 bg-white shadow-xl ${compact ? 'my-3' : ''}`}>
      <div className="border-b border-[#0A2342]/10 bg-gradient-to-r from-[#0A2342] to-[#12345f] px-5 py-4 text-white">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.35em] text-[#C9A959]">
              Valuation · Cenário {data.cenario}
            </p>
            <h2 className="mt-1 text-xl font-extrabold">DRE/DFC Projetados e Enterprise Value</h2>
            {companyName && <p className="mt-1 text-sm text-white/70">{companyName}</p>}
          </div>
          <div className="rounded-2xl border border-[#C9A959]/40 bg-[#0A2342]/40 px-4 py-3 text-right">
            <p className="text-[10px] uppercase tracking-widest text-white/60">Enterprise Value</p>
            <p className="text-2xl font-extrabold text-[#C9A959]">
              {money(data.valuation.enterprise_value)}
              <span className="ml-1 text-xs font-normal text-white/60">mi</span>
            </p>
            <p className="mt-1 text-[10px] text-white/50">
              WACC {data.premissas.taxa_desconto_pct.toFixed(0)}% · PV FCF projetado
            </p>
          </div>
        </div>
      </div>

      {!compact && (
        <div className="grid gap-3 border-b border-gray-100 bg-[#F8FAFC] px-5 py-4 sm:grid-cols-4">
          {[
            ['Receita', `+${data.premissas.crescimento_receita_pct}% a.a.`],
            ['Custos operacionais', `+${data.premissas.crescimento_custos_fixos_pct}% a.a.`],
            ['Horizonte', `${data.premissas.anos} anos`],
            ['Ano base', String(data.ano_base)],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-gray-100 bg-white px-3 py-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{k}</p>
              <p className="text-sm font-bold text-[#0A2342]">{v}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 border-b border-gray-100 px-5 py-3">
        {(['resumo', 'dre', 'dfc'] as const).map(tab => (
          <button
            key={tab}
            type="button"
            onClick={() => setActive(tab)}
            className={`rounded-full px-4 py-1.5 text-xs font-bold transition ${
              active === tab
                ? 'bg-[#0A2342] text-[#C9A959]'
                : 'border border-gray-200 bg-white text-gray-600 hover:border-[#C9A959]/50'
            }`}
          >
            {tab === 'resumo' ? 'Resumo' : tab.toUpperCase()}
          </button>
        ))}
        <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-gray-400">
          <TrendingUp size={12} className="text-[#C9A959]" />
          {data.unidade} · motor auditável JUNO
        </span>
      </div>

      <div className="px-5 py-4">
        {active === 'resumo' && (
          <div className="space-y-3 text-sm text-gray-700">
            {data.diagnostico && (
              <p className="rounded-xl border border-[#C9A959]/20 bg-[#FBF8F0] px-4 py-3 leading-relaxed">
                {data.diagnostico}
              </p>
            )}
            <p className="text-xs text-gray-500">{data.valuation.metodo}</p>
            <div className="overflow-x-auto rounded-xl border border-gray-100">
              <table className="min-w-full text-sm">
                <thead>
                  <tr style={{ backgroundColor: NAVY }} className="text-left text-white">
                    <th className="px-4 py-2.5 font-bold">Ano</th>
                    <th className="px-4 py-2.5 text-right font-bold">FCF</th>
                    <th className="px-4 py-2.5 text-right font-bold">PV FCF</th>
                    <th className="px-4 py-2.5 text-right font-bold">Tipo</th>
                  </tr>
                </thead>
                <tbody>
                  {data.dfc_projetado.map((row, idx) => (
                    <tr
                      key={row.ano}
                      className={`border-t border-gray-100 ${idx % 2 === 0 ? 'bg-white' : 'bg-[#F8FAFC]'}`}
                    >
                      <td className="px-4 py-2 font-semibold text-[#0A2342]">{row.ano}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(row.fcf)}</td>
                      <td className="px-4 py-2 text-right tabular-nums font-semibold text-[#0A2342]">
                        {row.tipo === 'realizado' ? '—' : money(row.pv_fcf)}
                      </td>
                      <td className="px-4 py-2 text-right text-xs uppercase tracking-wide text-gray-500">
                        {row.tipo}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {active === 'dre' && (
          <TableBlock
            title="DRE Projetada"
            anos={anos}
            rows={data.dre_projetada}
            lines={dreLines}
            tipos={data.dre_projetada.map(r => r.tipo)}
          />
        )}

        {active === 'dfc' && (
          <TableBlock
            title="Demonstração do Fluxo de Caixa Projetado"
            anos={anos}
            rows={data.dfc_projetado}
            lines={dfcLines}
            tipos={data.dfc_projetado.map(r => r.tipo)}
          />
        )}
      </div>
    </section>
  );
}

function TableBlock<T extends Record<string, unknown>>({
  title,
  anos,
  rows,
  lines,
  tipos,
}: {
  title: string;
  anos: string[];
  rows: T[];
  lines: { label: string; key: keyof T; destaque?: boolean }[];
  tipos: string[];
}) {
  return (
    <>
      <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-[#0A2342]">{title}</h3>
      <div className="overflow-x-auto rounded-xl border border-gray-100">
        <table className="min-w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: NAVY }} className="text-left text-white">
              <th className="min-w-[220px] px-4 py-2.5 font-bold">Conta</th>
              {anos.map((ano, i) => (
                <th key={ano} className="px-4 py-2.5 text-right font-bold whitespace-nowrap">
                  {ano}
                  {tipos[i] === 'realizado' && (
                    <span className="ml-1 text-[9px] font-normal text-[#C9A959]">base</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lines.map((line, rowIdx) => (
              <tr
                key={String(line.key)}
                className={`border-t border-gray-100 ${
                  line.destaque
                    ? 'bg-[#C9A959]/12 font-semibold text-[#0A2342]'
                    : rowIdx % 2 === 0
                      ? 'bg-white text-gray-700'
                      : 'bg-[#F8FAFC] text-gray-700'
                }`}
              >
                <td className="px-4 py-2.5">{line.label}</td>
                {rows.map(row => (
                  <td key={`${String(line.key)}-${String(row.ano)}`} className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">
                    {money(row[line.key] as number)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
