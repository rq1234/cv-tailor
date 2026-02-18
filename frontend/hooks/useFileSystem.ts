"use client";

import { useCallback, useEffect, useState } from "react";
import { get, set } from "idb-keyval";

const IDB_KEY = "rootDirectoryHandle";

export function useFileSystem() {
  const [directoryHandle, setDirectoryHandle] =
    useState<FileSystemDirectoryHandle | null>(null);
  const [directoryName, setDirectoryName] = useState<string | null>(null);

  // Restore handle from IndexedDB on mount
  useEffect(() => {
    (async () => {
      const stored = await get<FileSystemDirectoryHandle>(IDB_KEY);
      if (stored) {
        const permission = await stored.queryPermission({ mode: "readwrite" });
        if (permission === "granted") {
          setDirectoryHandle(stored);
          setDirectoryName(stored.name);
        }
      }
    })();
  }, []);

  const pickDirectory = useCallback(async () => {
    try {
      const handle = await window.showDirectoryPicker({ mode: "readwrite" });
      await set(IDB_KEY, handle);
      setDirectoryHandle(handle);
      setDirectoryName(handle.name);
      return handle;
    } catch {
      return null;
    }
  }, []);

  const requestPermission = useCallback(async () => {
    if (!directoryHandle) return false;
    const permission = await directoryHandle.requestPermission({
      mode: "readwrite",
    });
    return permission === "granted";
  }, [directoryHandle]);

  const saveFile = useCallback(
    async (
      companyName: string,
      fileName: string,
      blob: Blob
    ): Promise<boolean> => {
      if (!directoryHandle) return false;

      try {
        // Ensure permission
        const permission = await directoryHandle.queryPermission({
          mode: "readwrite",
        });
        if (permission !== "granted") {
          const result = await directoryHandle.requestPermission({
            mode: "readwrite",
          });
          if (result !== "granted") return false;
        }

        const companyDir = await directoryHandle.getDirectoryHandle(
          companyName,
          { create: true }
        );
        const fileHandle = await companyDir.getFileHandle(fileName, {
          create: true,
        });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
        return true;
      } catch (error) {
        console.error("Failed to save file:", error);
        return false;
      }
    },
    [directoryHandle]
  );

  return {
    directoryHandle,
    directoryName,
    pickDirectory,
    requestPermission,
    saveFile,
    hasDirectory: !!directoryHandle,
  };
}
