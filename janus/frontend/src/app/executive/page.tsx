'use client';

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import UnifiedExecutiveDashboard, {
  type UnifiedDashboardPayload,
} from '@/components/dashboard/UnifiedExecutiveDashboard';
import TemplateExecutiveReport, {
  type TemplateReportPayload,
} from '@/components/dashboard/TemplateExecutiveReport';
import ValuationScenarioReport, {
  type ValuationScenarioPayload,
} from '@/components/dashboard/ValuationScenarioReport';

export default function ExecutiveDashboardsPage() {
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();
  const [data, setData] = useState<UnifiedDashboardPayload | null>(null);
  const [valuation, setValuation] = useState<ValuationScenarioPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (companyLoading) return;
    if (!companyId) return;

    let mounted = true;
    async function loadDashboard() {
      setLoading(true);
      try {
        const [dashRes, valRes] = await Promise.all([
          api.get(`/kpis/${companyId}/unified`, { timeout: 120000 }),
          api.get<ValuationScenarioPayload>(`/financials/${companyId}/valuation/scenario`, {
            params: {
              anos: 5,
              crescimento_receita_pct: 10,
              crescimento_custos_fixos_pct: 5,
              taxa_desconto_pct: 10,
            },
          }),
        ]);
        if (mounted) {
          setData(dashRes.data);
          setValuation(valRes.data);
          setError(null);
        }
      } catch (err: unknown) {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          ?? 'Nao foi possivel carregar o dashboard unificado.';
        if (mounted) setError(String(detail));
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      mounted = false;
    };
  }, [companyId, companyLoading]);

  if (loading || companyLoading) {
    return (
      <div className="flex h-[70vh] items-center justify-center text-[#0A2342]">
        <Loader2 className="mr-2 animate-spin" size={22} />
        Carregando dashboard UNO a partir de Templates...
      </div>
    );
  }

  if (!companyId) {
    return (
      <div className="mx-auto max-w-4xl rounded-2xl border border-yellow-100 bg-white p-8">
        <h1 className="text-xl font-bold text-[#0A2342]">Nenhuma empresa vinculada</h1>
        <p className="mt-2 text-sm text-gray-600">Vincule um tenant ao usuario para carregar os KPIs executivos.</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl rounded-2xl border border-red-100 bg-white p-8">
        <h1 className="text-xl font-bold text-red-700">Dashboard indisponivel</h1>
        <p className="mt-2 text-sm text-gray-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="px-1">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-[#C9A959]">Relatório Executivo</p>
        <h1 className="mt-2 text-2xl font-extrabold text-[#0A2342] md:text-3xl">
          Demonstrações financeiras e painel UNO
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-gray-500">
          Tabelas alinhadas ao modelo em Templates, score industrial, síntese analítica e quadrantes operacionais.
        </p>
      </div>

      {data.relatorio_templates ? (
        <TemplateExecutiveReport
          report={data.relatorio_templates as TemplateReportPayload}
          companyName={company?.name}
        />
      ) : null}

      {valuation ? (
        <ValuationScenarioReport data={valuation} companyName={company?.name} />
      ) : null}

      <UnifiedExecutiveDashboard data={data} companyName={company?.name} />
    </div>
  );
}
