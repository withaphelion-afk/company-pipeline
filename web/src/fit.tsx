import { RefObject, useEffect, useRef, useState } from "react";
import { BTN_QUIET } from "./design";

/** How many fixed-height rows fit in the element the ref is attached to (it must have a definite height, e.g. flex-1 min-h-0). */
export function useFitRows(rowH: number, headH = 40, min = 3): [RefObject<HTMLDivElement>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [rows, setRows] = useState(8);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const calc = () => setRows(Math.max(min, Math.floor((el.clientHeight - headH) / rowH)));
    calc();
    const ro = new ResizeObserver(calc);
    ro.observe(el);
    return () => ro.disconnect();
  }, [rowH, headH, min]);
  return [ref, rows];
}

export function Pager({ page, total, size, onPage }: { page: number; total: number; size: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / Math.max(1, size)));
  return (
    <div className="mt-2 flex shrink-0 items-center gap-3 text-sm text-mist-500">
      <button className={`${BTN_QUIET} !px-3 !py-1`} disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</button>
      <span>Page {Math.min(page, pages)} of {pages} · {total} total · {size} per page</span>
      <button className={`${BTN_QUIET} !px-3 !py-1`} disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
    </div>
  );
}

export function useSort(initial: string, initialOrder: "asc" | "desc" = "desc"): [string, "asc" | "desc", (k: string, firstOrder?: "asc" | "desc") => void] {
  const [sort, setSort] = useState(initial);
  const [order, setOrder] = useState<"asc" | "desc">(initialOrder);
  const toggle = (k: string, firstOrder: "asc" | "desc" = "asc") => {
    if (k === sort) setOrder(order === "asc" ? "desc" : "asc");
    else { setSort(k); setOrder(firstOrder); }
  };
  return [sort, order, toggle];
}

export function SortTh({ label, k, sort, order, onSort, className = "", first = "asc" }: {
  label: string; k: string; sort: string; order: string; onSort: (k: string, first?: "asc" | "desc") => void; className?: string; first?: "asc" | "desc";
}) {
  return (
    <th className={`${className} cursor-pointer select-none hover:text-mist-50`} onClick={() => onSort(k, first)} aria-sort={sort === k ? (order === "asc" ? "ascending" : "descending") : "none"}>
      {label}{sort === k ? (order === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );
}

/** Wrapper for a page whose main card should fill the available height. */
export const FILL = "flex min-h-0 flex-1 flex-col";
