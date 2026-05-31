import Link from 'next/link';
import { Factory, MessageSquare, BarChart3, Gauge, Plug, Rocket, ShieldCheck } from 'lucide-react';

export default function Home() {
  const pilots = [
    {
      title: "Minha Empresa",
      description: "Diagnóstico operacional unificado para qualquer atividade econômica — manufatura, serviços, comércio ou agroindústria.",
      href: "/romi",
      icon: <Factory size={32} className="text-[#C9A959]" />,
      color: "border-blue-200"
    },
    {
      title: "KPIs Executivos",
      description: "Score proprietario, sintese analitica e tres quadrantes — operacao, financeiro e risco em uma unica tela.",
      href: "/executive",
      icon: <Gauge size={32} className="text-[#C9A959]" />,
      color: "border-blue-200"
    },
    {
      title: "IA Operacional",
      description: "Decisões governadas por dados cruzando Ontology e RAG.",
      href: "/ai",
      icon: <MessageSquare size={32} className="text-[#C9A959]" />,
      color: "border-blue-200"
    },
    {
      title: "Score Industrial",
      description: "Métrica proprietária de saúde operacional em tempo real.",
      href: "/audit",
      icon: <BarChart3 size={32} className="text-[#C9A959]" />,
      color: "border-blue-200"
    }
  ];

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-12 text-center">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-[#C9A959] mb-4">
          SaaS hibrido para empresas brasileiras
        </p>
        <h1 className="text-4xl font-extrabold text-[#0A2342] mb-4">
          JUNO — Sistema Operacional de Dados e IA
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Plataforma para decisões empresariais governadas, com IA, auditoria e integração ERP sem tirar o cliente do seu ambiente.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-xs font-bold uppercase">
          <span className="rounded-full bg-white border border-gray-100 px-4 py-2 text-[#0A2342]">Cloud ou on-prem</span>
          <span className="rounded-full bg-white border border-gray-100 px-4 py-2 text-[#0A2342]">LGPD e trilha de auditoria</span>
          <span className="rounded-full bg-white border border-gray-100 px-4 py-2 text-[#0A2342]">TOTVS, Sankhya, Senior, SAP e Infor</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {pilots.map((pilot, i) => (
          <div key={i} className="bg-white p-8 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-between hover:shadow-md transition-shadow">
            <div>
              <div className="mb-4">{pilot.icon}</div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">{pilot.title}</h3>
              <p className="text-gray-500 text-sm mb-6">{pilot.description}</p>
            </div>
            <Link
              href={pilot.href}
              className="inline-flex items-center justify-center bg-[#0A2342] text-white font-bold py-3 px-6 rounded-lg hover:bg-[#0c2d54] transition-colors"
            >
              Abrir Diagnóstico
            </Link>
          </div>
        ))}
      </div>

      <section className="mt-12 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <ShieldCheck className="text-[#C9A959]" size={28} />
          <h2 className="mt-4 text-lg font-bold text-[#0A2342]">Confiança para diretoria</h2>
          <p className="mt-2 text-sm text-gray-500">
            Score JUNO, Data Trust, logs e governança para explicar de onde veio cada recomendação.
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <Plug className="text-[#C9A959]" size={28} />
          <h2 className="mt-4 text-lg font-bold text-[#0A2342]">Entrada por CSV, escala por ERP</h2>
          <p className="mt-2 text-sm text-gray-500">
            Comece com planilhas no piloto e evolua para conectores controlados por tenant.
          </p>
        </div>
        <div className="bg-[#0A2342] rounded-xl p-6 text-white">
          <Rocket className="text-[#C9A959]" size={28} />
          <h2 className="mt-4 text-lg font-bold">Piloto de 30 dias</h2>
          <p className="mt-2 text-sm text-blue-100">
            Diagnóstico executivo, auditoria de dados e plano de ação para validar valor antes da implantação completa.
          </p>
          <Link
            href="/pilot"
            className="mt-5 inline-flex items-center justify-center rounded-lg bg-[#C9A959] px-5 py-2 text-sm font-bold text-[#0A2342]"
          >
            Ver roteiro do piloto
          </Link>
        </div>
      </section>
    </div>
  );
}
