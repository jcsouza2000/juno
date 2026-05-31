interface MarginItem {
  product: string;
  receita_liquida: number;
  custo_real: number;
  margem: number;
}

export default function MarginTable({ data }: { data: MarginItem[] }) {
  const getStatus = (margin: number) => {
    if (margin < 0) return { text: 'Margem Negativa', class: 'bg-red-100 text-red-700' };
    if (margin < 50000) return { text: 'Margem Crítica', class: 'bg-yellow-100 text-yellow-700' };
    return { text: 'Margem Saudável', class: 'bg-green-100 text-green-700' };
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h3 className="font-bold text-gray-800">Análise de Margem por Produto/Projeto</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-semibold">
            <tr>
              <th className="px-6 py-3">Produto/Projeto</th>
              <th className="px-6 py-3">Receita</th>
              <th className="px-6 py-3">Custo</th>
              <th className="px-6 py-3">Margem</th>
              <th className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 text-sm">
            {data.map((item, i) => {
              const status = getStatus(item.margem);
              return (
                <tr key={i} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 font-medium text-gray-900">{item.product}</td>
                  <td className="px-6 py-4">R$ {item.receita_liquida.toLocaleString()}</td>
                  <td className="px-6 py-4">R$ {item.custo_real.toLocaleString()}</td>
                  <td className={`px-6 py-4 font-bold ${item.margem < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                    R$ {item.margem.toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${status.class}`}>
                      {status.text}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
