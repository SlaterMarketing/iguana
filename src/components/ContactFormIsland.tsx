"use client";

import React from "react";
import type { KintanaFormField } from "@kintana/sdk";
import { KintanaProvider, useKintanaSubmit } from "@kintana/sdk/react";

import { t, type Locale } from "../i18n/ui";
import { EmbedFormField } from "./form/EmbedFormField";

function contactFormFields(locale: Locale): KintanaFormField[] {
  return [
    { id: "firstName", type: "text", label: t(locale, "ui.contactForm.firstName"), required: true },
    { id: "lastName", type: "text", label: t(locale, "ui.contactForm.lastName"), required: true },
    { id: "email", type: "email", label: t(locale, "ui.contactForm.email"), required: true },
    { id: "phone", type: "phone", label: t(locale, "ui.contactForm.phone"), required: false },
    { id: "subject", type: "text", label: t(locale, "ui.contactForm.subject"), required: false },
    { id: "message", type: "textarea", label: t(locale, "ui.contactForm.message"), required: true },
  ];
}

/** Must match catalog/spam.py HONEYPOT_FIELD. Hidden, never focusable, never announced. */
const HONEYPOT_FIELD = "company_website";

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

  // The honeypot is not a declared field, so it has to be read by name. A browser leaves it empty; a bot that
  // fills every input it finds does not, and the backend drops the submission without telling it why.
  const trap = fd.get(HONEYPOT_FIELD);
  values[HONEYPOT_FIELD] = typeof trap === "string" ? trap : "";

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
  title,
  locale,
}: {
  endpointSlug: string;
  prefills: Record<string, string>;
  hideHeading?: boolean;
  title?: string;
  locale: Locale;
}) {
  const { submit, submitting, message, error } = useKintanaSubmit(endpointSlug);
  const fieldsForLocale = React.useMemo(() => contactFormFields(locale), [locale]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const values = collectFormValues(form, fieldsForLocale);
    const email = values.email?.trim();
    if (!email) return;

    const { email: _email, phone, ...fields } = values;

    await submit({
      email,
      phone: phone?.trim() || undefined,
      fields,
    });

    form.reset();
    applyPrefills(form, fieldsForLocale, prefills);
  }

  const defaults = prefills ?? {};

  return (
    <div className="mx-auto w-full max-w-xl text-left">
      {hideHeading ? null : (
        <h2
          className="text-center font-display text-2xl tracking-tight text-neutral-950"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {title ?? t(locale, "ui.contactForm.title")}
        </h2>
      )}

      <form className={hideHeading ? "grid gap-5" : "mt-8 grid gap-5"} onSubmit={(e) => void handleSubmit(e)}>
        <div aria-hidden="true" className="absolute left-[-9999px] h-px w-px overflow-hidden">
          <label htmlFor={HONEYPOT_FIELD}>Leave this field empty</label>
          <input id={HONEYPOT_FIELD} name={HONEYPOT_FIELD} type="text" tabIndex={-1} autoComplete="off" />
        </div>
        {fieldsForLocale.map((field) => (
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
            <EmbedFormField field={field} defaults={defaults} disabled={submitting} locale={locale} />
          </div>
        ))}
        <button
          disabled={submitting}
          type="submit"
          className="rounded-full bg-neutral-950 px-12 py-[0.9rem] text-xs font-semibold uppercase tracking-[0.35em] text-white shadow-lg shadow-neutral-900/35 transition hover:opacity-[0.95] disabled:bg-neutral-500"
        >
          {submitting ? t(locale, "ui.contactForm.sending") : t(locale, "ui.contactForm.sendMessage")}
        </button>
      </form>
      {/* The SDK returns the endpoint's stored success message and its own error text, both English, so show the
          site's translated copy instead. */}
      {error ? <p className="mt-6 text-red-700">{t(locale, "ui.contactForm.failed")}</p> : null}
      {message ? <p className="mt-6 text-neutral-700">{t(locale, "ui.contactForm.sent")}</p> : null}
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
  locale = "en",
}: {
  apiKey: string;
  baseUrl: string;
  endpointSlug: string;
  prefills?: Record<string, string>;
  hideHeading?: boolean;
  title?: string;
  locale?: Locale;
}) {
  const merged = React.useMemo(() => prefills ?? {}, [prefills]);

  return (
    <KintanaProvider apiKey={apiKey} baseUrl={baseUrl}>
      <StyledFormInner
        endpointSlug={endpointSlug}
        prefills={merged}
        hideHeading={hideHeading}
        title={title}
        locale={locale}
      />
    </KintanaProvider>
  );
}
