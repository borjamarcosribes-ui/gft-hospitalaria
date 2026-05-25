import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { GFTAtcIndexItem } from '../../types/gft';

interface GftAtcIndexProps {
  items: GFTAtcIndexItem[];
  selectedAtc: string;
  onSelectAtc: (value: string) => void;
}

interface AtcNode {
  code: string;
  name: string | null;
  level: number;
  count: number;
  children: AtcNode[];
}

const LEVEL_LABEL: Record<number, string> = {
  1: 'L1',
  2: 'L2',
  3: 'L3',
  4: 'L4',
  5: 'L5',
};

function normalizeCode(code: string): string {
  return code.trim().toUpperCase();
}

function parseLevel(level: string | null, code: string): number {
  const raw = (level ?? '').trim().toUpperCase();
  const direct = Number(raw.replace(/^ATC|^L/, ''));

  if (Number.isInteger(direct) && direct >= 1 && direct <= 5) {
    return direct;
  }

  if (code.length === 1) return 1;
  if (code.length === 3) return 2;
  if (code.length === 4) return 3;
  if (code.length === 5) return 4;
  return 5;
}

function prefixForLevel(code: string, level: number): string {
  if (level <= 1) return code.slice(0, 1);
  if (level === 2) return code.slice(0, 3);
  if (level === 3) return code.slice(0, 4);
  if (level === 4) return code.slice(0, 5);
  return code;
}

function buildTree(items: GFTAtcIndexItem[]): AtcNode[] {
  const normalized = items
    .map((item) => {
      const code = normalizeCode(item.codigo);
      const level = parseLevel(item.nivel ?? null, code);
      return {
        code,
        name: item.nombre,
        level,
        count: item.count,
      };
    })
    .filter((item) => item.code.length > 0);

  const byCode = new Map<string, AtcNode>();

  normalized.forEach((item) => {
    const existing = byCode.get(item.code);
    if (existing) {
      existing.name = existing.name ?? item.name;
      existing.level = Math.min(existing.level, item.level);
      existing.count = Math.max(existing.count, item.count);
      return;
    }

    byCode.set(item.code, {
      code: item.code,
      name: item.name,
      level: item.level,
      count: item.count,
      children: [],
    });
  });

  const roots: AtcNode[] = [];

  Array.from(byCode.values())
    .sort((a, b) => a.code.localeCompare(b.code, 'es'))
    .forEach((node) => {
      if (node.level <= 1) {
        roots.push(node);
        return;
      }

      let parent: AtcNode | undefined;
      for (let level = node.level - 1; level >= 1; level -= 1) {
        const parentCode = prefixForLevel(node.code, level);
        const maybeParent = byCode.get(parentCode);
        if (maybeParent && maybeParent.code !== node.code) {
          parent = maybeParent;
          break;
        }
      }

      if (parent) {
        parent.children.push(node);
      } else {
        roots.push(node);
      }
    });

  function sortChildren(nodes: AtcNode[]) {
    nodes.sort((a, b) => a.code.localeCompare(b.code, 'es'));
    nodes.forEach((node) => {
      if (node.children.length > 0) {
        sortChildren(node.children);
      }
    });
  }

  sortChildren(roots);
  return roots;
}

function formatNodeLabel(node: AtcNode): string {
  return node.name ? `${node.code} — ${node.name}` : node.code;
}

function collectDefaultExpandedCodes(nodes: AtcNode[], selectedAtc: string): Set<string> {
  const expanded = new Set<string>();

  function walk(node: AtcNode, ancestors: string[]) {
    if (selectedAtc && selectedAtc.startsWith(node.code)) {
      ancestors.forEach((ancestor) => expanded.add(ancestor));
      if (node.children.length > 0) {
        expanded.add(node.code);
      }
    }

    node.children.forEach((child) => walk(child, [...ancestors, node.code]));
  }

  nodes.forEach((node) => walk(node, []));
  return expanded;
}

export function GftAtcIndex({ items, selectedAtc, onSelectAtc }: GftAtcIndexProps) {
  const tree = useMemo(() => buildTree(items), [items]);
  const totalMedicationCount = useMemo(() => tree.reduce((sum, node) => sum + node.count, 0), [tree]);
  const defaultExpanded = useMemo(() => collectDefaultExpandedCodes(tree, selectedAtc), [tree, selectedAtc]);
  const [expandedCodes, setExpandedCodes] = useState<Set<string>>(new Set());
  const [isPanelOpen, setIsPanelOpen] = useState(Boolean(selectedAtc));

  useEffect(() => {
    if (selectedAtc) setIsPanelOpen(true);
  }, [selectedAtc]);

  const mergedExpanded = useMemo(() => {
    const merged = new Set(expandedCodes);
    defaultExpanded.forEach((code) => merged.add(code));
    return merged;
  }, [expandedCodes, defaultExpanded]);

  function toggleExpand(code: string) {
    setExpandedCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function renderNodes(nodes: AtcNode[]): ReactNode {
    return (
      <ul className="gft-atc-index__tree" role="tree">
        {nodes.map((node) => {
          const isActive = selectedAtc === node.code;
          const isAncestorOfActive = Boolean(selectedAtc) && selectedAtc !== node.code && selectedAtc.startsWith(node.code);
          const isExpanded = mergedExpanded.has(node.code);
          const hasChildren = node.children.length > 0;

          return (
            <li key={node.code} className="gft-atc-index__node" role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
              <div className="gft-atc-index__row">
                {hasChildren ? (
                  <button
                    type="button"
                    className="gft-atc-index__toggle"
                    aria-label={`${isExpanded ? 'Contraer' : 'Expandir'} ${node.code}`}
                    onClick={() => toggleExpand(node.code)}
                  >
                    {isExpanded ? '−' : '+'}
                  </button>
                ) : (
                  <span className="gft-atc-index__toggle-placeholder" aria-hidden="true" />
                )}
                <button
                  type="button"
                  className={`gft-atc-index__button${isActive ? ' gft-atc-index__button--active' : ''}${isAncestorOfActive ? ' gft-atc-index__button--parent-active' : ''}`}
                  aria-pressed={isActive}
                  onClick={() => onSelectAtc(node.code)}
                >
                  <span className="gft-atc-index__label-wrap">
                    <span className="gft-atc-index__level">{LEVEL_LABEL[node.level] ?? `L${node.level}`}</span>
                    <span className="gft-atc-index__label">{formatNodeLabel(node)}</span>
                  </span>
                  <span className="gft-atc-index__count">{node.count}</span>
                </button>
              </div>
              {hasChildren && isExpanded ? <div className="gft-atc-index__children">{renderNodes(node.children)}</div> : null}
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <section className="gft-atc-index" aria-labelledby="gft-atc-index-title">
      <div className="gft-atc-index__header">
        <div>
          <h2 className="gft-atc-index__title" id="gft-atc-index-title">Índice ATC</h2>
          <p className="gft-atc-index__subtitle">Navegación jerárquica por niveles L1-L5</p>
        </div>
        <button
          type="button"
          className="gft-atc-index__toggle"
          aria-expanded={isPanelOpen}
          aria-controls="gft-atc-index-panel"
          onClick={() => setIsPanelOpen((prev) => !prev)}
        >
          <span className="gft-atc-index__count" aria-label={`${totalMedicationCount} medicamentos en el índice ATC`}>{totalMedicationCount}</span>
          <span className="gft-atc-index__level">{isPanelOpen ? 'Ocultar' : 'Mostrar'}</span>
        </button>
      </div>

      {isPanelOpen ? (
        <div id="gft-atc-index-panel">
          <div className="gft-atc-index__actions">
            <button
              type="button"
              className={`gft-atc-index__button gft-atc-index__button--all${selectedAtc ? '' : ' gft-atc-index__button--active'}`}
              aria-pressed={!selectedAtc}
              onClick={() => onSelectAtc('')}
            >
              <span className="gft-atc-index__label-wrap">
                <span className="gft-atc-index__level">Filtro</span>
                <span className="gft-atc-index__label">Limpiar ATC (todos los grupos)</span>
              </span>
              <span className="gft-atc-index__count">{totalMedicationCount}</span>
            </button>
          </div>

          {tree.length > 0 ? renderNodes(tree) : <p className="gft-atc-index__empty">No hay grupos ATC disponibles en el índice global.</p>}
        </div>
      ) : null}
    </section>
  );
}
