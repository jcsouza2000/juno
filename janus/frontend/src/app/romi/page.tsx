'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useActiveCompany } from '@/lib/tenant';
import { useI18n } from '@/lib/i18n';
import MetricCard from '@/components/dashboard/MetricCard';
import ScoreCard from '@/components/dashboard/ScoreCard';
import MarginTable from '@/components/dashboard/MarginTable';
import DelayTable from '@/components/dashboard/DelayTable';
import InsightSection from '@/components/dashboard/InsightSection';
import DiagnosticReport from '@/components/dashboard/DiagnosticReport';
import { getTrendDirection, previousWindowCount } from '@/lib/trends';
import { DollarSign, TrendingUp, AlertTriangle, FileText, Loader2, Download } from 'lucide-react';

interface CeoData {
  receita_liquida?: number;
  score_juno?: number;
}

interface CfoRow {
  product: string;
  receita_liquida: number;
  custo_real: number;
  margem: number;
  [key: string]: unknown;
}

interface DashboardRow {
  order_id: number;
  product: string;
  planned_date: string;
  actual_date: string | null;
  status: string;
  [key: string]: unknown;
}

interface InsightRow {
  type?: string;
  message: string;
  impact: string;
  action: string;
}

interface ReportData {
  company_name: string;
  score_juno: number;
  revenue: number;
  insights: Array<{ message: string; impact: string }>;
  recommendations: string[];
  action_plan: string[];
}

export default function RomiPage() {
  const { t, locale } = useI18n();
  const { company, companyId, isLoading: companyLoading } = useActiveCompany();
  const [ceoData, setCeoData] = useState<CeoData | null>(null);
  const [cfoData, setCfoData] = useState<CfoRow[]>([]);
  const [cooData, setCooData] = useState<DashboardRow[]>([]);
  const [insightsData, setInsightsData] = useState<InsightRow[]>([]);
  const [events7d, setEvents7d] = useState(0);
  const [eventsPrev7d, setEventsPrev7d] = useState(0);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [downloadingPDF, setDownloadingPDF] = useState(false);
  const receitaLiquida = ceoData?.receita_liquida ?? 0;
  const totalMargin = cfoData.reduce((sum, item) => sum + Number(item.margem ?? 0), 0);
  const totalRevenueFromMargins = cfoData.reduce(
    (sum, item) => sum + Number(item.receita_liquida ?? 0),
    0,
  );
  const averageMarginPct = totalRevenueFromMargins
    ? (totalMargin / totalRevenueFromMargins) * 100
    : null;

  useEffect(() => {
    async function fetchData() {
      if (companyLoading) return;
      if (!companyId) {
        setLoading(false);
        return;
      }
      try {
        const fetchCeo = api.get(`/dashboard/ceo/${companyId}`).then(r => r.data).catch(() => ({ receita_liquida: 0, score_juno: 0 }));
        const fetchCfo = api.get(`/dashboard/cfo/${companyId}`).then(r => r.data).catch(() => []);
        const fetchCoo = api.get(`/dashboard/coo/${companyId}`).then(r => r.data).catch(() => []);
        const fetchIns = api.get(`/insights/${companyId}?lang=${locale}`).then(r => r.data).catch(() => []);
        const fetchEvents7d = api.get(`/events/${companyId}?count_only=true&days=7`).then(r => Number(r.data?.count ?? 0)).catch(() => 0);
        const fetchEvents14d = api.get(`/events/${companyId}?count_only=true&days=14`).then(r => Number(r.data?.count ?? 0)).catch(() => 0);

        const [ceo, cfo, coo, ins, e7, e14] = await Promise.all([
          fetchCeo,
          fetchCfo,
          fetchCoo,
          fetchIns,
          fetchEvents7d,
          fetchEvents14d,
        ]);

        setCeoData(ceo);
        setCfoData(cfo);
        setCooData(coo);
        setInsightsData(ins);
        setEvents7d(e7);
        setEventsPrev7d(previousWindowCount(e7, e14));
      } catch (error) {
        console.error("Erro ao carregar dados da Minha Empresa:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [companyId, companyLoading, locale]);

  const handleGenerateReport = async () => {
    if (!companyId) return;
    setGeneratingReport(true);
    try {
      const res = await api.get(`/report/diagnostic/${companyId}?lang=${locale}`);
      setReportData(res.data);
    } catch (error) {
      console.error("Erro ao gerar diagnóstico:", error);
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleDownloadPDF = async () => {
    if (!companyId) return;
    setDownloadingPDF(true);
    try {
      const res = await api.get(`/report/pdf/${companyId}?lang=${locale}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'JUNO_Diagnostico_Minha_Empresa.pdf';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Erro ao baixar PDF:", error);
    } finally {
      setDownloadingPDF(false);
    }
  };

  if (loading || companyLoading) return <div className="flex items-center justify-center h-full">{t('myCompany.loading')}</div>;
  if (!companyId) {
    return (
      <div className="bg-white border border-yellow-100 rounded-lg p-8">
        <h1 className="text-xl font-bold text-[#0A2342]">{t('myCompany.noCompanyTitle')}</h1>
        <p className="mt-2 text-sm text-gray-600">{t('myCompany.noCompanyDesc')}</p>
      </div>
    );
  }

  const eventTrend = getTrendDirection(events7d, eventsPrev7d);

  return (
    <div className="space-y-8">
      <div className="border-b border-gray-200 pb-4 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-[#0A2342]">{company?.name ?? t('myCompany.defaultName')} — {t('myCompany.title360')}</h1>
          <p className="text-gray-500 text-sm">{t('myCompany.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateReport}
            disabled={generatingReport}
            className="flex items-center gap-2 bg-[#C9A959] text-[#0A2342] font-bold py-2 px-6 rounded-lg hover:bg-[#b89a51] transition-colors shadow-md disabled:opacity-50"
          >
            {generatingReport ? <Loader2 className="animate-spin" size={18} /> : <FileText size={18} />}
            {t('myCompany.generate')}
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={downloadingPDF}
            className="flex items-center gap-2 bg-[#0A2342] text-white font-bold py-2 px-6 rounded-lg hover:bg-[#0d2d57] transition-colors shadow-md disabled:opacity-50"
          >
            {downloadingPDF ? <Loader2 className="animate-spin" size={18} /> : <Download size={18} />}
            {t('myCompany.downloadPdf')}
          </button>
        </div>
      </div>

      {reportData && <DiagnosticReport data={reportData} />}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1">
          <ScoreCard score={ceoData?.score_juno ?? 0} />
        </div>
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6">
          <MetricCard
            title={t('myCompany.revenueNet')}
            value={`R$ ${receitaLiquida.toLocaleString()}`}
            icon={<DollarSign size={20} />}
          />
          <MetricCard
            title={t('myCompany.avgMargin')}
            value={averageMarginPct == null ? t('myCompany.noData') : `${averageMarginPct.toFixed(1)}%`}
            icon={<TrendingUp size={20} />}
          />
          <MetricCard
            title={t('myCompany.criticalAlerts')}
            value={cooData.length}
            subtitle={t('myCompany.eventsSub', { n: events7d, prev: eventsPrev7d })}
            icon={<AlertTriangle size={20} />}
            trend={eventTrend}
          />
        </div>
      </div>

      <InsightSection insights={insightsData} />

      <div className="grid grid-cols-1 gap-8">
        <MarginTable data={cfoData} />
        <DelayTable data={cooData} />
      </div>

      <div className="bg-blue-50 border-l-4 border-[#0A2342] p-4 rounded-r-lg">
        <h4 className="font-bold text-[#0A2342] mb-1 uppercase text-xs">{t('myCompany.execAlerts')}</h4>
        {insightsData.length === 0 && cooData.length === 0 ? (
          <p className="text-sm text-gray-700">{t('myCompany.noAlerts')}</p>
        ) : (
          <ul className="text-sm text-gray-700 list-disc ml-4 space-y-1">
            {insightsData.slice(0, 3).map((insight, index) => (
              <li key={`${insight.type ?? 'insight'}-${index}`}>{insight.message}</li>
            ))}
            {insightsData.length === 0 && cooData.length > 0 && (
              <li>{t('myCompany.delayedOrdersAlert', { n: cooData.length })}</li>
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
