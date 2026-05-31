interface ScoreCardProps {
  score: number;
}

export default function ScoreCard({ score }: ScoreCardProps) {
  const getStatus = (val: number) => {
    if (val >= 85) return { text: 'Excelente', color: 'text-green-600', bg: 'bg-green-100' };
    if (val >= 70) return { text: 'Bom', color: 'text-blue-600', bg: 'bg-blue-100' };
    if (val >= 50) return { text: 'Atenção', color: 'text-yellow-600', bg: 'bg-yellow-100' };
    return { text: 'Crítico', color: 'text-red-600', bg: 'bg-red-100' };
  };

  const status = getStatus(score);

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex flex-col items-center justify-center text-center">
      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">Score JUNO</p>
      <div className="relative w-32 h-32 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx="64"
            cy="64"
            r="58"
            stroke="currentColor"
            strokeWidth="10"
            fill="transparent"
            className="text-gray-100"
          />
          <circle
            cx="64"
            cy="64"
            r="58"
            stroke="currentColor"
            strokeWidth="10"
            fill="transparent"
            strokeDasharray={364.4}
            strokeDashoffset={364.4 - (364.4 * score) / 100}
            className="text-[#C9A959] transition-all duration-1000"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-4xl font-bold text-gray-900">{score}</span>
        </div>
      </div>
      <div className={`mt-4 px-4 py-1 rounded-full ${status.bg} ${status.color} text-xs font-bold uppercase`}>
        {status.text}
      </div>
    </div>
  );
}
