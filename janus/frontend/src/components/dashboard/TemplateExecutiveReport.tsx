'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { FileSpreadsheet } from 'lucide-react';

export interface TemplateReportLine {
  conta: string;
  valores: Array<number | null>;
  destaque?: boolean;
  unit?: string;
}

export interface TemplateReportSection {
  id: string;
  titulo: string;
  periodos: string[];
  linhas: TemplateReportLine[];
  nota?: string;
}

export interface TemplateReportPayload {
  titulo: string;
  subtitulo?: string;
  fonte?: string;
  unidade?: string;
  competencia?: string;
  patrimonial?: string;
  secoes: TemplateReportSection[];
}

interface Props {
  report: TemplateReportPayload;
  companyName?: string;
}

const NAVY = '#0A2342';

function fmtMil(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtCell(value: number | null | undefined, unit?: string, showMilSuffix = false): ReactNode {
  if (value == null || Number.isNaN(value)) return '—';
  if (unit === 'percent') return `${value.toFixed(2)}%`;
  if (unit === 'ratio') return `${value.toFixed(2)}x`;
  if (unit === 'score') return `${value.toFixed(1)}/100`;
  const formatted = `R$ ${fmtMil(value)}`;
  if (!showMilSuffix) return formatted;
  return (
    <>
      {formatted}
      <span className="ml-1 text-[10px] font-normal text-gray-400">mi</span>
    </>
  );
}

function sectionNote(section: TemplateReportSection, report: TemplateReportPayload) {
  if (section.nota) return section.nota;
  if (section.id === 'kpis') {
    return `Indicadores consolidados — competência ${report.competencia ?? '2025'} (Templates/KPIs_Templates.md).`;
  }
  if (section.id === 'balanco') {
    return `Valores em ${report.unidade ?? 'R$ milhões'}, posição ${report.patrimonial ?? '4T25'}.`;
  }
  if (section.id === 'dfc') {
    return `Valores em ${report.unidade ?? 'R$ milhões'}, fluxo ${report.competencia ?? '2025'}.`;
  }
  return `Valores em ${report.unidade ?? 'R$ milhões'}, conforme planilha modelo Templates.`;
}

export default function TemplateExecutiveReport({ report, companyName }: Props) {
  const [active, setActive] = useState(report.secoes[0]?.id ?? 'dre');
  const section = useMemo(
    () => report.secoes.find(sec => sec.id === active) ?? report.secoes[0],
    [active, report.secoes],
  );

  if (!section) return null;

  const isCurrency = section.id === 'dre' || section.id === 'balanco' || section.id === 'dfc';

  return (
    <section className="overflow-hidden rounded-3xl border border-[#C9A959]/30 bg-white shadow-xl">
      <div className="border-b border-[#0A2342]/10 bg-gradient-to-r from-[#0A2342] to-[#12345f] px-6 py-5 text-white">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.35em] text-[#C9A959]">JUNO · Industrial Diagnostic</p>
            <h2 className="mt-2 text-2xl font-extrabold">{report.titulo}</h2>
            <p className="mt-1 text-sm text-white/70">{report.subtitulo ?? 'Relatório Executivo'}</p>
          </div>
          <div className="text-right text-xs text-white/60">
            {companyName && <p className="font-semibold text-white">{companyName}</p>}
            <p>{report.unidade ?? 'R$ milhões'}</p>
            <p>DRE/DFC {report.competencia} · Balanço {report.patrimonial}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 bg-[#F8FAFC] px-6 py-3">
        <div className="flex flex-wrap gap-2">
          {report.secoes.map(sec => (
            <button
              key={sec.id}
              type="button"
              onClick={() => setActive(sec.id)}
              className={`rounded-full px-4 py-1.5 text-xs font-bold transition ${
                active === sec.id
                  ? 'bg-[#0A2342] text-[#C9A959]'
                  : 'border border-gray-200 bg-white text-gray-600 hover:border-[#C9A959]/50'
              }`}
            >
              {sec.id === 'dre' ? 'DRE' : sec.id === 'balanco' ? 'Balanço' : sec.id === 'dfc' ? 'DFC' : 'KPIs'}
            </button>
          ))}
        </div>
        <div className="inline-flex items-center gap-2 text-xs text-gray-500">
          <FileSpreadsheet size={14} className="text-[#C9A959]" />
          Fonte: {report.fonte}
        </div>
      </div>

      <div className="px-6 py-5">
        <h3 className="mb-4 text-sm font-bold uppercase tracking-widest text-[#0A2342]">{section.titulo}</h3>
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="min-w-full text-sm">
            <thead>
              <tr style={{ backgroundColor: NAVY }} className="text-left text-white">
                <th className="min-w-[260px] px-4 py-3 font-bold">Conta</th>
                {section.periodos.map(periodo => (
                  <th key={periodo} className="px-4 py-3 text-right font-bold whitespace-nowrap">
                    {periodo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {section.linhas.map((linha, rowIdx) => (
                <tr
                  key={linha.conta}
                  className={`border-t border-gray-100 ${
                    linha.destaque
                      ? 'bg-[#C9A959]/12 font-semibold text-[#0A2342]'
                      : rowIdx % 2 === 0
                        ? 'bg-white text-gray-700'
                        : 'bg-[#F8FAFC] text-gray-700'
                  }`}
                >
                  <td className="px-4 py-2.5">{linha.conta}</td>
                  {linha.valores.map((valor, idx) => (
                    <td key={`${linha.conta}-${idx}`} className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">
                      {fmtCell(valor, linha.unit, isCurrency)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-gray-400">{sectionNote(section, report)}</p>
      </div>
    </section>
  );
}
