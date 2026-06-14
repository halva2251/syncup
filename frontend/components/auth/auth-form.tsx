"use client";

import { useActionState, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorMessage } from "@/components/ui/error-message";
import { Loader2, X, Check } from "lucide-react";

type ValidationType = "email" | "password" | "displayName";

interface AuthField {
  name: string;
  label: string;
  type?: string;
  placeholder?: string;
  required?: boolean;
  autoComplete?: string;
  validation?: ValidationType;
  showValidationIcon?: boolean;
}

interface AuthFormProps {
  action: (formData: FormData) => Promise<{ error?: string }>;
  title: string;
  subtitle: string;
  fields: AuthField[];
  submitLabel: string;
  footer: ReactNode;
}

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const validators: Record<ValidationType, (value: string) => string | undefined> = {
  email: (value) => {
    if (!value.trim()) return "Email is required.";
    if (!emailRegex.test(value.trim())) return "Please enter a valid email address.";
    return undefined;
  },
  password: (value) => {
    if (!value) return "Password is required.";
    if (value.length < 8) return "Password must be at least 8 characters.";
    if (value.length > 128) return "Password must be 128 characters or less.";
    return undefined;
  },
  displayName: (value) => {
    if (!value.trim()) return "Display name is required.";
    if (value.trim().length > 100) return "Display name must be 100 characters or less.";
    return undefined;
  },
};

function getEmailStatus(value: string): "empty" | "invalid" | "valid" {
  if (!value) return "empty";
  return emailRegex.test(value.trim()) ? "valid" : "invalid";
}

function ValidationIcon({
  status,
}: {
  status: "empty" | "invalid" | "valid";
}) {
  if (status === "valid") {
    return (
      <Check
        className="h-5 w-5 text-[var(--color-success)]"
        strokeWidth={2.5}
      />
    );
  }
  if (status === "invalid") {
    return (
      <X className="h-5 w-5 text-[var(--color-danger)]" strokeWidth={2.5} />
    );
  }
  return null;
}

export function AuthForm({
  action,
  title,
  subtitle,
  fields,
  submitLabel,
  footer,
}: AuthFormProps) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.name, ""]))
  );
  const [touched, setTouched] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(fields.map((f) => [f.name, false]))
  );
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  const validateField = useCallback(
    (field: AuthField, value: string) => {
      if (field.required && !value.trim()) {
        return `${field.label} is required.`;
      }
      if (field.validation) {
        return validators[field.validation](value);
      }
      return undefined;
    },
    []
  );

  const [state, formAction, pending] = useActionState(
    async (_prevState: { error?: string } | null, formData: FormData) => {
      const newErrors: Record<string, string> = {};
      let hasError = false;

      for (const field of fields) {
        const value = (formData.get(field.name) as string) ?? "";
        const error = validateField(field, value);
        if (error) {
          newErrors[field.name] = error;
          hasError = true;
        }
      }

      setClientErrors(newErrors);
      setTouched(Object.fromEntries(fields.map((f) => [f.name, true])));

      if (hasError) {
        return { error: "Please fix the errors above." };
      }

      return await action(formData);
    },
    null
  );

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement>,
    field: AuthField
  ) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));

    const error = validateField(field, value);
    setClientErrors((prev) => {
      const next = { ...prev };
      if (error) {
        next[name] = error;
      } else {
        delete next[name];
      }
      return next;
    });
  };

  const handleBlur = (fieldName: string) => {
    setTouched((prev) => ({ ...prev, [fieldName]: true }));
  };

  const getFieldRightElement = (field: AuthField) => {
    if (!field.showValidationIcon) return null;

    if (field.validation === "email") {
      const status = getEmailStatus(values[field.name]);
      if (!touched[field.name] && status === "empty") return null;
      return <ValidationIcon status={status} />;
    }

    const value = values[field.name];
    if (!value) return null;

    const error = field.validation ? validators[field.validation](value) : undefined;
    if (error) {
      return (
        <X className="h-5 w-5 text-[var(--color-danger)]" strokeWidth={2.5} />
      );
    }
    return (
      <Check
        className="h-5 w-5 text-[var(--color-success)]"
        strokeWidth={2.5}
      />
    );
  };

  const getFieldError = (field: AuthField) => {
    if (!touched[field.name] && !clientErrors[field.name]) return undefined;
    return clientErrors[field.name];
  };

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-auth-card)] p-8 shadow-sm sm:p-10">
      <div className="mb-8">
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-[var(--color-text-primary)]">
          {title}
        </h1>
        <p className="mt-2 text-[15px] text-[var(--color-text-secondary)]">
          {subtitle}
        </p>
      </div>

      <form action={formAction} className="space-y-5">
        {state?.error && <ErrorMessage>{state.error}</ErrorMessage>}

        {fields.map((field) => (
          <Input
            key={field.name}
            name={field.name}
            label={field.label}
            type={field.type ?? "text"}
            placeholder={field.placeholder}
            required={field.required}
            autoComplete={field.autoComplete}
            value={values[field.name]}
            onChange={(e) => handleChange(e, field)}
            onBlur={() => handleBlur(field.name)}
            error={getFieldError(field)}
            rightElement={getFieldRightElement(field)}
          />
        ))}

        <Button
          type="submit"
          size="lg"
          className="mt-2 w-full"
          disabled={pending}
        >
          {pending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            submitLabel
          )}
        </Button>
      </form>

      <div className="mt-8 text-center text-sm text-[var(--color-text-secondary)]">
        {footer}
      </div>
    </div>
  );
}
