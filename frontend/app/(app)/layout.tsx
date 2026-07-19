import { ToastProvider } from "@/components/ui/toast-provider";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <ToastProvider />
    </>
  );
}