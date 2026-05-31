import { AlertTriangle, CheckCircle } from 'lucide-react';

interface Insight {
  type?: string;
  message: string;
  impact: string;
  action: string;
}

export default function InsightSection({ insights }: { insights: Insight[] }) {
  if (insights.length === 0) return (
    <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-lg">
      <div className="flex items-center gap-2 text-green-700">
        <CheckCircle size={18} />
        <span className="font-bold uppercase text-xs">Insights do JUNO</span>
      </div>
      <p className="text-sm text-green-600 mt-1">Nenhum risco crítico detectado no momento.</p>
    </div>
  );

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest">Insights do JUNO</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {insights.map((insight, i) => (
          <div key={i} className="bg-white p-5 rounded-lg border-l-4 border-red-500 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="text-red-500 mt-1" size={20} />
              <div>
                <p className="text-gray-900 font-bold text-sm">{insight.message}</p>
                <div className="mt-2 flex items-center gap-4 text-xs">
                  <span className="text-red-600 font-bold uppercase">Impacto: {insight.impact}</span>
                </div>
                <div className="mt-3 p-2 bg-gray-50 rounded border border-gray-100 text-[11px]">
                  <span className="font-bold text-gray-500 uppercase">Acao Recomendada:</span>
                  <p className="text-gray-700 mt-1">{insight.action}</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
