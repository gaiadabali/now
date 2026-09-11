/**
 * Minimal typed client over engine-api's generated OpenAPI schema.
 *
 * This is intentionally not a full SDK -- E0.3 is skeleton/routing only, no
 * business endpoints exist yet (see ARCHITECTURE.md §16 / §19). Its purpose
 * is to prove the exported OpenAPI schema produces a *compiling*,
 * *type-safe* TypeScript client, and to give later waves (E3 onward) a
 * pattern to extend rather than a library to fight.
 */
import type { paths } from "./schema.js";

type Healthz = paths["/healthz"]["get"]["responses"][200]["content"]["application/json"];
type CityHealth =
  paths["/v1/{site}/health"]["get"]["responses"][200]["content"]["application/json"];

export class EngineApiClient {
  constructor(private readonly baseUrl: string) {}

  async healthz(): Promise<Healthz> {
    const res = await fetch(`${this.baseUrl}/healthz`);
    if (!res.ok) {
      throw new Error(`healthz failed: ${res.status}`);
    }
    return (await res.json()) as Healthz;
  }

  /** `site` is always a runtime value from the caller (a hostname lookup,
   * a config file, a CLI flag) -- never a literal baked into this client. */
  async cityHealth(site: string): Promise<CityHealth> {
    const res = await fetch(`${this.baseUrl}/v1/${encodeURIComponent(site)}/health`);
    if (!res.ok) {
      throw new Error(`city health failed for ${site}: ${res.status}`);
    }
    return (await res.json()) as CityHealth;
  }
}

export type { paths } from "./schema.js";
