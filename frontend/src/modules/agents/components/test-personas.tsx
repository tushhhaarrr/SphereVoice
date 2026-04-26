"use client";

import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

export interface TestPersona {
    id: string;
    label: string;
    description: string;
    variables: Record<string, string>;
}

const DEFAULT_PERSONAS: TestPersona[] = [
    {
        id: "new_lead",
        label: "New Lead",
        description: "First-time caller, no prior interaction",
        variables: {
            lead_name: "Priya Sharma",
            lead_email: "priya.sharma@example.com",
            lead_phone: "+919876543210",
            lead_company: "TechVentures India",
            deal_stage: "New",
        },
    },
    {
        id: "returning_customer",
        label: "Returning Customer",
        description: "Existing customer checking on their order",
        variables: {
            lead_name: "Rajesh Kumar",
            lead_email: "rajesh.k@example.com",
            lead_phone: "+919123456789",
            lead_company: "Kumar Industries",
            deal_stage: "Customer",
        },
    },
    {
        id: "hot_prospect",
        label: "Hot Prospect",
        description: "Highly interested lead ready to buy",
        variables: {
            lead_name: "Anita Desai",
            lead_email: "anita.d@example.com",
            lead_phone: "+918765432100",
            lead_company: "Desai Group",
            deal_stage: "Negotiation",
        },
    },
    {
        id: "unhappy_caller",
        label: "Unhappy Caller",
        description: "Frustrated customer with a complaint",
        variables: {
            lead_name: "Vikram Singh",
            lead_email: "vikram.s@example.com",
            lead_phone: "+917654321098",
            lead_company: "Singh Enterprises",
            deal_stage: "Support",
        },
    },
    {
        id: "enterprise",
        label: "Enterprise Decision Maker",
        description: "Senior buyer evaluating the product",
        variables: {
            lead_name: "Meera Patel",
            lead_email: "meera.patel@largecorp.com",
            lead_phone: "+916543210987",
            lead_company: "LargeCorp Solutions",
            deal_stage: "Evaluation",
        },
    },
];

interface TestPersonaSelectorProps {
    onSelect: (persona: TestPersona) => void;
    disabled?: boolean;
}

export function TestPersonaSelector({ onSelect, disabled }: TestPersonaSelectorProps) {
    return (
        <Select
            onValueChange={(id) => {
                const persona = DEFAULT_PERSONAS.find((p) => p.id === id);
                if (persona) onSelect(persona);
            }}
            disabled={disabled}
        >
            <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Load a test persona…" />
            </SelectTrigger>
            <SelectContent>
                {DEFAULT_PERSONAS.map((persona) => (
                    <SelectItem key={persona.id} value={persona.id}>
                        <div className="flex flex-col">
                            <span className="text-xs font-medium">{persona.label}</span>
                            <span className="text-[10px] text-muted-foreground">
                                {persona.description}
                            </span>
                        </div>
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
}
