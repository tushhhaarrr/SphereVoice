"use client";

import {
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  ListOrdered,
  Phone,
  PhoneCall,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { CampaignStats } from "../../types";

interface CampaignStatsCardsProps {
  stats: CampaignStats | undefined;
  isLoading: boolean;
}

interface StatCardDef {
  label: string;
  key: keyof CampaignStats;
  icon: React.ElementType;
  color: string;
}

const STAT_CARDS: StatCardDef[] = [
  { label: "Total Contacts", key: "total_contacts", icon: Users, color: "text-slate-600" },
  { label: "Completed", key: "completed_calls", icon: CheckCircle2, color: "text-green-600" },
  { label: "Successful", key: "successful_calls", icon: Phone, color: "text-emerald-600" },
  { label: "Failed", key: "failed_calls", icon: XCircle, color: "text-red-600" },
  { label: "Pending", key: "pending_count", icon: Clock, color: "text-yellow-600" },
  { label: "Queued", key: "queued_count", icon: ListOrdered, color: "text-blue-600" },
  { label: "Calling", key: "calling_count", icon: PhoneCall, color: "text-indigo-600" },
];

export function CampaignStatsCards({ stats, isLoading }: CampaignStatsCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
      {STAT_CARDS.map((card) => {
        const Icon = card.icon;
        return (
          <Card key={card.key}>
            <CardContent className="flex flex-col gap-1 p-4">
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${card.color}`} />
                <span className="text-xs font-medium text-muted-foreground">
                  {card.label}
                </span>
              </div>
              <p className="text-2xl font-bold tabular-nums">
                {isLoading ? "—" : (stats?.[card.key] ?? 0)}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
