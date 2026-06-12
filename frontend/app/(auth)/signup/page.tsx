import Link from "next/link";
import { AuthForm } from "@/components/auth/auth-form";
import { signup } from "@/lib/auth";

export default function SignupPage() {
  return (
    <AuthForm
      action={signup}
      title="Create your account"
      subtitle="Start finding people who share your actual taste."
      fields={[
        {
          name: "display_name",
          label: "Display name",
          type: "text",
          placeholder: "alex",
          required: true,
          autoComplete: "username",
          validate: (value) =>
            value.trim().length > 100
              ? "Display name must be 100 characters or less."
              : undefined,
        },
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
          autoComplete: "new-password",
          showValidationIcon: "password",
          validate: (value) =>
            value.length < 8
              ? "Password must be at least 8 characters."
              : value.length > 128
                ? "Password must be 128 characters or less."
                : undefined,
        },
      ]}
      submitLabel="Create account"
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-[var(--color-accent)] hover:text-[var(--color-accent-hover)]"
          >
            Sign in
          </Link>
        </>
      }
    />
  );
}
