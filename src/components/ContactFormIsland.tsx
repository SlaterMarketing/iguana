"use client";

import React from "react";
import type { KintanaFormField } from "@kintana/sdk";
import { KintanaProvider, useKintanaSubmit } from "@kintana/sdk/react";

import { EmbedFormField } from "./form/EmbedFormField";

const CONTACT_FORM_FIELDS: KintanaFormField[] = [
  { id: "firstName", type: "text", label: "First name", required: true },
  { id: "lastName", type: "text", label: "Last name", required: true },
  { id: "email", type: "email", label: "Email", required: true },
  { id: "phone", type: "phone", label: "Phone", required: false },
  { id: "subject", type: "text", label: "Subject", required: false },
  { id: "message", type: "textarea", label: "Message", required: true },
];

function collectFormValues(form: HTMLFormElement, fields: KintanaFormField[]): Record<string, string> {
  const fd = new FormData(form);
  const values: Record<string, string> = {};

  for (const field of fields) {
    if (field.type === "boolean") {
      const el = form.elements.namedItem(field.id);
      values[field.id] =
        el instanceof HTMLInputElement && el.type === "checkbox" && el.checked ? "true" : "false";
      continue;
    }

    if (field.type === "multiselect") {
      values[field.id] = fd.getAll(field.id).map(String).join(",");
      continue;
    }

    const raw = fd.get(field.id);
    values[field.id] = typeof raw === "string" ? raw : "";
  }

  return values;
}

function applyPrefills(form: HTMLFormElement, fields: KintanaFormField[], prefills: Record<string, string>) {
  for (const field of fields) {
    const val = prefills[field.id];
    if (!val) continue;
    const el = form.elements.namedItem(field.id);
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
      el.value = val;
    }
    if (el instanceof HTMLInputElement && el.type === "checkbox") {
      el.checked = val === "true" || val === "1";
    }
    if (el instanceof HTMLSelectElement && !el.multiple) {
      el.value = val;
    }
  }
}

function StyledFormInner({
  endpointSlug,
  prefills,
  hideHeading = false,
  title = "Get in touch",
}: {
  endpointSlug: string;
  prefills: Record<string, string>;
  hideHeading?: boolean;
  title?: string;
}) {
  const { submit, submitting, message, error } = useKintanaSubmit(endpointSlug);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = collectFormValues(e.currentTarget, CONTACT_FORM_FIELDS);
    const email = values.email?.trim();
    if (!email) return;

    const { email: _email, phone, ...fields } = values;

    await submit({
      email,
      phone: phone?.trim() || undefined,
      fields,
    });

    e.currentTarget.reset();
    applyPrefills(e.currentTarget, CONTACT_FORM_FIELDS, prefills);
  }

  const defaults = prefills ?? {};

  return (
    <div className="max-w-xl">
      {hideHeading ? null : (
        <h2
          className="font-display text-2xl tracking-tight text-neutral-950"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {title}
        </h2>
      )}

      <form className={hideHeading ? "grid gap-5" : "mt-8 grid gap-5"} onSubmit={(e) => void handleSubmit(e)}>
        {CONTACT_FORM_FIELDS.map((field) => (
          <div key={field.id} className="grid gap-2 text-sm font-medium text-neutral-900">
            {field.type === "boolean" ? (
              <span>
                {field.label}
                {field.required ? " *" : null}
              </span>
            ) : (
              <label htmlFor={field.id}>
                {field.label}
                {field.required ? " *" : null}
              </label>
            )}
            <EmbedFormField field={field} defaults={defaults} disabled={submitting} />
          </div>
        ))}
        <button
          disabled={submitting}
          type="submit"
          className="rounded-full bg-neutral-950 px-12 py-[0.9rem] text-xs font-semibold uppercase tracking-[0.35em] text-white shadow-lg shadow-neutral-900/35 transition hover:opacity-[0.95] disabled:bg-neutral-500"
        >
          {submitting ? "Sending…" : "Send message"}
        </button>
      </form>
      {error ? <p className="mt-6 text-red-700">{error}</p> : null}
      {message ? <p className="mt-6 text-neutral-700">{message}</p> : null}
    </div>
  );
}

export function ContactFormIsland({
  apiKey,
  baseUrl,
  endpointSlug,
  prefills,
  hideHeading = false,
  title,
}: {
  apiKey: string;
  baseUrl: string;
  endpointSlug: string;
  prefills?: Record<string, string>;
  hideHeading?: boolean;
  title?: string;
}) {
  const merged = React.useMemo(() => prefills ?? {}, [prefills]);

  return (
    <KintanaProvider apiKey={apiKey} baseUrl={baseUrl}>
      <StyledFormInner
        endpointSlug={endpointSlug}
        prefills={merged}
        hideHeading={hideHeading}
        title={title}
      />
    </KintanaProvider>
  );
}
