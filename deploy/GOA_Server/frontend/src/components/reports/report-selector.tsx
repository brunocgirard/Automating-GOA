"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface ReportClientOption {
  id: string;
  name: string;
}

export interface ReportMachineOption {
  id: string;
  label: string;
}

interface ReportSelectorProps {
  clientId: string;
  machineId: string;
  clients: ReportClientOption[];
  machines: ReportMachineOption[];
  onClientChange: (value: string) => void;
  onMachineChange: (value: string) => void;
}

export function ReportSelector({
  clientId,
  machineId,
  clients,
  machines,
  onClientChange,
  onMachineChange,
}: ReportSelectorProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="w-full space-y-1 sm:w-auto">
        <label className="text-sm font-medium">Client</label>
        <Select
          value={clientId}
          onValueChange={(value) => {
            onClientChange(value);
            onMachineChange("");
          }}
        >
          <SelectTrigger className="w-full sm:w-[260px]">
            <SelectValue placeholder="Select a client" />
          </SelectTrigger>
          <SelectContent>
            {clients.map((client) => (
              <SelectItem key={client.id} value={client.id}>
                {client.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="w-full space-y-1 sm:w-auto">
        <label className="text-sm font-medium">Machine</label>
        <Select value={machineId} onValueChange={onMachineChange} disabled={!clientId}>
          <SelectTrigger className="w-full sm:w-[300px]">
            <SelectValue placeholder="Select a machine" />
          </SelectTrigger>
          <SelectContent>
            {machines.map((machine) => (
              <SelectItem key={machine.id} value={machine.id}>
                {machine.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
