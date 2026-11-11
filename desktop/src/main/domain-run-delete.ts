export type DeleteDomainRunResult = {
  deleted_domain_run_id: string;
  deleted_domain_experiment: string | null;
  preserved_template: boolean;
};

export function readDeleteDomainRunId(params: unknown): string {
  if (params === null || typeof params !== "object" || Array.isArray(params)) {
    throw new Error("Parámetros de borrado inválidos.");
  }
  const value = params as Record<string, unknown>;
  if (
    Object.keys(value).length !== 1 ||
    typeof value.domain_run_id !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.domain_run_id)
  ) {
    throw new Error("El borrado requiere un UUID v4 canónico.");
  }
  return value.domain_run_id;
}

export function readDeleteDomainRunResult(
  result: unknown,
  requestedId: string,
): DeleteDomainRunResult {
  if (result === null || typeof result !== "object" || Array.isArray(result)) {
    throw new Error("Respuesta de borrado inválida.");
  }
  const value = result as Record<string, unknown>;
  if (
    Object.keys(value).length !== 3 ||
    value.deleted_domain_run_id !== requestedId ||
    (value.deleted_domain_experiment !== null &&
      (typeof value.deleted_domain_experiment !== "string" ||
        !/^[0-9a-f]{64}$/.test(value.deleted_domain_experiment))) ||
    typeof value.preserved_template !== "boolean"
  ) {
    throw new Error("La respuesta no coincide con el borrado solicitado.");
  }
  return value as DeleteDomainRunResult;
}
