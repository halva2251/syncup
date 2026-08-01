"use client";

import { useEffect, useState } from "react";
import { ToastContainer } from "./toast";

interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
  duration?: number;
}

export function ToastProvider() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const handleToast = (event: Event) => {
      const customEvent = event as CustomEvent<Omit<Toast, "id"> & { id: string }>;
      const { type, message, duration, id } = customEvent.detail;

      setToasts((prev) => [...prev, { type, message, duration, id }]);
    };

    window.addEventListener("toast", handleToast);
    return () => window.removeEventListener("toast", handleToast);
  }, []);

  const handleDismiss = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return <ToastContainer toasts={toasts} onDismiss={handleDismiss} />;
}