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
          name: "email",
          label: "Email",
          type: "email",
          placeholder: "you@example.com",
          required: true,
          autoComplete: "email",
          validation: "email",
          showValidationIcon: true,
        },
        {
          name: "display_name",
          label: "Display name",
          type: "text",
          placeholder: "alex",
          required: true,
          autoComplete: "username",
        },
        {
          name: "password",
          label: "Password",
          type: "password",
          placeholder: "••••••••",
          required: true,
          autoComplete: "new-password",
          validation: "password",
          showValidationIcon: true,
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
