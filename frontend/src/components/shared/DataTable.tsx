import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { itemFadeUp, staggerContainer } from "../../lib/motion";

export interface DataTableColumn<T> {
  header: string;
  accessor: (row: T) => ReactNode;
  className?: string;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  emptyMessage = "No data yet.",
  onRowClick,
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/50">
            {columns.map((column) => (
              <th
                key={column.header}
                className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 ${column.className ?? ""}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <motion.tbody
          className="divide-y divide-slate-100 dark:divide-slate-800"
          variants={staggerContainer(0.03)}
          initial="hidden"
          animate="show"
        >
          {data.map((row) => (
            <motion.tr
              key={keyExtractor(row)}
              variants={itemFadeUp}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`group transition-colors duration-150 hover:bg-slate-50 dark:hover:bg-slate-800/50 ${onRowClick ? "cursor-pointer" : ""}`}
            >
              {columns.map((column) => (
                <td key={column.header} className={`px-4 py-3 text-slate-700 dark:text-slate-300 ${column.className ?? ""}`}>
                  {column.accessor(row)}
                </td>
              ))}
            </motion.tr>
          ))}
        </motion.tbody>
      </table>
    </div>
  );
}
