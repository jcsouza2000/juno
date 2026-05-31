'use client';

import { useEffect, useState } from 'react';
import { Layers, ArrowRight, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

interface WorkshopApp {
  object_type: string;
  title: string;
  description: string;
  fields: number;
  actions: number;
  links: number;
}

export default function WorkshopPage() {
  const [apps, setApps] = useState<WorkshopApp[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/v1/ontology/workshop/apps')
      .then(r => setApps(r.data?.apps ?? []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="border-b border-gray-200 pb-4">
        <div className="flex items-center gap-2">
          <Layers size={22} className="text-[#C9A959]" />
          <h1 className="text-2xl font-bold text-[#0A2342]">Workshop — Apps no-code</h1>
        </div>
        <p className="text-gray-500 text-sm mt-1">
          Cada ObjectType da ontologia vira um app pronto. UI gerada do schema, sem dev.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 className="animate-spin text-gray-400" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {apps.map(app => (
            <a
              key={app.object_type}
              href={`/workshop/${app.object_type}`}
              className="bg-white rounded-xl border border-gray-100 p-5 hover:border-[#C9A959] hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-lg font-bold text-[#0A2342]">{app.title}</h2>
                <ArrowRight size={18} className="text-[#C9A959]" />
              </div>
              <p className="text-sm text-gray-500 mb-3">{app.description || '—'}</p>
              <div className="flex gap-4 text-xs text-gray-400">
                <span>{app.fields} fields</span>
                <span>·</span>
                <span>{app.actions} actions</span>
                <span>·</span>
                <span>{app.links} links</span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
