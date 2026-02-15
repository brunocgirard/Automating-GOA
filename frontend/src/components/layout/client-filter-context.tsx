"use client";

import { createContext, useContext } from "react";

interface ClientFilterContextValue {
  selectedClientId: string | null;
  setSelectedClientId: (id: string | null) => void;
}

const ClientFilterContext = createContext<ClientFilterContextValue | null>(null);

export function ClientFilterProvider({
  value,
  children,
}: {
  value: ClientFilterContextValue;
  children: React.ReactNode;
}) {
  return (
    <ClientFilterContext.Provider value={value}>
      {children}
    </ClientFilterContext.Provider>
  );
}

export function useClientFilter(): ClientFilterContextValue {
  const context = useContext(ClientFilterContext);
  if (!context) {
    throw new Error("useClientFilter must be used inside ClientFilterProvider.");
  }
  return context;
}
