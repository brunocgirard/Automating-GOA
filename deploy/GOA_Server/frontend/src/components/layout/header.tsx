"use client";

import { useState } from "react";
import { Menu } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { logout, removeMyGeminiKey, setMyGeminiKey, testMyGeminiKey } from "@/lib/api";
import type { User } from "@/lib/types";

interface HeaderProps {
  onToggleSidebar: () => void;
  currentUser: User | null;
  onUserChange: (user: User | null) => void;
}

export function Header({ onToggleSidebar, currentUser, onUserChange }: HeaderProps) {
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [busyAction, setBusyAction] = useState<"save" | "test" | "remove" | "logout" | null>(null);

  async function handleLogout() {
    setBusyAction("logout");
    try {
      await logout();
    } catch {
      // Ignore logout API failures and force local redirect.
    } finally {
      onUserChange(null);
      setBusyAction(null);
      router.replace("/login");
    }
  }

  async function handleSaveKey() {
    const trimmed = apiKeyInput.trim();
    if (!trimmed) {
      setStatusError(true);
      setStatusMessage("Enter a Gemini API key before saving.");
      return;
    }

    setBusyAction("save");
    setStatusMessage(null);
    try {
      const updated = await setMyGeminiKey(trimmed);
      onUserChange(updated);
      setApiKeyInput("");
      setStatusError(false);
      setStatusMessage("Gemini API key saved.");
    } catch (error) {
      setStatusError(true);
      setStatusMessage(error instanceof Error ? error.message : "Failed to save Gemini API key.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleTestKey() {
    setBusyAction("test");
    setStatusMessage(null);
    try {
      const result = await testMyGeminiKey();
      setStatusError(!result.valid);
      setStatusMessage(result.valid ? "Gemini API key is valid." : result.error ?? "Gemini API key test failed.");
    } catch (error) {
      setStatusError(true);
      setStatusMessage(error instanceof Error ? error.message : "Failed to test Gemini API key.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRemoveKey() {
    setBusyAction("remove");
    setStatusMessage(null);
    try {
      const updated = await removeMyGeminiKey();
      onUserChange(updated);
      setApiKeyInput("");
      setStatusError(false);
      setStatusMessage("Gemini API key removed.");
    } catch (error) {
      setStatusError(true);
      setStatusMessage(error instanceof Error ? error.message : "Failed to remove Gemini API key.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-white px-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          className="shrink-0"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[#c00000]">
            <span className="text-sm font-bold text-white">P</span>
          </div>
          <h1 className="text-lg font-semibold tracking-tight">PM Tool</h1>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-neutral-800">
              {currentUser?.display_name || currentUser?.username || "Unknown User"}
            </p>
            <p className="text-xs text-neutral-500">
              {currentUser?.has_gemini_key ? "Key set" : "No Gemini key"}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setStatusMessage(null);
              setStatusError(false);
              setSettingsOpen(true);
            }}
          >
            Gemini Key
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleLogout()}
            disabled={busyAction === "logout"}
          >
            Logout
          </Button>
        </div>
      </header>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Gemini API Key</DialogTitle>
            <DialogDescription>
              Save your personal Gemini key for extraction and generation.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Input
              type="password"
              placeholder="Paste Gemini API key"
              value={apiKeyInput}
              onChange={(event) => setApiKeyInput(event.target.value)}
            />
            <p className="text-xs text-neutral-600">
              Current status: {currentUser?.has_gemini_key ? "Key configured" : "No key configured"}
            </p>
            {statusMessage ? (
              <p className={`text-sm ${statusError ? "text-red-700" : "text-green-700"}`}>{statusMessage}</p>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => void handleTestKey()}
              disabled={busyAction === "test" || busyAction === "save" || busyAction === "remove"}
            >
              Test Key
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleRemoveKey()}
              disabled={busyAction === "remove" || busyAction === "save" || busyAction === "test"}
            >
              Remove Key
            </Button>
            <Button
              onClick={() => void handleSaveKey()}
              disabled={busyAction === "save" || busyAction === "test" || busyAction === "remove"}
            >
              Save Key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
