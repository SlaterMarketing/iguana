"use client";

import React, { useEffect, useState } from "react";
import { KintanaProvider, useKintana } from "@kintana/sdk/react";

import type { KintanaClient, KintanaPublicFormSchema } from "@kintana/sdk";

async function buildSubmitValues(
  client: KintanaClient,
  form: HTMLFormElement,
  schema: KintanaPublicFormSchema,
): Promise<Record<string, string>> {
  const fd = new FormData(form);
  const values: Record<string, string> = {};

  for (const field of schema.fields) {
    if (field.type === "file") {
      const input = form.elements.namedItem(field.id);
      if (!(input instanceof HTMLInputElement) || input.type !== "file") {
        values[field.id] = "";
        continue;
      }
      const picked = input.files?.[0];
      if (!picked) {
        if (field.required) throw new Error(`${field.label} is required`);
        values[field.id] = "";
        continue;
      }
      const err = validateFileField(field, picked);
      if (err) throw new Error(err);
      const uploaded = await client.uploadEmbedFormFile(schema.id, field.id, picked);
      if (!uploaded.ok || !uploaded.url) throw new Error(uploaded.error ?? "Upload failed");
      values[field.id] = uploaded.url;
      continue;
    }

    if (field.type === "boolean") {
      const el = form.elements.namedItem(field.id);
      values[field.id] = el instanceof HTMLInputElement && el.type === "checkbox" && el.checked ? "true" : "false";
      continue;
    }

    if (field.type === "multiselect") {
      const all = fd.getAll(field.id);
      values[field.id] = all.map(String).join(",");
      continue;
    }

    const raw = fd.get(field.id);
    values[field.id] = typeof raw === "string" ? raw : "";
  }

  return values;
}

function StyledFormInner({
  formId,
  prefills,
  hideHeading = false,
}: {
  formId: string;
  prefills: Record<string, string>;
  hideHeading?: boolean;
}) {
  const client = useKintana();
  const [schema, setSchema] = useState<KintanaPublicFormSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    client
      .getFormSchema(formId, { cache: "force-cache" })
      .then((s) => {
        if (!alive) return;
        setSchema(s);
      })
      .catch(() => alive && setMessage("We could not load this form yet."))
      .finally(() => alive && setLoading(false));

    return () => {
      alive = false;
    };
  }, [client, formId]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!schema) return;
    setSubmitting(true);
    setMessage(null);

    try {
      const values = await buildSubmitValues(client, e.currentTarget, schema);
      const result = await client.submitForm(schema.id, values);
      if (result.redirectUrl) {
        window.location.assign(result.redirectUrl);
        return;
      }
      if (result.ok !== true) {
        setMessage("Something went sideways—try WhatsApp?");
        return;
      }
      setMessage(result.successMessage ?? "Got it—we will reply shortly.");
      e.currentTarget.reset();
      if (prefills) {
        for (const field of schema.fields) {
          const val = prefills[field.id];
          if (!val) continue;
          const el = e.currentTarget.elements.namedItem(field.id);
          if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
            el.value = val;
          }
          if (el instanceof HTMLInputElement && el.type === "checkbox") {
            el.checked = val === "true" || val === "1";
          }
          if (el instanceof HTMLSelectElement && !el.multiple) el.value = val;
        }
      }
    } catch (submitErr) {
      setMessage(submitErr instanceof Error ? submitErr.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const defaults = prefills ?? {};

  if (loading)
    return <p className="rounded-3xl bg-neutral-100 px-6 py-4 text-neutral-700">Loading form…</p>;
  if (!schema)
    return <p className="rounded-3xl border border-neutral-300 px-6 py-4 text-neutral-700">{message}</p>;

  return (
    <div className="max-w-xl">
      {hideHeading ? null : (
        <h2 className="font-display text-2xl tracking-tight text-neutral-950" style={{ fontFamily: "var(--font-display)" }}>
          {schema.title}
        </h2>
      )}

      <form className={hideHeading ? "grid gap-5" : "mt-8 grid gap-5"} onSubmit={(e) => void submit(e)}>
        {schema.fields.map((field) => (
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
      {message ? <p className="mt-6 text-neutral-700">{message}</p> : null}
    </div>
  );
}

export function ContactFormIsland({
  apiKey,
  baseUrl,
  formId,
  prefills,
  hideHeading = false,
}: {
  apiKey: string;
  baseUrl: string;
  formId: string;
  prefills?: Record<string, string>;
  hideHeading?: boolean;
}) {
  const merged = React.useMemo(() => prefills ?? {}, [prefills]);

  return (
    <KintanaProvider apiKey={apiKey} baseUrl={baseUrl}>
      <StyledFormInner formId={formId} prefills={merged} hideHeading={hideHeading} />
    </KintanaProvider>
  );
}
