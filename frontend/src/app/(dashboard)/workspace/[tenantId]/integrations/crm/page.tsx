import { Suspense } from "react";
import { CrmContactsPage } from "@/modules/integrations/components/crm-contacts-page";

export default function TenantCrmContactsPage() {
    return (
        <div className="p-6 lg:p-8">
            <Suspense>
                <CrmContactsPage />
            </Suspense>
        </div>
    );
}
