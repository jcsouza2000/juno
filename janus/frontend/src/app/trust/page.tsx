"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BrainCircuit, CheckCircle2, Database, FileText, Lock, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

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

export default function TrustCenterPage() {
  const { t } = useI18n();
  const [posture, setPosture] = useState<TrustPosture | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pillars = [
    { title: t("trust.pillars.securityTitle"), icon: <Lock size={24} />, text: t("trust.pillars.securityText") },
    { title: t("trust.pillars.isolationTitle"), icon: <Database size={24} />, text: t("trust.pillars.isolationText") },
    { title: t("trust.pillars.lgpdTitle"), icon: <FileText size={24} />, text: t("trust.pillars.lgpdText") },
    { title: t("trust.pillars.aiTitle"), icon: <BrainCircuit size={24} />, text: t("trust.pillars.aiText") },
  ];

  useEffect(() => {
    api
      .get("/api/v1/security/trust/posture")
      .then((res) => {
        setPosture(res.data);
        setError(null);
      })
      .catch(() => {
        setError(t("trust.error"));
      });
  }, [t]);

  return (
    <div className="space-y-8">
      <section className="rounded-2xl bg-[#0A2342] p-8 text-white">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-[#C9A959]">{t("trust.eyebrow")}</p>
        <h1 className="mt-4 text-3xl font-extrabold">{t("trust.title")}</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-blue-100">
          {t("trust.subtitle")}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <span className="rounded-full bg-white/10 px-4 py-2 text-xs font-bold uppercase">{t("trust.badgeCloud")}</span>
          <span className="rounded-full bg-white/10 px-4 py-2 text-xs font-bold uppercase">{t("trust.badgeAudit")}</span>
          <span className="rounded-full bg-white/10 px-4 py-2 text-xs font-bold uppercase">{t("trust.badgeLgpd")}</span>
        </div>
      </section>

      {posture && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <Metric label={t("trust.metricAuditEvents")} value={String(posture.summary.audit_events_24h)} />
          <Metric label={t("trust.metricDsr")} value={String(posture.summary.open_data_subject_requests)} />
          <Metric label={t("trust.metricMfa")} value={posture.summary.mfa_required ? t("trust.active") : t("trust.planned")} />
          <Metric label={t("trust.metricSession")} value={t("trust.minutes", { n: posture.summary.session_timeout_minutes })} />
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
            <h2 className="text-xl font-bold text-[#0A2342]">{t("trust.controlsTitle")}</h2>
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
        <h2 className="text-xl font-bold text-[#0A2342]">{t("trust.futureTitle")}</h2>
        <p className="mt-2 text-sm leading-6 text-gray-500">
          {t("trust.futureText")}
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
