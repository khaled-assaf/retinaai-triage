import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

const ToastContext = createContext<{ push: (message: string, type?: ToastType) => void } | null>(
  null,
);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const STYLES: Record<ToastType, { ring: string; icon: ReactNode }> = {
  success: { ring: "ring-green-200", icon: <CheckCircle2 className="size-4.5 text-green-500" /> },
  error: { ring: "ring-red-200", icon: <XCircle className="size-4.5 text-red-500" /> },
  info: { ring: "ring-slate-200", icon: <Info className="size-4.5 text-slate-400" /> },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = ++nextId.current;
      setToasts((current) => [...current, { id, message, type }]);
      setTimeout(() => dismiss(id), 4500);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed right-5 bottom-5 z-50 flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto flex items-start gap-2.5 rounded-xl bg-white p-3.5 shadow-lg ring-1 ${STYLES[t.type].ring}`}
          >
            {STYLES[t.type].icon}
            <p className="flex-1 text-sm leading-snug text-slate-700">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              aria-label="Dismiss"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
