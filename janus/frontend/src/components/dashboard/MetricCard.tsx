import { Minus, TrendingDown, TrendingUp } from 'lucide-react';
import { useI18n } from '@/lib/i18n';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}

export default function MetricCard({ title, value, subtitle, icon, trend }: MetricCardProps) {
  const { t } = useI18n();
  const trendStyle =
    trend === 'up'
      ? 'bg-green-100 text-green-700'
      : trend === 'down'
      ? 'bg-red-100 text-red-700'
      : 'bg-gray-100 text-gray-700';

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">{title}</p>
          <h3 className="text-3xl font-bold mt-2 text-gray-900">{value}</h3>
          {subtitle && (
            <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
          )}
          {trend && (
            <span className={`inline-flex items-center gap-1 mt-2 px-2 py-1 rounded-full text-[10px] font-bold ${trendStyle}`}>
              {trend === 'up' && <TrendingUp size={11} />}
              {trend === 'down' && <TrendingDown size={11} />}
              {trend === 'neutral' && <Minus size={11} />}
              <span>{trend === 'up' ? t('myCompany.trend.up') : trend === 'down' ? t('myCompany.trend.down') : t('myCompany.trend.stable')}</span>
            </span>
          )}
        </div>
        {icon && (
          <div className="p-3 rounded-md bg-blue-50 text-[#0A2342]">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
