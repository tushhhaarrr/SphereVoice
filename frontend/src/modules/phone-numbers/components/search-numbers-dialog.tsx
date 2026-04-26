/**
 * Search & Purchase Phone Numbers Dialog.
 *
 * Searches numbers from configured telephony providers, shows results
 * with provider badges, and confirms purchase via a provider-specific dialog.
 */

"use client";

import { useState } from "react";
import { AlertCircle, Loader2, Phone, Search, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";

import { useProvidersList } from "@/modules/providers/hooks/use-providers";
import { getProviderLabel } from "@/modules/providers/lib/catalog";

import type { AvailableNumber } from "../types";
import { usePurchaseNumber, useSearchAvailableNumbers } from "../hooks/use-phone-numbers";

interface SearchNumbersDialogProps {
  tenantId?: string;
  tenantName?: string;
  trigger?: React.ReactNode;
}

const COUNTRIES = [
  { code: "US", label: "United States" },
  { code: "GB", label: "United Kingdom" },
  { code: "CA", label: "Canada" },
  { code: "AU", label: "Australia" },
  { code: "IN", label: "India" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "SG", label: "Singapore" },
  { code: "AE", label: "UAE" },
  { code: "JP", label: "Japan" },
  { code: "BR", label: "Brazil" },
  { code: "MX", label: "Mexico" },
  { code: "ZA", label: "South Africa" },
  { code: "NG", label: "Nigeria" },
  { code: "KE", label: "Kenya" },
];

export function SearchNumbersDialog({
  tenantId,
  tenantName,
  trigger,
}: SearchNumbersDialogProps) {
  const [open, setOpen] = useState(false);
  const [country, setCountry] = useState("US");
  const [areaCode, setAreaCode] = useState("");
  const [contains, setContains] = useState("");
  const [provider, setProvider] = useState("");
  const [searchEnabled, setSearchEnabled] = useState(false);

  // Fetch telephony providers configured for this tenant
  const { data: providersData, isLoading: isLoadingProviders } = useProvidersList({
    category: "telephony",
    tenantId: tenantId || undefined,
  });
  const telephonyProviders = (providersData?.providers ?? []).filter((p) => p.is_active);

  // Auto-select first provider when loaded
  const effectiveProvider =
    provider ||
    (telephonyProviders.length > 0 ? telephonyProviders[0].provider_name : "");

  const {
    data: searchResults,
    isLoading: isSearching,
    refetch,
  } = useSearchAvailableNumbers(
    {
      country,
      area_code: areaCode || undefined,
      contains: contains || undefined,
      limit: 10,
      provider: effectiveProvider,
    },
    searchEnabled && !!effectiveProvider,
  );

  // Purchase confirmation state
  const [purchaseTarget, setPurchaseTarget] = useState<AvailableNumber | null>(null);
  const purchaseMutation = usePurchaseNumber();

  function handleSearch() {
    if (!effectiveProvider) return;
    setSearchEnabled(true);
    refetch();
  }

  function handlePurchaseClick(number: AvailableNumber) {
    setPurchaseTarget(number);
  }

  async function handleConfirmPurchase() {
    if (!purchaseTarget) return;
    await purchaseMutation.mutateAsync({
      phone_number: purchaseTarget.phone_number,
      tenant_id: tenantId,
      provider_name: purchaseTarget.provider,
    });
    setPurchaseTarget(null);
    setOpen(false);
    setSearchEnabled(false);
  }

  return (
    <>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          {trigger ?? (
            <Button>
              <Phone className="mr-2 h-4 w-4" />
              Buy Number
            </Button>
          )}
        </DialogTrigger>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Search Available Phone Numbers</DialogTitle>
            <DialogDescription>
              {tenantId
                ? `Search for numbers to assign to ${tenantName ?? "this workspace"}.`
                : "Search for available phone numbers by country and area code. Purchase is enabled from tenant workspaces."}
            </DialogDescription>
          </DialogHeader>

          {/* No telephony providers configured */}
          {!isLoadingProviders && telephonyProviders.length === 0 && (
            <div className="flex items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-900 dark:bg-yellow-950">
              <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              <div className="text-sm">
                <p className="font-medium text-yellow-800 dark:text-yellow-300">
                  No telephony providers configured
                </p>
                <p className="text-yellow-700 dark:text-yellow-400">
                  Add a telephony provider (e.g. Plivo, Twilio) in the Providers
                  section to search and purchase phone numbers.
                </p>
              </div>
            </div>
          )}

          {/* Search Form */}
          {(isLoadingProviders || telephonyProviders.length > 0) && (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div className="space-y-2">
                  <Label>Provider</Label>
                  {isLoadingProviders ? (
                    <div className="flex h-10 items-center rounded-md border px-3">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <Select
                      value={effectiveProvider}
                      onValueChange={(v) => {
                        setProvider(v);
                        setSearchEnabled(false);
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        {telephonyProviders.map((p) => (
                          <SelectItem key={p.id} value={p.provider_name}>
                            {getProviderLabel(p.provider_name)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Country</Label>
                  <Select value={country} onValueChange={setCountry}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {COUNTRIES.map((c) => (
                        <SelectItem key={c.code} value={c.code}>
                          {c.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Area Code</Label>
                  <Input
                    placeholder="e.g. 415"
                    value={areaCode}
                    onChange={(e) => setAreaCode(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Contains</Label>
                  <Input
                    placeholder="e.g. 555"
                    value={contains}
                    onChange={(e) => setContains(e.target.value)}
                  />
                </div>
              </div>

              <Button
                onClick={handleSearch}
                disabled={isSearching || !effectiveProvider}
                className="w-full"
              >
                {isSearching ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-2 h-4 w-4" />
                )}
                Search Numbers
              </Button>
            </>
          )}

          {/* Results */}
          {searchResults?.numbers && searchResults.numbers.length > 0 && (
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {searchResults.numbers.map((num) => (
                <div
                  key={num.phone_number}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="font-mono text-sm font-medium">
                        {num.phone_number}
                      </p>
                      <div className="flex gap-1 mt-1">
                        <Badge variant="secondary" className="text-xs">
                          {getProviderLabel(num.provider)}
                        </Badge>
                        {num.capabilities.voice && (
                          <Badge variant="outline" className="text-xs">
                            Voice
                          </Badge>
                        )}
                        {num.capabilities.sms && (
                          <Badge variant="outline" className="text-xs">
                            SMS
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground">
                      ${Number(num.monthly_cost).toFixed(2)}/mo
                    </span>
                    <Button
                      size="sm"
                      onClick={() => handlePurchaseClick(num)}
                      disabled={purchaseMutation.isPending || !tenantId}
                      title={
                        tenantId
                          ? undefined
                          : "Open a tenant workspace to purchase this number"
                      }
                    >
                      Purchase
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {searchResults?.numbers && searchResults.numbers.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-4">
              No numbers found. Try a different search.
            </p>
          )}

          {!tenantId && (
            <p className="text-center text-sm text-muted-foreground py-2">
              Open a tenant workspace to purchase and assign numbers safely.
            </p>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Purchase Confirmation Dialog ─────────────────────── */}
      <Dialog
        open={!!purchaseTarget}
        onOpenChange={(v) => {
          if (!v) setPurchaseTarget(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Confirm Purchase</DialogTitle>
            <DialogDescription>
              Review the details below and confirm the purchase.
            </DialogDescription>
          </DialogHeader>

          {purchaseTarget && (
            <div className="space-y-4">
              {/* Number details */}
              <div className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Number</span>
                  <span className="font-mono font-medium">
                    {purchaseTarget.phone_number}
                  </span>
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Provider</span>
                  <Badge variant="secondary">
                    {getProviderLabel(purchaseTarget.provider)}
                  </Badge>
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Monthly Cost
                  </span>
                  <span className="font-medium">
                    ${Number(purchaseTarget.monthly_cost).toFixed(2)}/mo
                  </span>
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Capabilities
                  </span>
                  <div className="flex gap-1">
                    {purchaseTarget.capabilities.voice && (
                      <Badge variant="outline" className="text-xs">
                        Voice
                      </Badge>
                    )}
                    {purchaseTarget.capabilities.sms && (
                      <Badge variant="outline" className="text-xs">
                        SMS
                      </Badge>
                    )}
                    {purchaseTarget.capabilities.mms && (
                      <Badge variant="outline" className="text-xs">
                        MMS
                      </Badge>
                    )}
                  </div>
                </div>
                {tenantName && (
                  <>
                    <Separator />
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        Workspace
                      </span>
                      <span className="text-sm font-medium">{tenantName}</span>
                    </div>
                  </>
                )}
              </div>

              {/* Provider credential notice */}
              <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3">
                <ShieldCheck className="mt-0.5 h-4 w-4 text-green-600 dark:text-green-400" />
                <p className="text-xs text-muted-foreground">
                  This number will be purchased using your saved{" "}
                  <strong>{getProviderLabel(purchaseTarget.provider)}</strong>{" "}
                  credentials. You can manage provider API keys in the Providers
                  section.
                </p>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setPurchaseTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirmPurchase}
              disabled={purchaseMutation.isPending}
            >
              {purchaseMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Phone className="mr-2 h-4 w-4" />
              )}
              Confirm Purchase
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
