import { useMemo } from 'react';
import type { GFTAtcRef, GFTMedicamentoListItem } from '../../types/gft';

interface GftAtcIndexProps {
  medications: GFTMedicamentoListItem[];
  selectedAtc: string;
  onSelectAtc: (value: string) => void;
}

interface AtcGroup {
  code: string;
  name: string | null;
  medicationCns: Set<string>;
  children: Map<string, AtcGroup>;
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

function isLevel(ref: GFTAtcRef, level: number): boolean {
  const normalizedLevel = ref.nivel?.trim().toUpperCase();
  return normalizedLevel === String(level) || normalizedLevel === `L${level}` || normalizedLevel === `ATC${level}`;
}

function createGroup(code: string, name: string | null = null): AtcGroup {
  return {
    code,
    name,
    medicationCns: new Set<string>(),
    children: new Map<string, AtcGroup>(),
  };
}

function resolveName(currentName: string | null, nextName: string | null): string | null {
  return currentName ?? nextName;
}

function getReferenceName(refs: GFTAtcRef[], code: string): string | null {
  return refs.find((ref) => normalizeCode(ref.codigo) === code)?.nombre ?? null;
}

function deriveSections(medications: GFTMedicamentoListItem[]): AtcSection[] {
  const groups = new Map<string, AtcGroup>();

  medications.forEach((medication) => {
    const refs = medication.atc.filter((ref) => ref.codigo.trim());
    const level1Refs = refs.filter((ref) => isLevel(ref, 1));
    const level2Refs = refs.filter((ref) => isLevel(ref, 2));

    refs.forEach((ref) => {
      const code = normalizeCode(ref.codigo);
      const explicitLevel1 = level1Refs.find((item) => code.startsWith(normalizeCode(item.codigo)));
      const l1Code = explicitLevel1 ? normalizeCode(explicitLevel1.codigo) : code.slice(0, 1);

      if (!l1Code) {
        return;
      }

      const explicitLevel2 = level2Refs.find((item) => {
        const level2Code = normalizeCode(item.codigo);
        return code.startsWith(level2Code) && level2Code.startsWith(l1Code);
      });
      const l2Code = explicitLevel2 ? normalizeCode(explicitLevel2.codigo) : code.slice(0, 3);
      const l1Name = explicitLevel1?.nombre ?? getReferenceName(refs, l1Code);
      const l2Name = explicitLevel2?.nombre ?? getReferenceName(refs, l2Code);

      const l1Group = groups.get(l1Code) ?? createGroup(l1Code, l1Name);
      l1Group.name = resolveName(l1Group.name, l1Name);
      l1Group.medicationCns.add(medication.cn);
      groups.set(l1Code, l1Group);

      if (l2Code && l2Code !== l1Code) {
        const l2Group = l1Group.children.get(l2Code) ?? createGroup(l2Code, l2Name);
        l2Group.name = resolveName(l2Group.name, l2Name);
        l2Group.medicationCns.add(medication.cn);
        l1Group.children.set(l2Code, l2Group);
      }
    });
  });

  return Array.from(groups.values())
    .sort((first, second) => first.code.localeCompare(second.code, 'es'))
    .map((group) => ({
      code: group.code,
      name: group.name,
      count: group.medicationCns.size,
      children: Array.from(group.children.values())
        .sort((first, second) => first.code.localeCompare(second.code, 'es'))
        .map((child) => ({
          code: child.code,
          name: child.name,
          count: child.medicationCns.size,
        })),
    }));
}

function formatLabel(code: string, name: string | null): string {
  return name ? `${code} — ${name}` : code;
}

export function GftAtcIndex({ medications, selectedAtc, onSelectAtc }: GftAtcIndexProps) {
  const sections = useMemo(() => deriveSections(medications), [medications]);
  const totalMedicationCount = useMemo(() => new Set(medications.map((medication) => medication.cn)).size, [medications]);

  return (
    <section className="gft-atc-index" aria-labelledby="gft-atc-index-title">
      <div className="gft-atc-index__header">
        <div>
          <h2 className="gft-atc-index__title" id="gft-atc-index-title">
            Índice ATC
          </h2>
          <p className="gft-atc-index__subtitle">Navegación por grupos terapéuticos</p>
        </div>
        <span className="gft-atc-index__count" aria-label={`${totalMedicationCount} medicamentos cargados`}>
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
        <p className="gft-atc-index__empty">No hay grupos ATC en los medicamentos cargados.</p>
      )}
    </section>
  );
}
