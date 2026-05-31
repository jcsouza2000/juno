export type TrendDirection = 'up' | 'down' | 'neutral';
export type TrendBadgeDirection = 'up' | 'down' | 'flat';

export interface TrendInfo {
  text: string;
  className: string;
  direction: TrendBadgeDirection;
}

export function getTrendDirection(current: number, previous: number): TrendDirection {
  if (current > previous) return 'up';
  if (current < previous) return 'down';
  return 'neutral';
}

export function previousWindowCount(currentWindowCount: number, largerWindowCount: number): number {
  return Math.max(0, largerWindowCount - currentWindowCount);
}

export function getTrendInfo(current: number, previous: number): TrendInfo {
  const diff = current - previous;

  const pctText = (): string => {
    if (previous === 0) {
      if (current === 0) return '0%';
      return 'novo';
    }
    const pct = Math.round((diff / previous) * 100);
    return `${pct > 0 ? '+' : ''}${pct}%`;
  };

  if (current > previous) {
    return {
      text: `Alta +${diff} (${pctText()})`,
      className: 'text-green-700 bg-green-100',
      direction: 'up',
    };
  }

  if (current < previous) {
    return {
      text: `Queda ${diff} (${pctText()})`,
      className: 'text-red-700 bg-red-100',
      direction: 'down',
    };
  }

  return {
    text: `Estavel (${pctText()})`,
    className: 'text-gray-700 bg-gray-100',
    direction: 'flat',
  };
}
