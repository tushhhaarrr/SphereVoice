import { Suspense } from "react";
import { IntegrationsPage } from "@/modules/integrations";

export default function TenantIntegrationsPage() {
  return (
    <div className="p-6 lg:p-8">
      <Suspense>
        <IntegrationsPage />
      </Suspense>
    </div>
  );
}
