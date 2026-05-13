import { useMemo } from 'react';
import type { GFTAtcIndexItem } from '../../types/gft';

interface GftAtcIndexProps {
  items: GFTAtcIndexItem[];
  selectedAtc: string;
  onSelectAtc: (value: string) => void;
}

interface NormalizedAtcItem {
  code: string;
  name: string | null;
  level: string;
  count: number;
}

interface AtcSection {
  code: string;
  name: string | null;
  count: number;
  children: AtcSubgroup[];
}

interface AtcSubgroup {
  code: string;
  name: string | null;
  count: number;
}

function normalizeCode(code: string): string {
  return code.trim().toUpperCase();
}

function normalizeLevel(level: string): string {
  return level.trim().toUpperCase();
}

function isLevel(item: NormalizedAtcItem, level: number): boolean {
  const normalizedLevel = normalizeLevel(item.level);
  return normalizedLevel === String(level) || normalizedLevel === `L${level}` || normalizedLevel === `ATC${level}`;
}

function getSectionCode(item: NormalizedAtcItem, hasExplicitLevel1: boolean): string {
  if (hasExplicitLevel1 && isLevel(item, 1)) {
    return item.code;
  }

  return item.code.slice(0, 1);
}

function getSubgroupCode(item: NormalizedAtcItem, hasExplicitLevel2: boolean): string {
  if (hasExplicitLevel2 && isLevel(item, 2)) {
    return item.code;
  }

  return item.code.slice(0, 3);
}

function mergeName(currentName: string | null, nextName: string | null): string | null {
  return currentName ?? nextName;
}

function mergeCount(currentCount: number, nextCount: number): number {
  return Math.max(currentCount, nextCount);
}

function toNormalizedItems(items: GFTAtcIndexItem[]): NormalizedAtcItem[] {
  return items
    .map((item) => ({
      code: normalizeCode(item.codigo),
      name: item.nombre,
      level: item.nivel,
      count: item.count,
    }))
    .filter((item) => item.code);
}

function deriveSections(items: GFTAtcIndexItem[]): AtcSection[] {
  const normalizedItems = toNormalizedItems(items);
  const itemByCode = new Map(normalizedItems.map((item) => [item.code, item]));
  const hasExplicitLevel1 = normalizedItems.some((item) => isLevel(item, 1));
  const hasExplicitLevel2 = normalizedItems.some((item) => isLevel(item, 2));
  const sections = new Map<string, AtcSection>();

  normalizedItems.forEach((item) => {
    const sectionCode = getSectionCode(item, hasExplicitLevel1);

    if (!sectionCode) {
      return;
    }

    const exactSectionItem = itemByCode.get(sectionCode);
    const section = sections.get(sectionCode) ?? {
      code: sectionCode,
      name: exactSectionItem?.name ?? null,
      count: exactSectionItem?.count ?? 0,
      children: [],
    };

    section.name = mergeName(section.name, exactSectionItem?.name ?? null);
    section.count = exactSectionItem ? mergeCount(section.count, exactSectionItem.count) : section.count;

    if (item.code !== sectionCode) {
      section.count = mergeCount(section.count, item.count);
    }

    sections.set(sectionCode, section);
  });

  sections.forEach((section) => {
    const subgroups = new Map<string, AtcSubgroup>();

    normalizedItems
      .filter((item) => item.code.startsWith(section.code) && item.code !== section.code)
      .forEach((item) => {
        const subgroupCode = getSubgroupCode(item, hasExplicitLevel2);

        if (!subgroupCode || subgroupCode === section.code) {
          return;
        }

        const exactSubgroupItem = itemByCode.get(subgroupCode);
        const subgroup = subgroups.get(subgroupCode) ?? {
          code: subgroupCode,
          name: exactSubgroupItem?.name ?? null,
          count: exactSubgroupItem?.count ?? 0,
        };

        subgroup.name = mergeName(subgroup.name, exactSubgroupItem?.name ?? null);
        subgroup.count = exactSubgroupItem ? mergeCount(subgroup.count, exactSubgroupItem.count) : subgroup.count;

        if (item.code !== subgroupCode) {
          subgroup.count = mergeCount(subgroup.count, item.count);
        }

        subgroups.set(subgroupCode, subgroup);
      });

    section.children = Array.from(subgroups.values()).sort((first, second) => first.code.localeCompare(second.code, 'es'));
  });

  return Array.from(sections.values()).sort((first, second) => first.code.localeCompare(second.code, 'es'));
}

function getTotalCount(items: GFTAtcIndexItem[]): number {
  const normalizedItems = toNormalizedItems(items);
  const level1Total = normalizedItems.filter((item) => isLevel(item, 1)).reduce((total, item) => total + item.count, 0);

  if (level1Total > 0) {
    return level1Total;
  }

  return deriveSections(items).reduce((total, section) => total + section.count, 0);
}

function formatLabel(code: string, name: string | null): string {
  return name ? `${code} — ${name}` : code;
}

export function GftAtcIndex({ items, selectedAtc, onSelectAtc }: GftAtcIndexProps) {
  const sections = useMemo(() => deriveSections(items), [items]);
  const totalMedicationCount = useMemo(() => getTotalCount(items), [items]);

  return (
    <section className="gft-atc-index" aria-labelledby="gft-atc-index-title">
      <div className="gft-atc-index__header">
        <div>
          <h2 className="gft-atc-index__title" id="gft-atc-index-title">
            Índice ATC
          </h2>
          <p className="gft-atc-index__subtitle">Navegación por grupos terapéuticos</p>
        </div>
        <span className="gft-atc-index__count" aria-label={`${totalMedicationCount} medicamentos en el índice ATC`}>
          {totalMedicationCount}
        </span>
      </div>

      <button
        type="button"
        className={`gft-atc-index__button gft-atc-index__button--all${selectedAtc ? '' : ' gft-atc-index__button--active'}`}
        aria-pressed={!selectedAtc}
        onClick={() => onSelectAtc('')}
      >
        <span>Todos los grupos</span>
        <span className="gft-atc-index__count">{totalMedicationCount}</span>
      </button>

      {sections.length > 0 ? (
        <div className="gft-atc-index__groups">
          {sections.map((section) => {
            const isSectionActive = selectedAtc === section.code;
            const hasActiveChild = Boolean(selectedAtc) && selectedAtc !== section.code && selectedAtc.startsWith(section.code);

            return (
              <div className="gft-atc-index__section" key={section.code}>
                <button
                  type="button"
                  className={`gft-atc-index__section-title${isSectionActive ? ' gft-atc-index__section-title--active' : ''}${
                    hasActiveChild ? ' gft-atc-index__section-title--parent-active' : ''
                  }`}
                  aria-pressed={isSectionActive}
                  onClick={() => onSelectAtc(section.code)}
                >
                  <span>{formatLabel(section.code, section.name)}</span>
                  <span className="gft-atc-index__count">{section.count}</span>
                </button>

                {section.children.length > 0 ? (
                  <div className="gft-atc-index__subgroups" aria-label={`Subgrupos de ${section.code}`}>
                    {section.children.map((child) => {
                      const isChildActive = selectedAtc === child.code;

                      return (
                        <button
                          type="button"
                          className={`gft-atc-index__button${isChildActive ? ' gft-atc-index__button--active' : ''}`}
                          aria-pressed={isChildActive}
                          key={child.code}
                          onClick={() => onSelectAtc(child.code)}
                        >
                          <span>{formatLabel(child.code, child.name)}</span>
                          <span className="gft-atc-index__count">{child.count}</span>
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="gft-atc-index__empty">No hay grupos ATC disponibles en el índice global.</p>
      )}
    </section>
  );
}
