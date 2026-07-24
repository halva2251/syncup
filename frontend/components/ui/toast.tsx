"use client";

import { useEffect, useState } from "react";
import { Check, AlertCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

function Toast({ toast, onDismiss }: ToastProps) {
  const [isLeaving, setIsLeaving] = useState(false);

  useEffect(() => {
    const duration = toast.duration || 3000;
    const timer = setTimeout(() => {
      setIsLeaving(true);
      setTimeout(() => onDismiss(toast.id), 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  const icons = {
    success: <Check className="h-4 w-4" />,
    error: <AlertCircle className="h-4 w-4" />,
    info: <Info className="h-4 w-4" />,
  };

  const colors = {
    success: "border-[var(--color-border)] bg-[var(--color-bg-card)]",
    error: "border-[var(--color-border)] bg-[var(--color-bg-card)]",
    info: "border-[var(--color-border)] bg-[var(--color-bg-card)]",
  };

  const iconColors = {
    success: "text-[var(--color-success)]",
    error: "text-[var(--color-danger)]",
    info: "text-[var(--color-accent)]",
  };

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border ${colors[toast.type]} px-4 py-3 shadow-lg transition-all duration-300 ${
        isLeaving ? "translate-x-full opacity-0" : "translate-x-0 opacity-100"
      }`}
    >
      <div className={`${iconColors[toast.type]} shrink-0`}>
        {icons[toast.type]}
      </div>
      <p className="flex-1 text-sm text-[var(--color-text-primary)]">
        {toast.message}
      </p>
      <button
        onClick={() => {
          setIsLeaving(true);
          setTimeout(() => onDismiss(toast.id), 300);
        }}
        className="shrink-0 rounded-md p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-text-primary)]"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

let toastCounter = 0;
export function toast(type: ToastType, message: string, duration?: number): string {
  const id = `toast-${++toastCounter}`;
  window.dispatchEvent(
    new CustomEvent("toast", { detail: { type, message, duration, id } })
  );
  return id;
}

toast.success = (message: string, duration?: number) => toast("success", message, duration);
toast.error = (message: string, duration?: number) => toast("error", message, duration);
toast.info = (message: string, duration?: number) => toast("info", message, duration);