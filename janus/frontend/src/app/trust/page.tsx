"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BrainCircuit, CheckCircle2, Database, FileText, Lock, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

type TrustControl = {
  id: string;
  label: string;
  status: "active" | "planned" | string;
  evidence: string;
};

type TrustPosture = {
  trust_level: string;
  generated_at: string;
  summary: {
    audit_events_24h: number;
    open_data_subject_requests: number;
    mfa_required: boolean;
    session_timeout_minutes: number;
    data_retention_days: number;
  };
  controls: TrustControl[];
  next_certification_targets: string[];
};

const pillars = [
  {
    title: "Segurança enterprise",
    icon: <Lock size={24} />,
    text: "RBAC, roles por tenant, autenticação obrigatória e trilha para MFA/SSO.",
  },
  {
    title: "Isolamento multi-tenant",
    icon: <Database size={24} />,
    text: "Cada leitura sensível precisa carregar o tenant validado antes de consultar dados.",
  },
  {
    title: "LGPD operacional",
    icon: <FileText size={24} />,
    text: "DSR, consentimentos, retenção e evidências por empresa, com auditoria consultável.",
  },
  {
    title: "IA governada",
    icon: <BrainCircuit size={24} />,
    text: "Ações propostas pela IA exigem confirmação humana e devem manter evidência auditável.",
  },
];

export default function TrustCenterPage() {
  const [posture, setPosture] = useState<TrustPosture | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get("/api/v1/security/trust/posture")
      .then((res) => {
        setPosture(res.data);
        setError(null);
      })
      .catch(() => {
        setError("Postura em tempo real restrita a administradores do tenant.");
      });
  }, []);

  return (
    <div className="space-y-8">
      <section className="rounded-2xl bg-[#0A2342] p-8 text-white">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-[#C9A959]">Trust Center</p>
        <h1 className="mt-4 text-3xl font-extrabold">Confiança inata para SaaS hibrido</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-blue-100">
          O JUNO deve provar segurança, isolamento, LGPD, IA governada e operação confiável em cada tenant,
          não apenas prometer tecnologia.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <span className="rounded-full bg-white/10 px-4 py-2 text-xs font-bold uppercase">Cloud ou on-prem</span>
          <span className="rounded-full bg-white/10 px-4 py-2 text-xs font-bold uppercase">Auditoria por tenant</span>
          <span className="rounded-full bg-white/10 px-4 py-2 text-xs font-bold uppercase">LGPD-ready</span>
        </div>
      </section>

      {posture && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Metric label="Eventos auditados 24h" value={String(posture.summary.audit_events_24h)} />
          <Metric label="DSR em aberto" value={String(posture.summary.open_data_subject_requests)} />
          <Metric label="MFA" value={posture.summary.mfa_required ? "Ativo" : "Planejado"} />
          <Metric label="Sessão" value={`${posture.summary.session_timeout_minutes} min`} />
        </section>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-yellow-100 bg-yellow-50 p-4 text-sm text-yellow-800">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {pillars.map((pillar) => (
          <div key={pillar.title} className="rounded-xl border border-gray-100 bg-white p-6">
            <div className="text-[#C9A959]">{pillar.icon}</div>
            <h2 className="mt-4 text-lg font-bold text-[#0A2342]">{pillar.title}</h2>
            <p className="mt-2 text-sm leading-6 text-gray-500">{pillar.text}</p>
          </div>
        ))}
      </section>

      {posture && (
        <section className="rounded-xl border border-gray-100 bg-white p-6">
          <div className="flex items-center gap-2">
            <ShieldCheck className="text-[#C9A959]" size={22} />
            <h2 className="text-xl font-bold text-[#0A2342]">Controles com evidência</h2>
          </div>
          <div className="mt-6 space-y-4">
            {posture.controls.map((control) => (
              <div key={control.id} className="flex items-start gap-3 rounded-lg bg-gray-50 p-4">
                <CheckCircle2
                  size={18}
                  className={control.status === "active" ? "text-green-600" : "text-[#C9A959]"}
                />
                <div>
                  <p className="font-semibold text-[#0A2342]">
                    {control.label} <span className="text-xs uppercase text-gray-400">({control.status})</span>
                  </p>
                  <p className="mt-1 text-sm text-gray-500">{control.evidence}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-xl border border-gray-100 bg-white p-6">
        <h2 className="text-xl font-bold text-[#0A2342]">Terreno preparado, sem custo enterprise agora</h2>
        <p className="mt-2 text-sm leading-6 text-gray-500">
          O JUNO mantém os controles essenciais ativos e deixa MFA, SSO, SOC 2 e ISO 27001 como trilhas
          futuras para quando houver cliente, receita ou exigência contratual.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          {(posture?.next_certification_targets ?? ["LGPD-ready", "ISO 27001 readiness", "SOC 2 readiness"]).map(
            (target) => (
              <span key={target} className="rounded-full bg-[#C9A959]/10 px-4 py-2 text-sm font-bold text-[#8A6D1D]">
                {target}
              </span>
            ),
          )}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-5">
      <p className="text-xs font-bold uppercase tracking-wider text-gray-400">{label}</p>
      <p className="mt-2 text-2xl font-extrabold text-[#0A2342]">{value}</p>
    </div>
  );
}
