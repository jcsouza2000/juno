"use client";

import Link from 'next/link';
import { Home, MessageSquare, ShieldCheck, Factory, Plug, Play, Rocket, BarChart2, ShieldAlert, Gauge, LockKeyhole } from 'lucide-react';
import { useSession } from 'next-auth/react';

export default function Sidebar() {
  const { data: session } = useSession();
  const role = session?.user?.role;
  const isAdmin = role === 'admin' || role === 'platform_admin';
  const menuItems = [
    { name: 'Visão Geral',        icon: <Home size={20} />,           href: '/',             highlight: false, danger: false },
    { name: 'Minha Empresa',      icon: <Factory size={20} />,        href: '/romi',         highlight: false, danger: false },
    { name: 'KPIs Executivos',    icon: <Gauge size={20} />,          href: '/executive',    highlight: false, danger: false },
    { name: 'IA Operacional',     icon: <MessageSquare size={20} />,  href: '/ai',           highlight: false, danger: false },
    { name: 'Financeiro',         icon: <BarChart2 size={20} />,      href: '/financials',   highlight: false, danger: false },
    { name: 'Integrações ERP',    icon: <Plug size={20} />,           href: '/integrations', highlight: false, danger: false },
    { name: 'Auditoria',          icon: <ShieldCheck size={20} />,    href: '/audit',        highlight: false, danger: false },
    { name: 'Trust Center',        icon: <LockKeyhole size={20} />,    href: '/trust',        highlight: false, danger: false },
    ...(isAdmin ? [
      { name: 'Governança',       icon: <ShieldCheck size={20} />,    href: '/admin/markings', highlight: false, danger: false },
      { name: 'Auto Teste',       icon: <ShieldAlert size={20} />,    href: '/autotest',     highlight: false, danger: true  },
    ] : []),
    { name: 'Demo Executivo',     icon: <Play size={20} />,           href: '/demo',         highlight: true,  danger: false },
    { name: 'Piloto',             icon: <Rocket size={20} />,         href: '/pilot',        highlight: true,  danger: false },
  ];

  return (
    <aside className="w-64 bg-[#0A2342] text-white h-screen fixed left-0 top-0 flex flex-col">
      <div className="p-6 border-b border-white/10">
        <h1 className="text-2xl font-bold text-[#C9A959]">JUNO</h1>
        <p className="text-xs text-gray-400 mt-1 uppercase tracking-widest">Industrial Diagnostic</p>
      </div>

      <nav className="mt-6 flex-1 overflow-y-auto pb-4">
        {menuItems.map((item, i) => (
          <span key={item.name}>
            {item.highlight && i > 0 && !menuItems[i - 1].highlight && (
              <div className="mx-6 my-2 border-t border-white/10" />
            )}
            <Link
              href={item.href}
              className={`flex items-center gap-3 px-6 py-4 transition-colors border-l-4 ${
                item.danger
                  ? 'text-red-400 border-transparent hover:bg-red-900/30 hover:border-red-400'
                  : item.highlight
                  ? 'text-[#C9A959] border-transparent hover:bg-[#C9A959]/10 hover:border-[#C9A959]'
                  : 'border-transparent hover:bg-white/5 hover:border-[#C9A959]'
              }`}
            >
              {item.icon}
              <span className="text-sm font-medium">{item.name}</span>
              {item.danger && (
                <span className="ml-auto text-[10px] font-bold bg-red-900/40 text-red-400 px-1.5 py-0.5 rounded uppercase tracking-wider">
                  TEST
                </span>
              )}
              {item.highlight && (
                <span className="ml-auto text-[10px] font-bold bg-[#C9A959]/20 text-[#C9A959] px-1.5 py-0.5 rounded uppercase tracking-wider">
                  NEW
                </span>
              )}
            </Link>
          </span>
        ))}
      </nav>

      <div className="m-6 mt-auto p-4 rounded-lg bg-white/5">
        <p className="text-[10px] text-gray-500 uppercase tracking-wider">Status Sistema</p>
        <div className="flex items-center gap-2 mt-2">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-xs font-semibold">v0.3.2 — ONLINE</span>
        </div>
      </div>
    </aside>
  );
}
