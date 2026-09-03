import type { ReactNode } from 'react';
import './RankedTable.css';

export interface RankedTableColumn<T> {
  key: string;
  header: string;
  align?: 'left' | 'right' | 'center';
  width?: string;
  render: (row: T) => ReactNode;
}

export interface RankedTableFooterCell {
  content: ReactNode;
  align?: 'left' | 'right' | 'center';
  colSpan?: number;
}

interface RankedTableProps<T> {
  columns: RankedTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string | number;
  footer?: RankedTableFooterCell[];
  /** Makes rows clickable — used by the issue tables to cross-filter the
   *  dashboard by category. Omit for a plain, non-interactive table. */
  onRowClick?: (row: T) => void;
  /** Which row is currently the dashboard's selection, if any. */
  isRowActive?: (row: T) => boolean;
  /** Tooltip per row, so each table can word its own interaction. */
  rowTitle?: (row: T) => string;
}

export function RankedTable<T>({
  columns,
  rows,
  getRowKey,
  footer,
  onRowClick,
  isRowActive,
  rowTitle,
}: RankedTableProps<T>) {
  return (
    <div className="ranked-table__scroll">
      <table className="ranked-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={{ width: col.width, textAlign: col.align ?? 'left' }}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getRowKey(row)}
              className={[
                onRowClick ? 'ranked-table__row--clickable' : '',
                isRowActive?.(row) ? 'ranked-table__row--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              title={rowTitle?.(row)}
            >
              {columns.map((col) => (
                <td key={col.key} style={{ textAlign: col.align ?? 'left' }}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {footer && (
          <tfoot>
            <tr>
              {footer.map((cell, index) => (
                <td
                  key={`footer-cell-${index}`}
                  colSpan={cell.colSpan}
                  className={
                    cell.colSpan && cell.colSpan > 1
                      ? 'ranked-table__total-label'
                      : 'ranked-table__total-value'
                  }
                  style={{ textAlign: cell.align ?? 'left' }}
                >
                  {cell.content}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
