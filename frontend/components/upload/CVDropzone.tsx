"use client";

import { useCallback, useRef, useState } from "react";

interface CVDropzoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export function CVDropzone({ onFileSelected, disabled }: CVDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): boolean => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are supported");
      return false;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be under 10MB");
      return false;
    }
    setError(null);
    return true;
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (disabled) return;

      const file = e.dataTransfer.files[0];
      if (file && validateFile(file)) {
        onFileSelected(file);
      }
    },
    [disabled, onFileSelected]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && validateFile(file)) {
        onFileSelected(file);
      }
    },
    [onFileSelected]
  );

  const handleClick = () => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  return (
    <div
      onClick={handleClick}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className={`
        flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors
        ${isDragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25"}
        ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:border-primary/50"}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
      <div className="text-center">
        <svg
          className="mx-auto h-12 w-12 text-muted-foreground"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p className="mt-4 text-sm font-medium">
          Drag and drop your CV here, or <span className="text-primary hover:underline">browse</span>
        </p>
        <p className="mt-1 text-xs text-muted-foreground">PDF only, max 10MB</p>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  );
}
