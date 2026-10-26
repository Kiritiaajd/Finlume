import { CircleCheck } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { ApiStatusPanel } from "@/components/ApiStatus";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldError, Label, Select } from "@/components/ui/form-controls";
import { apiUrl, config } from "@/lib/config";
import { formatRatio } from "@/lib/format";
import { zodResolver } from "@/lib/forms/zod-resolver";
import {
  DEFAULT_PREFERENCES,
  LOCALE_OPTIONS,
  type Preferences,
  preferencesSchema,
} from "@/lib/preferences";
import { usePreferences } from "@/lib/preferences-context";

function PreferencesForm() {
  const { preferences, setPreferences } = usePreferences();
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isDirty },
  } = useForm<Preferences>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: preferences,
  });
  const preview = useWatch({ control });

  const onSubmit = (values: Preferences) => {
    setPreferences(values);
    reset(values);
    setSaved(true);
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      onChange={() => setSaved(false)}
      className="space-y-5"
      noValidate
    >
      <div className="grid gap-5 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="locale">Number and date format</Label>
          <Select id="locale" aria-invalid={errors.locale ? true : undefined} {...register("locale")}>
            {Object.entries(LOCALE_OPTIONS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          {errors.locale ? <FieldError>{errors.locale.message}</FieldError> : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="ratioDisplay">Show ratios as</Label>
          <Select id="ratioDisplay" {...register("ratioDisplay")}>
            <option value="percent">Percentages</option>
            <option value="decimal">Decimals</option>
          </Select>
          {errors.ratioDisplay ? <FieldError>{errors.ratioDisplay.message}</FieldError> : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="theme">Theme</Label>
          <Select id="theme" {...register("theme")}>
            <option value="system">Match system</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </Select>
          {errors.theme ? <FieldError>{errors.theme.message}</FieldError> : null}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Preview: a ratio of 0.429962 displays as{" "}
        <span className="font-medium text-foreground tabular-nums">
          {formatRatio(
            "0.429962",
            preview.locale ?? DEFAULT_PREFERENCES.locale,
            preview.ratioDisplay ?? DEFAULT_PREFERENCES.ratioDisplay,
          )}
        </span>
        .
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!isDirty}>
          Save preferences
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            reset(DEFAULT_PREFERENCES, { keepDefaultValues: true });
            setSaved(false);
          }}
        >
          Reset to defaults
        </Button>
        {saved ? (
          <p role="status" className="flex items-center gap-1.5 text-sm text-success">
            <CircleCheck aria-hidden="true" className="size-4" />
            Saved in this browser
          </p>
        ) : null}
      </div>
    </form>
  );
}

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Display preferences and the connection to the Finlume backend."
      />

      <Card>
        <CardHeader>
          <CardTitle>Display preferences</CardTitle>
          <CardDescription>
            Stored only in this browser. There are no accounts yet, so nothing is saved on the
            server.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PreferencesForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API connection</CardTitle>
          <CardDescription>
            Requests go to{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">{apiUrl("/")}</code>
            {config.apiBaseUrl
              ? " (configured with VITE_API_BASE_URL)."
              : " on this site's own origin, forwarded to Django by the development proxy or the production reverse proxy."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ApiStatusPanel />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>About</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-muted-foreground">
          <p>Finlume web client v{config.appVersion} (pre-release). Open source under the MIT License.</p>
          <p>
            Sign-in, workspaces and account settings are not implemented yet. This client does not
            simulate them.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
