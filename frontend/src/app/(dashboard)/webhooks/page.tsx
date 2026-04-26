import { WebhookManager } from "@/modules/webhooks";

export default function WebhooksPage() {
    return (
        <div className="p-6 lg:p-8">
            <WebhookManager />
        </div>
    );
}
