import { FileText, CheckCircle, AlertCircle, ArrowRight } from 'lucide-react';

interface DiagnosticData {
  company_name: string;
  score_juno: number;
  revenue: number;
  insights: Array<{ message: string; impact: string }>;
  recommendations: string[];
  action_plan: string[];
}

export default function DiagnosticReport({ data }: { data: DiagnosticData }) {
  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden mt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="bg-[#0A2342] p-8 text-white">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold">Diagnóstico 360: {data.company_name}</h2>
            <p className="text-blue-200 mt-2">Relatório Executivo de Saúde Industrial</p>
          </div>
          <div className="text-right">
            <div className="text-sm uppercase tracking-widest text-blue-300">Score JUNO</div>
            <div className="text-5xl font-extrabold text-[#C9A959]">{data.score_juno}</div>
          </div>
        </div>
      </div>

      <div className="p-8 space-y-10">
        {/* Resumo Executivo */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <FileText className="text-[#0A2342]" size={24} />
            <h3 className="text-xl font-bold text-gray-800 uppercase tracking-tight">Resumo Executivo</h3>
          </div>
          <p className="text-gray-600 leading-relaxed">
            A análise atual da <strong>{data.company_name}</strong> revela um faturamento de <strong>R$ {data.revenue.toLocaleString()}</strong>. 
            O Score JUNO de <strong>{data.score_juno}</strong> indica um estado de 
            {data.score_juno >= 85 ? ' Excelente Saúde Operacional' : 
             data.score_juno >= 70 ? ' Boa Saúde, com pontos de atenção' : ' Risco Operacional Crítico'}.
          </p>
        </section>

        {/* Riscos Encontrados */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <AlertCircle className="text-red-500" size={24} />
            <h3 className="text-xl font-bold text-gray-800 uppercase tracking-tight">Riscos Encontrados</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.insights.map((insight, i) => (
              <div key={i} className="p-4 rounded-lg bg-red-50 border-l-4 border-red-500">
                <p className="text-sm font-bold text-red-800">{insight.message}</p>
                <p className="text-xs text-red-600 mt-1 uppercase">Impacto: {insight.impact}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Recomendações e Plano de Ação */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
          <section>
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle className="text-[#C9A959]" size={24} />
              <h3 className="text-xl font-bold text-gray-800 uppercase tracking-tight">Recomendações JUNO</h3>
            </div>
            <ul className="space-y-3">
              {data.recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                  <ArrowRight size={16} className="text-[#C9A959] mt-1 shrink-0" />
                  {rec}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-6 h-6 rounded-full bg-[#0A2342] text-white flex items-center justify-center text-xs font-bold">!</div>
              <h3 className="text-xl font-bold text-gray-800 uppercase tracking-tight">Plano de Ação (30 dias)</h3>
            </div>
            <ul className="space-y-3">
              {data.action_plan.map((step, i) => (
                <li key={i} className="flex items-start gap-2 text-sm font-medium text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                  {step}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="pt-8 border-t border-gray-100 text-center">
          <p className="text-xs text-gray-400 uppercase tracking-widest">
            Gerado automaticamente pelo JUNO Industrial Diagnostic v0.2.1 — © 2025
          </p>
        </div>
      </div>
    </div>
  );
}
