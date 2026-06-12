import Link from "next/link";
import { AuthForm } from "@/components/auth/auth-form";
import { login } from "@/lib/auth";

export default function LoginPage() {
  return (
    <AuthForm
      action={login}
      title="Welcome back"
      subtitle="Sign in to find your people through taste."
      fields={[
        {
          name: "email",
          label: "Email",
          type: "email",
          placeholder: "you@example.com",
          required: true,
          autoComplete: "email",
          showValidationIcon: "email",
        },
        {
          name: "password",
          label: "Password",
          type: "password",
          placeholder: "••••••••",
          required: true,
          autoComplete: "current-password",
        },
      ]}
      submitLabel="Sign in"
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link
            href="/signup"
            className="font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
          >
            Sign up
          </Link>
        </>
      }
    />
  );
}
