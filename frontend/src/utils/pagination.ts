export interface PaginationRange {
  from: number;
  to: number;
  canPrevious: boolean;
  canNext: boolean;
}

export function getPaginationRange(total: number, limit: number, offset: number): PaginationRange {
  if (total <= 0) {
    return {
      from: 0,
      to: 0,
      canPrevious: false,
      canNext: false,
    };
  }

  const from = offset + 1;
  const to = Math.min(offset + limit, total);

  return {
    from,
    to,
    canPrevious: offset > 0,
    canNext: offset + limit < total,
  };
}
