import { useI18n } from '@/lib/i18n';

interface DelayItem {
  order_id: number;
  product: string;
  planned_date: string;
  actual_date: string | null;
  status: string;
}

export default function DelayTable({ data }: { data: DelayItem[] }) {
  const { t } = useI18n();
  const calculateDelay = (p: string, a: string | null) => {
    const planned = new Date(p);
    const actual = a ? new Date(a) : new Date();
    const diffTime = actual.getTime() - planned.getTime();
    return Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h3 className="font-bold text-gray-800">{t('myCompany.delay.title')}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-semibold">
            <tr>
              <th className="px-6 py-3">{t('myCompany.delay.colOrder')}</th>
              <th className="px-6 py-3">{t('myCompany.delay.colProduct')}</th>
              <th className="px-6 py-3">{t('myCompany.delay.colPlanned')}</th>
              <th className="px-6 py-3">{t('myCompany.delay.colActual')}</th>
              <th className="px-6 py-3">{t('myCompany.delay.colDays')}</th>
              <th className="px-6 py-3">{t('myCompany.delay.colStatus')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 text-sm">
            {data.map((item, i) => (
              <tr key={i} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 font-medium text-gray-900">#{item.order_id}</td>
                <td className="px-6 py-4">{item.product}</td>
                <td className="px-6 py-4 text-gray-500">{item.planned_date}</td>
                <td className="px-6 py-4 text-red-600 font-medium">{item.actual_date ?? t('myCompany.delay.open')}</td>
                <td className="px-6 py-4">
                  <span className="text-red-600 font-bold">{calculateDelay(item.planned_date, item.actual_date)} {t('myCompany.delay.daysUnit')}</span>
                </td>
                <td className="px-6 py-4">
                  <span className="px-2 py-1 rounded bg-gray-100 text-gray-700 text-[10px] font-bold uppercase">
                    {item.status}
                  </span>
                </td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                  {t('myCompany.delay.noDelays')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
