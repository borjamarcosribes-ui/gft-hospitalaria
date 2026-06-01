const MOJIBAKE_MARKERS = /(?:Ã.|Â.|â[\u0080-\u00bf])/;

function repairLatin1Utf8Mojibake(value: string): string {
  const bytes = Uint8Array.from(Array.from(value, (char) => char.charCodeAt(0) & 0xff));
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
}

function looksBetterAfterRepair(original: string, repaired: string): boolean {
  const originalMarkers = (original.match(MOJIBAKE_MARKERS) ?? []).length;
  const repairedMarkers = (repaired.match(MOJIBAKE_MARKERS) ?? []).length;

  if (originalMarkers === 0 || repairedMarkers >= originalMarkers) {
    return false;
  }

  if (/�/.test(repaired)) {
    return false;
  }

  return true;
}

/**
 * Defensive presentation-only repair for clear UTF-8 bytes decoded as Latin-1.
 * The mojibake observed in GFT values is already present in API strings, so this
 * helper intentionally fixes only obvious display patterns and never mutates cache
 * or backend data.
 */
export function normalizeDisplayText(value: string): string;
export function normalizeDisplayText(value: string | null | undefined): string | null;
export function normalizeDisplayText(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (!MOJIBAKE_MARKERS.test(value)) {
    return value;
  }

  try {
    const repaired = repairLatin1Utf8Mojibake(value);
    return looksBetterAfterRepair(value, repaired) ? repaired : value;
  } catch {
    return value;
  }
}

export function normalizeDisplayValue(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return 'No informado';
  }

  if (typeof value === 'boolean') {
    return value ? 'Sí' : 'No';
  }

  const normalized = normalizeDisplayText(String(value).trim());
  return normalized?.trim() || 'No informado';
}
